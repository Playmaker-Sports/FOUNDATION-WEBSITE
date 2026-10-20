"""Public Foundation scholarship intake, with the private Sheet as its record.

The configured Gunicorn deployment has one worker and multiple threads. A shared
lock plus a persistent submission-ID lookup makes retries safe in that deployment,
including retries after a Sheets response times out. Multiple worker processes
would require a shared transactional idempotency store before scaling this flow.
"""

from datetime import date, datetime, timezone
from email.utils import parseaddr
import json
import logging
import os
import re
import threading
from uuid import UUID
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_cors import CORS


logger = logging.getLogger(__name__)
SCHOLARSHIP_TIMEZONE = ZoneInfo('America/Los_Angeles')
DEADLINE_DATE = date(2026, 11, 20)
DEADLINE_EXCLUSIVE = datetime(2026, 11, 21, tzinfo=SCHOLARSHIP_TIMEZONE)
POLICY_VERSION = '2026-10-15-grades-6-12'
AWARD_NAME = '2026 Playmakers Cup Student-Athlete Scholarship'
SHEETS_SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
ELIGIBLE_EXPENSES = ('Club soccer fees', 'Soccer equipment')
ELIGIBLE_GRADES = ('6th grade', '7th grade', '8th grade', '9th grade', '10th grade', '11th grade', '12th grade')
FOUNDATION_ORIGINS = ('https://playmakersportsfoundation.org', 'https://www.playmakersportsfoundation.org')
EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
TEXT_LIMITS = {
    'applicant_name': 200,
    'date_of_birth': 10,
    'grade_level': 100,
    'city': 200,
    'school': 200,
    'guardian_name': 200,
    'guardian_email': 254,
    'applicant_email': 254,
    'club_team': 300,
    'team_age_group': 100,
    'growth': 5000,
    'challenge': 5000,
    'goals': 5000,
    'financial_need': 5000,
    'additional_context': 3000,
}
REQUIRED_TEXT = (
    'applicant_name', 'date_of_birth', 'grade_level', 'city', 'school',
    'club_team', 'team_age_group', 'growth', 'challenge', 'goals', 'financial_need',
)
REQUIRED_ACKNOWLEDGMENTS = (
    'participation_confirmed', 'accuracy_ack', 'privacy_ack', 'payment_ack',
)
SHEET_COLUMNS = (
    'Application ID', 'Submitted at (UTC)', 'Award', 'Award maximum (USD)',
    'Applicant full name', 'Date of birth', 'Age at submission', 'Grade level',
    'City', 'Current school', 'Parent/guardian name', 'Parent/guardian email',
    'Applicant email', 'Club and team', 'Team age group',
    'Cup participation confirmed', 'Soccer and personal growth',
    'Challenge and response', 'Future goals', 'Financial need and scholarship impact',
    'Eligible expenses', 'Additional context', 'Parent/guardian acknowledgment',
    'Accuracy acknowledgment', 'Privacy acknowledgment', 'Reimbursement acknowledgment',
    'Optional publicity contact consent', 'Deadline (Pacific)', 'Policy version',
    'Source', 'Review status', 'Cup participation verified', 'Financial need reviewed',
    'Selection rationale', 'Approved reimbursement (USD)', 'Receipts/payment record',
)
_submission_lock = threading.Lock()


class ScholarshipConfigurationError(RuntimeError):
    """The private intake destination has not been configured correctly."""


class ScholarshipConflictError(RuntimeError):
    """This submission ID already belongs to a different saved application."""


def utc_now():
    return datetime.now(timezone.utc)


def applications_open(now=None):
    return (now or utc_now()) < DEADLINE_EXCLUSIVE


def validate_application(payload, now=None):
    """Validate independently of client controls; never infer checked consents."""
    if not isinstance(payload, dict):
        return None, 'Request body must be a JSON object'
    if isinstance(payload.get('_honey'), str) and payload['_honey'].strip():
        return {'honeypot': True}, None

    clean = {}
    for field, limit in TEXT_LIMITS.items():
        value = payload.get(field, '')
        if not isinstance(value, str):
            return None, f'{field} must be text'
        value = value.strip()
        if field in REQUIRED_TEXT and not value:
            return None, f'{field} is required'
        if len(value) > limit:
            return None, f'{field} is too long'
        if any(ord(char) < 32 and char not in '\n\r\t' for char in value):
            return None, f'{field} contains invalid characters'
        clean[field] = value

    if clean['grade_level'] not in ELIGIBLE_GRADES:
        return None, 'Applicants must currently be in grades 6 through 12'

    try:
        raw_id = payload.get('submission_id', '')
        submission_id = UUID(raw_id) if isinstance(raw_id, str) else None
        if submission_id is None or submission_id.version != 4:
            raise ValueError
        clean['submission_id'] = str(submission_id)
    except (ValueError, AttributeError):
        return None, 'submission_id must be a UUID generated for this application'

    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', clean['date_of_birth']):
        return None, 'date_of_birth is invalid'
    try:
        birthday = date.fromisoformat(clean['date_of_birth'])
    except ValueError:
        return None, 'date_of_birth is invalid'
    today = (now or utc_now()).astimezone(SCHOLARSHIP_TIMEZONE).date()
    if birthday > today:
        return None, 'date_of_birth cannot be in the future'
    age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    clean['age_at_submission'] = age
    is_minor = age < 18
    for field in ('guardian_name', 'guardian_email') if is_minor else ('applicant_email',):
        if not clean[field]:
            return None, f'{field} is required'
    for field in ('guardian_email', 'applicant_email'):
        if clean[field] and not EMAIL_PATTERN.fullmatch(clean[field]):
            return None, f'{field} is invalid'

    for field in REQUIRED_ACKNOWLEDGMENTS:
        if payload.get(field) is not True:
            return None, f'{field} is required'
        clean[field] = True
    if is_minor and payload.get('guardian_ack') is not True:
        return None, 'guardian_ack is required for applicants under 18'
    clean['guardian_ack'] = payload.get('guardian_ack') is True if is_minor else False
    publicity = payload.get('publicity_consent', False)
    if not isinstance(publicity, bool):
        return None, 'publicity_consent must be true or false'
    clean['publicity_consent'] = publicity

    expenses = payload.get('eligible_expenses')
    if (not isinstance(expenses, list) or not expenses or len(expenses) > len(ELIGIBLE_EXPENSES)
            or any(not isinstance(item, str) or item not in ELIGIBLE_EXPENSES for item in expenses)
            or len(set(expenses)) != len(expenses)):
        return None, 'Select club soccer fees, soccer equipment, or both'
    clean['eligible_expenses'] = [item for item in ELIGIBLE_EXPENSES if item in expenses]
    return clean, None


def _sheet_settings():
    sheet_id = os.environ.get('FOUNDATION_SCHOLARSHIP_SHEET_ID', '').strip()
    sheet_range = os.environ.get('FOUNDATION_SCHOLARSHIP_SHEET_RANGE', 'Applications!A:AJ').strip()
    # Keep submission IDs in column A and the fixed export contract in A:AJ.
    if not sheet_id or not re.fullmatch(r"(?:[A-Za-z0-9_ -]+|'(?:[^']|'')+')!A:AJ", sheet_range):
        raise ScholarshipConfigurationError('Scholarship spreadsheet is not configured')
    return sheet_id, sheet_range, sheet_range.rsplit('!', 1)[0]


def _sheet_client(load_credentials, build_service, authorized_http):
    sheet_id, sheet_range, tab = _sheet_settings()
    try:
        credentials = load_credentials(SHEETS_SCOPE)
    except (RuntimeError, ValueError) as exc:
        raise ScholarshipConfigurationError('Scholarship credentials are not configured') from exc
    service = build_service('sheets', 'v4', credentials=credentials, cache_discovery=False)
    http = authorized_http(credentials)
    values = service.spreadsheets().values()
    headers = values.get(spreadsheetId=sheet_id, range=f'{tab}!A1:AJ1').execute(http=http).get('values', [])
    if not headers or headers[0] != list(SHEET_COLUMNS):
        raise ScholarshipConfigurationError('Scholarship spreadsheet headers do not match the application template')
    return values, http, sheet_id, sheet_range, tab


def application_row(application, submitted_at):
    agreed = lambda flag: 'Agreed' if flag else 'Not applicable'
    return [
        application['submission_id'], submitted_at, AWARD_NAME, 500,
        application['applicant_name'], application['date_of_birth'], application['age_at_submission'],
        application['grade_level'], application['city'], application['school'],
        application['guardian_name'], application['guardian_email'], application['applicant_email'],
        application['club_team'], application['team_age_group'], 'Confirmed',
        application['growth'], application['challenge'], application['goals'], application['financial_need'],
        '; '.join(application['eligible_expenses']), application['additional_context'],
        agreed(application['guardian_ack']), 'Agreed', 'Agreed', 'Agreed',
        'Yes' if application['publicity_consent'] else 'No',
        '2026-11-20 11:59 PM America/Los_Angeles', POLICY_VERSION, 'Foundation website',
        'Submitted', '', '', '', '', '',
    ]


def _save_application(application, load_credentials, build_service, authorized_http):
    # Lookup occurs inside the lock, including when a previous append timed out.
    # Neither requests nor Google client objects are shared between threads.
    with _submission_lock:
        values, http, sheet_id, sheet_range, tab = _sheet_client(
            load_credentials, build_service, authorized_http,
        )
        existing = values.get(spreadsheetId=sheet_id, range=f'{tab}!A2:B').execute(http=http).get('values', [])
        for row_number, row in enumerate(existing, start=2):
            if row and row[0] == application['submission_id']:
                saved = values.get(
                    spreadsheetId=sheet_id, range=f'{tab}!A{row_number}:AJ{row_number}',
                ).execute(http=http).get('values', [])
                # Sheets omits trailing blank cells. Only compare applicant-entered
                # values (E:AA, excluding computed age G), not review decisions or
                # the submission time, policy version, and other generated metadata.
                saved_row = saved[0] if saved else []
                saved_row = saved_row + [''] * max(0, len(SHEET_COLUMNS) - len(saved_row))
                candidate = application_row(application, '')
                if any(saved_row[index] != candidate[index] for index in range(4, 27) if index != 6):
                    raise ScholarshipConflictError('An earlier version of this application is already saved')
                return row[1] if len(row) > 1 else '', True
        submitted_at = utc_now().isoformat()
        values.append(
            spreadsheetId=sheet_id,
            range=sheet_range,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [application_row(application, submitted_at)]},
        ).execute(http=http)
        return submitted_at, False


def _email_settings():
    staff_email = os.environ.get('FOUNDATION_SCHOLARSHIP_TO_EMAIL', 'info@playmakersportsfoundation.org').strip()
    # This service has its own Foundation credentials and sender. Never fall back
    # to the tournament company's sending domain or another service's secrets.
    sender = os.environ.get('FOUNDATION_SCHOLARSHIP_FROM_EMAIL', '').strip()
    return staff_email, sender


def _email_configuration_present():
    staff_email, sender = _email_settings()
    sender_address = parseaddr(sender)[1]
    return bool(
        os.environ.get('RESEND_API_KEY', '').strip()
        and EMAIL_PATTERN.fullmatch(staff_email)
        and EMAIL_PATTERN.fullmatch(sender_address)
    )


def _default_load_credentials(scopes):
    """Load only credentials explicitly configured on this Foundation service."""
    from google.oauth2 import service_account

    raw_credentials = os.environ.get('GOOGLE_CREDENTIALS', '').strip()
    if raw_credentials:
        return service_account.Credentials.from_service_account_info(json.loads(raw_credentials), scopes=scopes)
    raise RuntimeError('Google service account credentials are not configured')


def _default_build_service(*args, **kwargs):
    from googleapiclient.discovery import build

    return build(*args, **kwargs)


def _default_authorized_http(credentials):
    import google_auth_httplib2
    import httplib2

    return google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=120))


def _default_send_email(sender, recipient, reply_to, subject, body):
    import requests

    api_key = os.environ.get('RESEND_API_KEY', '').strip()
    if not api_key or not sender or not recipient or not reply_to:
        raise RuntimeError('Scholarship email delivery is not configured')
    response = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'from': sender, 'to': [recipient], 'reply_to': reply_to, 'subject': subject, 'text': body},
        timeout=15,
    )
    response.raise_for_status()


def _notify_staff(application_id, submitted_at, send_email):
    recipient, sender = _email_settings()
    sheet_id, _, _ = _sheet_settings()
    body = (
        f'A new {AWARD_NAME} application was saved.\n\n'
        f'Application ID: {application_id}\nSubmitted at (UTC): {submitted_at}\n\n'
        f'Review the full response in the private application spreadsheet:\n'
        f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit\n\n'
        'Verify Cup participation and financial need before selection. Request paid club-fee '
        'or soccer-equipment receipts only from the selected recipient. Reimburse documented '
        'eligible expenses up to $500, with a guardian handling payment for a minor. '
        'Record the selection reason, receipts, and payment in the private review columns.\n'
    )
    send_email(sender, recipient, recipient, 'New Foundation scholarship application', body)


def _confirm_application(application, send_email):
    staff_email, sender = _email_settings()
    recipient = application['guardian_email'] if application['age_at_submission'] < 18 else application['applicant_email']
    body = (
        f'Thank you for applying for the {AWARD_NAME}. We received your application.\n\n'
        f"Application reference: {application['submission_id']}\n\n"
        'Applications close November 20, 2026 at 11:59 PM Pacific. '
        'The Foundation will review your application. This email confirms receipt; '
        'it does not mean an award has been granted.\n\n'
        'You do not need to send receipts now. We will request paid club soccer fee '
        'or soccer equipment receipts only from the selected recipient.\n\n'
        f'For questions or corrections, reply to this email or contact {staff_email} '
        'and include your application reference.\n\n'
        'Playmaker Sports Foundation\n'
    )
    send_email(sender, recipient, staff_email, 'We received your Foundation scholarship application', body)


def register_scholarship_routes(app, limiter, *, load_credentials=None, build_service=None, authorized_http=None, send_email=None):
    load_credentials = load_credentials or _default_load_credentials
    build_service = build_service or _default_build_service
    authorized_http = authorized_http or _default_authorized_http
    send_email = send_email or _default_send_email
    blueprint = Blueprint('foundation_scholarships', __name__)
    # Scoped here so the intake also works with older API deployments whose
    # global CORS allowlist predates the Foundation domain.
    CORS(blueprint, origins=FOUNDATION_ORIGINS, methods=['GET', 'POST', 'OPTIONS'])

    @blueprint.errorhandler(429)
    def scholarship_rate_limit_exceeded(error):
        # Older API versions turn generic HTTPExceptions into 500 responses.
        return jsonify(success=False, message='Too many requests. Please wait a minute and try again.'), 429

    @blueprint.get('/api/foundation/scholarship-applications/status')
    def scholarship_status():
        status = {
            'accepting_applications': False,
            # Configuration presence is not a Google write or Resend delivery test.
            'email_configured': _email_configuration_present(),
            'deadline': DEADLINE_DATE.isoformat(),
            'deadline_timezone': 'America/Los_Angeles',
            'deadline_label': 'November 20, 2026 at 11:59 PM Pacific',
        }
        if not applications_open():
            return jsonify(dict(status, reason='deadline_passed'))
        if not status['email_configured']:
            return jsonify(dict(status, reason='not_configured'))
        try:
            _sheet_client(load_credentials, build_service, authorized_http)
        except ScholarshipConfigurationError:
            return jsonify(dict(status, reason='not_configured'))
        except Exception as exc:
            logger.warning('Scholarship intake availability check failed [%s]', type(exc).__name__)
            return jsonify(dict(status, reason='temporarily_unavailable'))
        return jsonify(dict(status, accepting_applications=True))

    @blueprint.post('/api/foundation/scholarship-applications')
    @limiter.limit('5 per minute')
    def submit_scholarship_application():
        now = utc_now()
        application, error = validate_application(request.get_json(silent=True), now=now)
        if error:
            return jsonify(success=False, message=error), 400
        if application.get('honeypot'):
            return jsonify(success=True)
        if not applications_open(now):
            return jsonify(success=False, message='The application deadline has passed.'), 410
        if not _email_configuration_present():
            return jsonify(success=False, message='Scholarship applications are not set up yet. Please try again later.'), 503
        try:
            submitted_at, duplicate = _save_application(
                application, load_credentials, build_service, authorized_http,
            )
        except ScholarshipConfigurationError:
            return jsonify(success=False, message='Scholarship applications are not set up yet. Please try again later.'), 503
        except ScholarshipConflictError:
            return jsonify(
                success=False, application_id=application['submission_id'],
                message='An earlier version of this application was already saved. Your latest edits have not been saved. Please contact the Foundation with your application ID to request a correction.',
            ), 409
        except Exception as exc:
            logger.error('Scholarship application storage failed [%s]', type(exc).__name__)
            return jsonify(success=False, message='We could not confirm your application was saved. Please retry using this form.'), 502

        notification_sent = False
        confirmation_sent = False
        if not duplicate:
            try:
                _notify_staff(application['submission_id'], submitted_at, send_email)
                notification_sent = True
            except Exception as exc:
                # The saved application remains successful; avoid duplicate applications
                # just because a staff notification could not be sent.
                logger.error('Scholarship staff notification failed [%s]', type(exc).__name__)
            try:
                _confirm_application(application, send_email)
                confirmation_sent = True
            except Exception as exc:
                # Staff and applicant delivery are independent of each other and
                # of the successful save. Keep personal details out of logs.
                logger.error('Scholarship application confirmation failed [%s]', type(exc).__name__)
        logger.info('Scholarship application saved id=%s duplicate=%s', application['submission_id'], duplicate)
        return jsonify(
            success=True, application_id=application['submission_id'],
            submitted_at=submitted_at, already_submitted=duplicate,
            notification_sent=notification_sent, confirmation_sent=confirmation_sent,
        )

    app.register_blueprint(blueprint)
