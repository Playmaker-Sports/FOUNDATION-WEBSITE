# Foundation scholarship API

This standalone service belongs in the Foundation's Render workspace. It serves
only scholarship intake and a health check. It does not import or run the
tournament company's API, Ops app, scrapers, database, or background jobs.

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

Configure these on this service only. Never copy the company's service secrets,
load a company `.env`, or commit credentials. This backend reads Google credentials
only from its own environment; it never falls back to a local credentials file.

| Variable | Required value |
| --- | --- |
| `GOOGLE_CREDENTIALS` | Foundation-owned Google service-account JSON, stored as a Render secret |
| `FOUNDATION_SCHOLARSHIP_SHEET_ID` | ID of the Foundation's restricted, native Google Sheet |
| `FOUNDATION_SCHOLARSHIP_SHEET_RANGE` | `Applications!A:AJ` (the default) |
| `RESEND_API_KEY` | Foundation-authorized Resend API key, stored as a Render secret |
| `FOUNDATION_SCHOLARSHIP_FROM_EMAIL` | Explicit Foundation sender verified in Resend; there is no fallback sender |
| `FOUNDATION_SCHOLARSHIP_TO_EMAIL` | Authorized Foundation staff inbox; defaults to `info@playmakersportsfoundation.org` |

Share the Sheet with the Foundation service account as **Editor** and enable the
Google Sheets API in its Google Cloud project. Keep general sharing Restricted.
Import the blank workbook at `../templates/2026-playmakers-cup-applications.xlsx`
as a native Google Sheet and preserve its exact 36 headers in `Applications!A1:AJ1`.
Real applications, selection notes, receipts, and payments stay in restricted
Foundation storage, never in this repository.

## Endpoints and readiness

- GET `/health`: cheap application liveness. It never reads Google credentials,
  opens the Sheet, sends email, or establishes that submissions are ready.
- GET `/api/foundation/scholarship-applications/status`: checks the deadline,
  explicit email configuration, private Sheet accessibility, and exact headers.
  `email_configured` checks key presence and address format only; it does **not**
  verify a Resend key, sender-domain verification, or email delivery. A successful
  Sheet read does not establish Editor/write permission.
- POST `/api/foundation/scholarship-applications`: validated JSON intake. Answers
  are appended using `RAW` input. Identical retries reuse the saved reference;
  altered answers under an already-saved UUID receive HTTP 409. Missing required
  email configuration returns HTTP 503 before opening or writing the Sheet.

The public website must use this Foundation service's URL, never the company API
URL. Keep the existing route path and allow only the Foundation's two website
origins. The website allows 90 seconds for availability and submission requests,
shows a startup notice after eight seconds, and preserves the submission reference
when retrying. Free-service cold starts can still delay access. An external
liveness ping can use `/health`, but does not prove Google/email readiness or
guarantee availability.

Submissions are saved before independently attempting the staff alert and the
guardian/applicant thank-you. Email failure never discards a saved application.
The response reports independent `notification_sent` and `confirmation_sent`
flags; provider acceptance does not guarantee inbox placement. Normal duplicate
retries do not send duplicate emails. There is no durable email delivery queue;
a lost response after a Sheet write can leave a saved application without email.
Use the private Sheet as the submission record and review it during the period.

Before announcing intake, verify `accepting_applications: true`, then separately
verify one authorized internal test saves exactly one row and sends both emails.
Use invented applicant details and an authorized staff email, not a real child.
Do not claim a health check, configuration flag, or automated test proved the live
Google write/email flow.

## Offline checks

The development tests require `pytest==8.4.2` in addition to production dependencies.
From this directory run `python -B -m pytest`. Tests mock Google and Resend, do not
load `.env` files, and do not write to production services. The tests cover the
original application contract and the standalone app's liveness, route isolation,
CORS, request cap, proxy-aware rate limits, and generic non-PII error handling.
