"""Scholarship tests use mocked Google services and never save live data."""

from datetime import datetime, timezone
import os
import re
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import foundation_scholarships as scholarships


NOW = datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc)
ROUTE = '/api/foundation/scholarship-applications'


def valid_application(**changes):
    return dict({
        'submission_id': str(uuid4()),
        'applicant_name': 'Taylor Player',
        'date_of_birth': '2012-04-15',
        'grade_level': '8th grade',
        'city': 'Moorpark',
        'school': 'Example School',
        'guardian_name': 'Jordan Parent',
        'guardian_email': 'parent@example.com',
        'applicant_email': '',
        'club_team': 'Example FC 2012',
        'team_age_group': 'U15',
        'growth': 'Soccer taught me to listen to my teammates.',
        'challenge': 'I learned to keep practicing after an injury.',
        'goals': 'I want to keep learning at school and on the field.',
        'financial_need': 'Our family needs help covering club soccer fees.',
        'eligible_expenses': ['Club soccer fees', 'Soccer equipment'],
        'additional_context': '',
        'participation_confirmed': True,
        'guardian_ack': True,
        'accuracy_ack': True,
        'privacy_ack': True,
        'payment_ack': True,
        'publicity_consent': False,
        '_honey': '',
    }, **changes)


class ScholarshipValidationTests(unittest.TestCase):
    def validate(self, **changes):
        return scholarships.validate_application(valid_application(**changes), NOW)

    def test_minor_can_apply_without_personal_email_or_publicity_consent(self):
        application, error = self.validate()
        self.assertIsNone(error)
        self.assertEqual(application['age_at_submission'], 14)
        self.assertFalse(application['publicity_consent'])

    def test_adult_requires_own_email_and_does_not_require_guardian(self):
        application, error = self.validate(
            date_of_birth='2008-10-15', applicant_email='adult@example.com',
            guardian_name='', guardian_email='', guardian_ack=False,
            grade_level='12th grade', school='Example High School',
        )
        self.assertIsNone(error)
        self.assertEqual(application['age_at_submission'], 18)
        self.assertFalse(application['guardian_ack'])
        self.assertEqual(self.validate(date_of_birth='2008-10-15')[1], 'applicant_email is required')

    def test_age_uses_pacific_date_and_exact_birthday(self):
        # UTC October 16 is still October 15 in California.
        now = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)
        payload = valid_application(date_of_birth='2008-10-16', guardian_ack=False)
        _, error = scholarships.validate_application(payload, now)
        self.assertEqual(error, 'guardian_ack is required for applicants under 18')

    def test_only_grades_six_through_twelve_are_eligible_without_an_age_cap(self):
        for grade in scholarships.ELIGIBLE_GRADES:
            with self.subTest(grade=grade):
                _, error = self.validate(grade_level=grade)
                self.assertIsNone(error)
        _, error = self.validate(date_of_birth='2006-01-01', grade_level='12th grade', applicant_email='adult@example.com')
        self.assertIsNone(error)
        for grade in ('Preschool', 'Kindergarten', '5th grade', 'College', 'Not currently enrolled', '13th grade', '6'):
            with self.subTest(grade=grade):
                self.assertEqual(self.validate(grade_level=grade)[1], 'Applicants must currently be in grades 6 through 12')

    def test_each_minor_guardian_field_and_ack_is_required(self):
        for field in ('guardian_name', 'guardian_email', 'guardian_ack'):
            with self.subTest(field=field):
                _, error = self.validate(**{field: False if field == 'guardian_ack' else ''})
                self.assertIn(field, error)

    def test_each_required_acknowledgment_requires_boolean_true(self):
        for field in scholarships.REQUIRED_ACKNOWLEDGMENTS:
            for value in (False, 'true', 1, None):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.validate(**{field: value})[1], f'{field} is required')

    def test_rejects_invalid_or_future_birthdate_and_invalid_email(self):
        for birthday in ('2026-10-16', '2012-02-30', '2012-4-15'):
            self.assertIsNotNone(self.validate(date_of_birth=birthday)[1])
        self.assertEqual(self.validate(guardian_email='bad\n@example.com')[1], 'guardian_email is invalid')

    def test_need_and_essays_are_required_and_bounded(self):
        for field in ('growth', 'challenge', 'goals', 'financial_need'):
            self.assertEqual(self.validate(**{field: ''})[1], f'{field} is required')
            self.assertEqual(self.validate(**{field: 'x' * 5001})[1], f'{field} is too long')
        self.assertEqual(self.validate(additional_context='x' * 3001)[1], 'additional_context is too long')

    def test_expense_selection_rejects_unsupported_types_and_categories(self):
        for value in (None, [], 'Soccer equipment', ['Cash'], ['Soccer equipment'] * 2, [None]):
            with self.subTest(value=value):
                self.assertIsNotNone(self.validate(eligible_expenses=value)[1])
        self.assertIsNone(self.validate(eligible_expenses=['Soccer equipment'])[1])

    def test_rejects_malformed_submission_id(self):
        self.assertIn('submission_id', self.validate(submission_id='not-an-id')[1])

    def test_deadline_is_inclusive_for_whole_pacific_day(self):
        for timestamp, expected in (
            ('2026-11-20T23:59:59.999999-08:00', True),
            ('2026-11-21T07:59:59.999999+00:00', True),
            ('2026-11-21T08:00:00+00:00', False),
            ('2026-11-21T00:00:00-08:00', False),
        ):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(scholarships.applications_open(datetime.fromisoformat(timestamp)), expected)


class ScholarshipEndpointTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'FOUNDATION_SCHOLARSHIP_API_ENABLED': 'true',
            'FOUNDATION_SCHOLARSHIP_SHEET_ID': 'private-test-sheet',
            'FOUNDATION_SCHOLARSHIP_SHEET_RANGE': 'Applications!A:AJ',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clock = patch.object(scholarships, 'utc_now', return_value=NOW)
        self.clock_mock = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.load_credentials = MagicMock(return_value='credentials')
        self.build_service = MagicMock()
        self.authorized_http = MagicMock(return_value='authorized-http')
        self.values = self.build_service.return_value.spreadsheets.return_value.values.return_value
        self.headers = list(scholarships.SHEET_COLUMNS)
        self.rows = []

        def get_values(**kwargs):
            result = MagicMock()
            if kwargs['range'].endswith('A1:AJ1'):
                result.execute.return_value = {'values': [self.headers]}
            elif match := re.search(r'!A(\d+):AJ\d+$', kwargs['range']):
                index = int(match.group(1)) - 2
                result.execute.return_value = {'values': self.rows[index:index + 1]}
            else:
                result.execute.return_value = {'values': [row[:2] for row in self.rows]}
            return result

        self.values.get.side_effect = get_values

        def append_values(**kwargs):
            result = MagicMock()
            self.rows.extend(kwargs['body']['values'])
            result.execute.return_value = {'updates': {'updatedRows': 1}}
            return result

        self.values.append.side_effect = append_values
        app = Flask(__name__)
        app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
        self.limiter = Limiter(get_remote_address, app=app)
        scholarships.register_scholarship_routes(
            app, self.limiter,
            load_credentials=self.load_credentials, build_service=self.build_service,
            authorized_http=self.authorized_http,
        )
        self.client = app.test_client()

    def test_status_checks_private_sheet_access_and_exact_headers(self):
        response = self.client.get(f'{ROUTE}/status')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['accepting_applications'])
        self.assertEqual(response.json['deadline_timezone'], 'America/Los_Angeles')
        self.values.append.assert_not_called()

    def test_unconfigured_or_mismatched_sheet_never_advertises_ready(self):
        with patch.dict(os.environ, {'FOUNDATION_SCHOLARSHIP_SHEET_ID': ''}):
            self.assertFalse(self.client.get(f'{ROUTE}/status').json['accepting_applications'])
            response = self.client.post(ROUTE, json=valid_application())
            self.assertEqual(response.status_code, 503)
        self.headers[0] = 'Wrong sheet'
        self.assertFalse(self.client.get(f'{ROUTE}/status').json['accepting_applications'])
        self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 503)
        self.values.append.assert_not_called()

    def test_unavailable_sheet_status_is_closed(self):
        self.values.get.side_effect = TimeoutError('Read timed out')
        response = self.client.get(f'{ROUTE}/status')
        self.assertFalse(response.json['accepting_applications'])
        self.assertEqual(response.json['reason'], 'temporarily_unavailable')

    def test_append_matches_template_preserves_formula_text_and_has_no_email_claims(self):
        payload = valid_application(applicant_name='=HYPERLINK("example")')
        response = self.client.post(ROUTE, json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
        self.assertEqual(response.json['application_id'], payload['submission_id'])
        kwargs = self.values.append.call_args.kwargs
        self.assertEqual(kwargs['valueInputOption'], 'RAW')
        self.assertEqual(kwargs['insertDataOption'], 'INSERT_ROWS')
        self.assertEqual(kwargs['range'], 'Applications!A:AJ')
        self.assertEqual(kwargs['spreadsheetId'], 'private-test-sheet')
        row = dict(zip(scholarships.SHEET_COLUMNS, kwargs['body']['values'][0], strict=True))
        self.assertEqual(row['Applicant full name'], payload['applicant_name'])
        self.assertEqual(row['Optional publicity contact consent'], 'No')
        self.assertEqual(row['Approved reimbursement (USD)'], '')
        self.assertEqual(row['Receipts/payment record'], '')
        self.assertEqual(row['Review status'], 'Submitted')
        self.assertEqual(row['Award'], '2026 Playmakers Cup Student-Athlete Scholarship')
        self.assertEqual(row['Award maximum (USD)'], 500)
        self.load_credentials.assert_called_with(scholarships.SHEETS_SCOPE)
        self.assertEqual(set(response.json), {'success', 'application_id', 'submitted_at', 'already_submitted'})

    def test_save_and_readiness_need_no_email_configuration_and_send_no_mail(self):
        with patch.dict(os.environ, {
            'RESEND_API_KEY': '', 'FOUNDATION_SCHOLARSHIP_FROM_EMAIL': '',
            'FOUNDATION_SCHOLARSHIP_TO_EMAIL': '',
        }), patch('requests.post') as outbound_post:
            status = self.client.get(f'{ROUTE}/status')
            response = self.client.post(ROUTE, json=valid_application())
        self.assertTrue(status.json['accepting_applications'])
        self.assertNotIn('email_configured', status.json)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
        self.assertNotIn('notification_sent', response.json)
        self.assertNotIn('confirmation_sent', response.json)
        outbound_post.assert_not_called()
        self.values.append.assert_called_once()

    def test_duplicate_submission_id_returns_success_without_duplicate_row(self):
        payload = valid_application()
        first = self.client.post(ROUTE, json=payload)
        retry = self.client.post(ROUTE, json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json['already_submitted'])
        self.assertEqual(retry.json['submitted_at'], first.json['submitted_at'])
        self.values.append.assert_called_once()

    def test_storage_failure_does_not_report_success(self):
        self.values.append.side_effect = TimeoutError('Append timed out')
        response = self.client.post(ROUTE, json=valid_application())
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json['success'])

    def test_uncertain_save_retry_finds_already_saved_row(self):
        def timed_out_append(**kwargs):
            self.rows.extend(kwargs['body']['values'])
            request = MagicMock()
            request.execute.side_effect = TimeoutError('Response lost after save')
            return request

        self.values.append.side_effect = timed_out_append
        payload = valid_application()
        self.assertEqual(self.client.post(ROUTE, json=payload).status_code, 502)
        retry = self.client.post(ROUTE, json=payload)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json['already_submitted'])
        self.values.append.assert_called_once()

    def test_uncertain_save_retry_with_edited_need_returns_conflict_without_losing_edits(self):
        def timed_out_append(**kwargs):
            self.rows.extend(kwargs['body']['values'])
            request = MagicMock()
            request.execute.side_effect = TimeoutError('Response lost after save')
            return request

        self.values.append.side_effect = timed_out_append
        payload = valid_application()
        self.assertEqual(self.client.post(ROUTE, json=payload).status_code, 502)
        original_row = list(self.rows[0])
        edited = dict(payload, financial_need='An updated explanation after the first request timed out.')
        retry = self.client.post(ROUTE, json=edited)
        self.assertEqual(retry.status_code, 409)
        self.assertFalse(retry.json['success'])
        self.assertEqual(retry.json['application_id'], payload['submission_id'])
        self.assertIn('earlier version', retry.json['message'])
        self.assertIn('latest edits have not been saved', retry.json['message'])
        self.assertEqual(self.rows[0], original_row)
        self.values.append.assert_called_once()

    def test_identical_retry_ignores_generated_age_and_staff_columns_and_trailing_blanks(self):
        payload = valid_application()
        self.assertEqual(self.client.post(ROUTE, json=payload).status_code, 200)
        self.rows[0][1] = '2026-10-15T21:00:00+00:00'
        self.rows[0][6] = 13
        self.rows[0][28] = 'Earlier policy version'
        self.rows[0][30] = 'Under review'
        self.rows[0][31] = 'Verified'
        self.rows[0] = self.rows[0][:32]
        retry = self.client.post(ROUTE, json=payload)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json['already_submitted'])
        self.values.append.assert_called_once()

    def test_closed_deadline_blocks_storage_and_reports_status(self):
        self.clock_mock.return_value = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 410)
        self.assertEqual(self.client.get(f'{ROUTE}/status').json['reason'], 'deadline_passed')
        self.values.append.assert_not_called()

    def test_validation_and_honeypot_never_call_google(self):
        response = self.client.post(ROUTE, json=valid_application(financial_need=''))
        self.assertEqual(response.status_code, 400)
        response = self.client.post(ROUTE, json={'_honey': 'spam'})
        self.assertEqual(response.status_code, 200)
        self.load_credentials.assert_not_called()

    def test_ineligible_grade_never_saves(self):
        response = self.client.post(ROUTE, json=valid_application(grade_level='College'))
        self.assertEqual(response.status_code, 400)
        self.load_credentials.assert_not_called()

    def test_public_post_is_rate_limited_before_storage(self):
        app = Flask('scholarship_rate_limit_test')
        app.config['TESTING'] = True
        limiter = Limiter(get_remote_address, app=app, storage_uri='memory://')
        scholarships.register_scholarship_routes(
            app, limiter,
            load_credentials=self.load_credentials, build_service=self.build_service,
            authorized_http=self.authorized_http,
        )
        client = app.test_client()
        responses = [client.post(ROUTE, json={}) for _ in range(6)]
        self.assertTrue(all(response.status_code == 400 for response in responses[:5]))
        self.assertEqual(responses[-1].status_code, 429)
        self.load_credentials.assert_not_called()

    def test_minimal_registration_uses_standalone_defaults_without_api_helpers(self):
        app = Flask('scholarship_defaults_test')
        app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
        limiter = Limiter(get_remote_address, app=app)
        with patch.object(scholarships, '_default_load_credentials', self.load_credentials), \
                patch.object(scholarships, '_default_build_service', self.build_service), \
                patch.object(scholarships, '_default_authorized_http', self.authorized_http):
            scholarships.register_scholarship_routes(app, limiter)
        response = app.test_client().post(ROUTE, json=valid_application())
        self.assertEqual(response.status_code, 200)
        self.values.append.assert_called_once()

    def test_legacy_global_error_handler_and_cors_do_not_break_foundation_rate_limits(self):
        app = Flask('scholarship_legacy_api_test')
        app.config['TESTING'] = True
        CORS(app, origins=['https://playmakersports.us'])

        @app.errorhandler(Exception)
        def legacy_error_handler(error):
            return {'error': 'Legacy generic handler'}, 500

        limiter = Limiter(get_remote_address, app=app, storage_uri='memory://')
        scholarships.register_scholarship_routes(
            app, limiter,
            load_credentials=self.load_credentials, build_service=self.build_service,
            authorized_http=self.authorized_http,
        )
        client = app.test_client()
        for origin in scholarships.FOUNDATION_ORIGINS:
            with self.subTest(origin=origin):
                response = client.get(f'{ROUTE}/status', headers={'Origin': origin})
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
                response = client.options(ROUTE, headers={
                    'Origin': origin, 'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type',
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
                self.assertIn('POST', response.headers['Access-Control-Allow-Methods'])
        origin = scholarships.FOUNDATION_ORIGINS[0]
        responses = [client.post(ROUTE, json={}, headers={'Origin': origin}) for _ in range(6)]
        self.assertEqual(responses[-1].status_code, 429)
        self.assertFalse(responses[-1].json['success'])
        self.assertEqual(responses[-1].headers['Access-Control-Allow-Origin'], origin)
        response = client.get(f'{ROUTE}/status', headers={'Origin': 'https://untrusted.example'})
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        self.values.append.assert_not_called()


class ScholarshipDefaultAdapterTests(unittest.TestCase):
    def test_credentials_load_json_service_account_with_sheets_scope(self):
        data = {'client_email': 'service@example.invalid', 'type': 'service_account'}
        with patch.dict(os.environ, {'GOOGLE_CREDENTIALS': scholarships.json.dumps(data)}), \
                patch('google.oauth2.service_account.Credentials.from_service_account_info') as load:
            credentials = scholarships._default_load_credentials(scholarships.SHEETS_SCOPE)
        load.assert_called_once_with(data, scopes=scholarships.SHEETS_SCOPE)
        self.assertIs(credentials, load.return_value)

    def test_missing_credentials_never_falls_back_to_a_local_secret_file(self):
        with patch.dict(os.environ, {'GOOGLE_CREDENTIALS': ''}), \
                patch('google.oauth2.service_account.Credentials.from_service_account_file') as load:
            with self.assertRaises(RuntimeError):
                scholarships._default_load_credentials(scholarships.SHEETS_SCOPE)
        load.assert_not_called()

    def test_build_service_and_authorized_http_use_existing_google_dependencies(self):
        with patch('googleapiclient.discovery.build') as build:
            service = scholarships._default_build_service('sheets', 'v4', credentials='test', cache_discovery=False)
        build.assert_called_once_with('sheets', 'v4', credentials='test', cache_discovery=False)
        self.assertIs(service, build.return_value)
        with patch('google_auth_httplib2.AuthorizedHttp') as authorized, patch('httplib2.Http') as http:
            transport = scholarships._default_authorized_http('test-credentials')
        http.assert_called_once_with(timeout=120)
        authorized.assert_called_once_with('test-credentials', http=http.return_value)
        self.assertIs(transport, authorized.return_value)

class ScholarshipAPIIntegrationTests(unittest.TestCase):
    def test_real_api_has_public_routes_and_foundation_only_cors(self):
        from app import create_app

        with patch.dict(os.environ, {'FOUNDATION_SCHOLARSHIP_SHEET_ID': ''}):
            client = create_app({'TESTING': True, 'RATELIMIT_ENABLED': False}).test_client()
            response = client.get(f'{ROUTE}/status', headers={'Origin': 'https://playmakersportsfoundation.org'})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json['accepting_applications'])
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://playmakersportsfoundation.org')
            response = client.options(ROUTE, headers={
                'Origin': 'https://www.playmakersportsfoundation.org',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type',
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn('POST', response.headers['Access-Control-Allow-Methods'])
            response = client.get(f'{ROUTE}/status', headers={'Origin': 'https://untrusted.example'})
            self.assertNotIn('Access-Control-Allow-Origin', response.headers)


if __name__ == '__main__':
    unittest.main()
