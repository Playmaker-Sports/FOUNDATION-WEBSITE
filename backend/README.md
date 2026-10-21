# Foundation scholarship API

This standalone service belongs in the Foundation's Render workspace. It serves
only scholarship intake and a health check. It does not import or run the
tournament company's API, Ops app, scrapers, database, or background jobs.

The public intake is moving to the Foundation-owned native Google Form.
**This superseded custom API is disabled by default**, even if old Sheet
credentials remain configured. Disabled status requests return
`accepting_applications: false` and `reason: intake_retired`; POST returns HTTP 410
without parsing application answers or calling Google. `/health` remains live.

The preserved fallback saves applications only. It sends no staff notifications
or applicant emails and requires no email-provider credentials. It does not
create a Google Form or prove that Google notifications are configured. Keep the
custom frontend disabled while the website uses the native Google Form.
The award remains need-based; a selection date has not been set.

## Render settings

- Repository: `Playmaker-Sports/FOUNDATION-WEBSITE`, branch `main`.
- Service type: Python Web Service; instance plan: Free.
- Root directory: `backend`.
- Python: `3.13.4`, pinned in `.python-version`.
- Build command: `pip install -r requirements.txt`.
- Start command: `gunicorn -c gunicorn.conf.py app:app`.
- Health check: `/health`.
- One instance, one Gunicorn worker, four threads, 120-second worker timeout.
- No disk or database is needed. Do not add replicas or workers: duplicate
  protection uses one process lock and persistent submission IDs in the Sheet.

Render supplies `PORT`. The service trusts Render's final proxy hop for client IP
and HTTPS only. Rate limits use memory inside the single worker and reset when
it restarts. POST is limited to five attempts per minute per client IP; request
bodies are capped at 128 KiB to allow the full response limits in UTF-8. Request
access logging is disabled.

## Foundation-owned environment values

These values are needed only for an intentionally approved API rollback; do not
set the opt-in for the native Google Forms launch. Configure them on this service
only. Never copy the company's service secrets,
load a company `.env`, or commit credentials. This backend reads Google credentials
only from its own environment; it never falls back to a local credentials file.

| Variable | Required value |
| --- | --- |
| `FOUNDATION_SCHOLARSHIP_API_ENABLED` | Leave unset or `false` for native Forms. Only the exact value `true` deliberately enables the legacy API fallback. |
| `GOOGLE_CREDENTIALS` | Foundation-owned Google service-account JSON, stored as a Render secret |
| `FOUNDATION_SCHOLARSHIP_SHEET_ID` | ID of the Foundation's restricted, native Google Sheet |
| `FOUNDATION_SCHOLARSHIP_SHEET_RANGE` | `Applications!A:AJ` (the default) |

Share the Sheet with the Foundation service account as **Editor** and enable the
Google Sheets API in its Google Cloud project. Keep general sharing Restricted.
Import the blank workbook at `../templates/2026-playmakers-cup-applications.xlsx`
as a native Google Sheet and preserve its exact 36 headers in `Applications!A1:AJ1`.
Never point this API at the native Form's **Form Responses 1** tab, whose schema
is different. Enabling API fallback does not configure native response alerts.
Real applications, selection notes, receipts, and payments stay in restricted
Foundation storage, never in this repository.

## Endpoints and readiness

- GET `/health`: cheap application liveness. It never reads Google credentials,
  opens the Sheet, sends email, or establishes that submissions are ready.
- GET `/api/foundation/scholarship-applications/status`: returns retired without
  Google calls unless the explicit rollback opt-in is set. If enabled, checks the deadline,
  private Sheet accessibility, and exact headers. A successful Sheet read does
  not establish Editor/write permission or Google notification delivery. This
  status does not depend on email keys, sender addresses, or notification rules.
- POST `/api/foundation/scholarship-applications`: HTTP 410 while retired. Only
  with explicit opt-in, validated JSON intake. Answers
  are appended using `RAW` input. Identical retries reuse the saved reference;
  altered answers under an already-saved UUID receive HTTP 409. Missing Sheet or
  Google credential configuration returns HTTP 503 without claiming success.

The native Form does not use this service. A deliberately restored custom
frontend must use this Foundation service's URL, never the company API URL.
The fallback retains its existing route path and allows only the Foundation's
two website origins. Free-service cold starts can still delay API access.

The repository's independent `.github/workflows/foundation-keepalive.yml` has no
automatic schedule or push trigger. It retains manual dispatch only for an
optional rollback diagnostic of
`https://foundation-website-7o9d.onrender.com/health`. A manual run needs no
credentials and makes no Google or email requests. The retired API does not
need to stay warm; native Google Forms does not depend on Render. A health run
does not establish Google/Form/notification readiness or guaranteed availability.

Successful saves return only `success`, `application_id`, `submitted_at`, and
`already_submitted`. The legacy `notification_sent`, `confirmation_sent`, and
`email_configured` fields have been removed. No automatic email is sent. The
frontend can show an on-site thank-you only after a confirmed save. Use the
private Sheet as the record of submissions and review it during the period.

Native Google staff notifications must be configured and verified separately;
an API append is not a Google Form submission. Do not assume a Sheets edit rule
or an Apps Script edit trigger will email staff for these API writes. This
backend neither installs nor verifies those rules.

Before enabling any selected public intake path, verify an authorized internal
test saves exactly one application and the intended Google-native staff alert
actually arrives. Use invented applicant details, not a real child. A health
check, configuration flag, or automated test does not establish that live flow.

## Offline checks

The development tests require `pytest==8.4.2` in addition to production dependencies.
From this directory run `python -B -m pytest`. Tests mock Google, do not
load `.env` files, and do not write to production services. The tests cover the
original application contract under explicit opt-in, default-off retirement
without Google calls, and the standalone app's liveness, route isolation,
CORS, request cap, proxy-aware rate limits, and generic non-PII error handling.
