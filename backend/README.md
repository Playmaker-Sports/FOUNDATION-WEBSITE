# Foundation scholarship API

This standalone service belongs in the Foundation's Render workspace. It serves
only scholarship intake and a health check. It does not import or run the
tournament company's API, Ops app, scrapers, database, or background jobs.

The branded website form can use this service's signed bridge to a
Foundation-owned Google Apps Script, which saves a native Google Form response.
**Intake is disabled by default**, even if Google credentials or bridge settings
remain configured. Disabled status requests return
`accepting_applications: false` and `reason: intake_retired`; POST returns HTTP 410
without parsing application answers or calling Google. `/health` remains live.

Do not activate the bridge until deployment/connection has been authorized and
the complete branded form flow is verified. The authorized October 20 scripted
test confirmed a saved native Form/linked Sheet response and Google's native
owner notification. The owner notification must remain enabled in Google Forms;
the API does not send it or certify future delivery. No applicant email, Resend,
Gmail-sending API, or MailApp substitute is used.
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
- No disk or database is needed. Keep one worker: the optional Sheet fallback
  uses a process lock, and the bridge status cache lives in that process.
  Native Form retry protection must be implemented durably by Apps Script.

Render supplies `PORT`. The service trusts Render's final proxy hop for client IP
and HTTPS only. Rate limits use memory inside the single worker and reset when
it restarts. POST is limited to five attempts per minute per client IP; request
bodies are capped at 128 KiB to allow the full response limits in UTF-8. Request
access logging is disabled.

## Foundation-owned environment values

Configure these on the Foundation service only, after deployment approval.
Never copy company secrets, load a company `.env`, put a signing secret in the
browser, or commit credentials. There is no automatic storage fallback.

| Variable | Required value |
| --- | --- |
| `FOUNDATION_SCHOLARSHIP_API_ENABLED` | Unset/`false` disables intake. Only exact `true` enables the explicitly selected adapter. |
| `FOUNDATION_SCHOLARSHIP_STORE` | Exact `google_form` for the signed bridge. Unset or unknown values fail closed. |
| `FOUNDATION_SCHOLARSHIP_BRIDGE_URL` | Verified deployment's `https://script.google.com/macros/s/DEPLOYMENT_ID/exec` URL; no query, fragment, alternate host, or development URL |
| `FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET` | A random secret of 32–1024 UTF-8 bytes, set to the identical value in the Foundation Apps Script's private Script Property with this same name |

Bridge mode does not use `GOOGLE_CREDENTIALS`, a service-account key, or Sheets
API access. The Foundation-owned Apps Script executes as its owner and holds
its own private Form/Sheet identifiers. Do not commit actual deployment/edit
identifiers, private Sheet URLs, applications, receipts, or signing keys here.

## Signed Apps Script protocol

The API POSTs JSON to the configured bridge URL. The envelope contains:

```
version: 1
action: "status" or "submit"
timestamp: integer Unix seconds
payload: a JSON string
signature: lowercase hexadecimal HMAC-SHA256
```

The envelope is sent as UTF-8 JSON bytes rather than ASCII-escaped JSON, keeping
maximum-length Unicode responses inside the receiver's request-size cap.
`payload` is `{}` for status, or the validated application object for submit,
including its canonical `submission_id`. Python serializes that string with
`ensure_ascii=False`, `sort_keys=True`, and `separators=(',', ':')`. Sign the exact
UTF-8 bytes of `version + "\n" + action + "\n" + timestamp + "\n" + payload`
using the shared secret. The secret itself is never sent. Apps Script must
verify the signature and timestamp freshness before any private read/write;
it must independently validate, enforce the deadline, and durably deduplicate
submission IDs, rejecting changed answers under an already-saved ID. Do not
rely on an Apps Script form-submit trigger: scripted submissions do not run it.

A status reply must have `success: true` and a boolean `accepting_applications`.
If false, `reason` must be `deadline_passed`, `not_configured`, or
`temporarily_unavailable`. Both status successes and remote failures are cached
for 60 seconds per bridge URL/signing-key identity to avoid quota amplification.
Secret or URL rotation invalidates that cache.

A submission success must contain `success: true`, `accepted: true`, an
`application_id` exactly matching the submitted UUID, an aware ISO `submitted_at`,
boolean `already_submitted`, and nonempty `response_id`. The API returns only
the first public application reference, timestamp, and retry flag, stripping
Google's private response ID. Invalid or ambiguous replies never produce a
successful save message.

An error reply has `success: false` and a safe `reason`: `conflict` maps to 409;
`closed`/`deadline_passed` to 410; `unavailable`/`not_configured`/
`temporarily_unavailable` to 503; unknown or malformed errors to 502. Remote
messages are never echoed to applicants or logs. No automatic POST retry occurs.

HTTP calls use connect/read timeouts of 5/25 seconds. The only accepted
ContentService redirect is 302/303 followed by a GET to HTTPS
`script.googleusercontent.com`; the signed POST body is never forwarded.
Other hosts, redirect chains, non-JSON/duplicate-key replies, and replies over
16 KiB fail closed. The API never silently switches to direct Sheets storage.

## Optional direct-Sheet rollback only

An intentional, separately approved rollback may select
`FOUNDATION_SCHOLARSHIP_STORE=sheet`. Only this mode uses
`GOOGLE_CREDENTIALS` (Foundation service-account JSON),
`FOUNDATION_SCHOLARSHIP_SHEET_ID`, and optional
`FOUNDATION_SCHOLARSHIP_SHEET_RANGE` (default `Applications!A:AJ`). Credentials
are read from this service's environment only, never a local credentials file.
Enable Sheets API, share the restricted Sheet as Editor with the service
account, and preserve the blank template's exact 36 headers. Never point this
adapter at **Form Responses 1**: the native response schema is different.
This mode has no native Form notifications and is not an email substitute.

## Endpoints and readiness

- GET `/health`: cheap application liveness. It never reads Google credentials,
  opens the Sheet, sends email, or establishes that submissions are ready.
- GET `/api/foundation/scholarship-applications/status`: returns retired without
  Google calls unless the explicit opt-in is set. If enabled, checks the Pacific
  deadline and selected adapter: cached signed Form status, or private Sheet
  accessibility/exact headers for explicit Sheet mode. Limited to 60/minute/IP.
  Readiness never certifies an actual save or owner-notification delivery.
- POST `/api/foundation/scholarship-applications`: HTTP 410 while retired. Only
  with explicit opt-in and adapter configuration, validated JSON intake. Missing
  configuration is 503. Honeypots return a non-success 400 without Google calls.
  The signed Form bridge must verify a saved response before returning success;
  the optional Sheet adapter appends with `RAW` input and persistent UUID lookup.

The branded custom frontend must use this Foundation service's URL, never the
company API URL. The existing route path allows only the Foundation's
two website origins. Free-service cold starts can still delay API access.

The repository's independent `.github/workflows/foundation-keepalive.yml` has no
automatic schedule or push trigger. It retains manual dispatch only for an
optional rollback diagnostic of
`https://foundation-website-7o9d.onrender.com/health`. A manual run needs no
credentials and makes no Google or email requests. The branded bridge path
depends on this service; direct Google Forms does not. A health run does not
establish Google/Form/notification readiness or guaranteed availability.

Successful saves return only `success`, `application_id`, `submitted_at`, and
`already_submitted`. The legacy `notification_sent`, `confirmation_sent`, and
`email_configured` fields have been removed. This API sends no email; Google
Forms handles the configured owner alert. No applicant emails are sent. The
frontend can show an on-site thank-you only after a confirmed save. Use the
private Sheet as the record of submissions and review it during the period.

Native Google staff notifications must be configured and verified separately.
Scripted native Form submission and its owner alert succeeded in the authorized
test, but an ordinary Sheet API append is not a Form submission. Do not assume
Sheet edit rules or Apps Script edit triggers email staff for direct API writes.

Before enabling any selected public intake path, verify an authorized internal
test saves exactly one application and the intended Google-native staff alert
actually arrives. Use invented applicant details, not a real child. A health
check, configuration flag, or automated test does not establish that live flow.

## Offline checks

The development tests require `pytest==8.4.2` in addition to production dependencies.
From this directory run `python -B -m pytest`. Tests mock Google, do not
load `.env` files, and do not write to production services. The tests cover the
original application contract under explicit Sheet opt-in, default-off behavior,
signed protocol and status cache, strict reply checks, safe redirects, no silent
fallback, liveness, route isolation, CORS, request cap, proxy-aware rate limits,
and generic non-PII error handling. Tests do not deploy the bridge or establish
that production credentials and notifications work.
