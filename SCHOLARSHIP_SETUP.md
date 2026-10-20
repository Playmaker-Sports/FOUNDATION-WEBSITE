# 2026 Playmakers Cup scholarship: setup and administration

The first-party application is `scholarship.html`, linked from Home, Programs, and every main navigation/footer. It does not use Google Forms. Its standalone Foundation API lives in this repository's `backend/` folder and saves to a private Foundation Google Sheet, with a minimal staff notification and a separate applicant thank-you through Resend.

## Current release status

Code and a blank 36-column workbook template are prepared. This document is not evidence that a live Sheet, credentials, email, or deployment has been configured. The website stays on GitHub Pages from `Playmaker-Sports/FOUNDATION-WEBSITE` `main`, behind Cloudflare. Deploy the API as a separate free Web Service in the **Playmaker Sports Foundation** Render workspace. Do not use the company API, company environment groups, or company credentials.

The shipped scholarship form has a blank `action` and `data-api-pending="true"`. It makes no intake requests until the new Foundation deployment is verified and explicitly connected. A local `file:` preview displays the form but cannot submit. Creating a Render workspace or getting a healthy `/health` response does not mean applications are open.

## Agreed award rules

- One recipient, a need-based soccer scholarship of up to $500.
- Applicants must currently be in grades 6–12 and be registered players participating with a team in the 2026 Playmakers Cup. Staff verify participation against tournament registration records. There is no separate age cutoff; applicants under 18 require guardian acknowledgment.
- Application deadline: November 20, 2026, at 11:59 p.m. America/Los_Angeles. The API rejects new submissions starting November 21 at midnight Pacific.
- Selection is based on demonstrated financial need and the application. Receipts substantiate expenses, not financial need.
- Only the selected recipient supplies paid club soccer fee or soccer equipment receipts, before reimbursement. Pay the smaller of $500 or total eligible documented expenses; a guardian handles payment for a minor.
- Publicity contact permission is optional and does not affect selection. Obtain separate permission before publishing identifying information or photos; obtain guardian permission for minors.
- The application makes no promise that an award is tax-free. These rules do not establish a recipient's tax treatment or replace accounting/reporting review.

## 1. One-time private Google Sheet setup

1. Import the prepared `templates/2026-playmakers-cup-applications.xlsx` into the Foundation's Google Drive as a **native Google Sheets spreadsheet**, not just an uploaded Excel file. It has `Applications` and `Review guide` tabs and no applicant data. Keep this repository template blank; real applications and receipts belong only in restricted Foundation storage, never GitHub.
2. Keep the `Applications` tab name and its exact 36 headers in A1:AJ1. The backend validates them. Do not reorder/delete columns. Staff may filter the Sheet, but should avoid sorting or editing while an application is being saved.
3. Restrict general access to **Restricted**. Give access only to authorized Foundation reviewers and the website's Google service account. Do not enable anyone-with-the-link access or publish the spreadsheet to the web.
4. Create or use a Google Cloud project and service account controlled by the Foundation. From that account's `GOOGLE_CREDENTIALS` JSON, use only the `client_email` value to share this Sheet as **Editor**. Store the complete JSON only as a secret on the new Foundation Render service. Do not copy the company's credentials, and never paste a private key into chat, a spreadsheet, the website, or GitHub.
5. Confirm the Google Sheets API is enabled in that service account's Google Cloud project.
6. Copy the spreadsheet ID from the native Sheet URL: the text between `/d/` and `/edit`.

The website uses this server-side service account, **not** a person's ChatGPT/Drive connector session. Google access tokens refresh automatically. Once configured, no recurring sign-in is required for normal submissions. Revoking Sheet access, disabling the account/API, or rotating/removing its key requires updating the setup. The ChatGPT Drive connection used to create/manage the document is separate and may occasionally need reauthorization.

## 2. One-time API configuration on Render

Choose **Web Services > New Web Service**, select `Playmaker-Sports/FOUNDATION-WEBSITE`, and use these settings in the Foundation workspace:

| Setting | Value |
| --- | --- |
| Name | `playmaker-foundation-api` (or another available Foundation-only name) |
| Language / runtime | Python 3 |
| Branch | `main` |
| Region | Oregon |
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn -c gunicorn.conf.py app:app` |
| Instance type | Free |
| Health check path | `/health` |

No database, disk, worker, or paid add-on is needed. Use the Python version pinned in `backend/.python-version`. A free workspace plan and the service's **Free** instance type are separate choices; verify both before creating the service.

Configure these variables only on the new Foundation service:

| Variable | Value |
| --- | --- |
| `FOUNDATION_SCHOLARSHIP_SHEET_ID` | ID of the private native Google Sheet |
| `FOUNDATION_SCHOLARSHIP_SHEET_RANGE` | `Applications!A:AJ` |
| `FOUNDATION_SCHOLARSHIP_TO_EMAIL` | Authorized staff inbox; defaults to `info@playmakersportsfoundation.org` |
| `FOUNDATION_SCHOLARSHIP_FROM_EMAIL` | Explicit, verified Foundation-controlled Resend sender; there is no company-domain fallback |
| `GOOGLE_CREDENTIALS` | Foundation-controlled Google service-account JSON, stored only as a server secret |
| `RESEND_API_KEY` | Foundation-controlled Resend key, stored only as a server secret |

Use Foundation-controlled Google and email access, not the company's Google account, Resend key, sender, or shared environment groups. Verify the Foundation sending domain in Resend and confirm the Foundation inbox can receive notifications. Do not put secrets, real applications, or receipts in this public repository. `.gitignore` protects common local secret filenames, and GitHub Pages excludes `backend/`; neither is permission to commit sensitive files under a different name.

The standalone `backend/app.py` does not import or start the company API. Keep Gunicorn at **one worker, four threads**, and one service instance. Duplicate protection uses a process lock plus a persistent Sheet lookup; do not increase the worker count or add replicas without replacing it with a shared transactional idempotency store.

### Startup delays and optional uptime checks

Free Render services can sleep or restart. The client allows up to 90 seconds for availability and submission requests and explains an availability wait after eight seconds. Failed/uncertain submissions retain their reference for safe manual retry; do not add automatic POST retries or a false success screen.

After the actual Foundation service URL is known, any separately configured uptime monitor should request its cheap `/health` endpoint, not the scholarship status route (which reads the private Sheet). Pings do not guarantee uptime, remove usage limits, or prove that Sheets/email works. No monitor is created merely by publishing this code. Render's current free-service limits are documented at https://render.com/docs/free.

## 3. Release verification

1. Open the new service's actual URL plus `/health`, then `/api/foundation/scholarship-applications/status`. Before the deadline, status must return `accepting_applications: true`. The status check verifies the Sheet/header setup and email configuration presence, not write access or actual email delivery.
2. Keep the public form pending while testing the new endpoint using a local/private QA configuration and an authorized staff email. Submit one clearly labeled internal test. Do not use real child information or redirect test submissions to the company API.
3. Confirm exactly one application row appears with a reference matching the success screen. Confirm the Foundation inbox receives a Resend alert linking to the private Sheet; the alert deliberately omits essays, DOB, and contact details. Confirm a separate thank-you email reaches the guardian for a minor, or the applicant for someone 18 or older. That email includes the reference and next steps, not private application answers.
4. Test a guardian-required applicant and an adult applicant. Confirm missing consents/expenses are blocked and optional publicity remains unchecked.
5. Check a retry using the same submission reference does not create a second row. If the first save succeeded but edited answers are retried, HTTP 409 explains the earlier version was saved and corrections must be requested from staff.
6. Remove only the clearly identified internal test row after verification through the normal authorized cleanup process. Do not delete real applications.
7. Set the `scholarship.html` form's `action` to the **verified Foundation service URL** plus `/api/foundation/scholarship-applications` and set `data-api-pending="false"`. Publish that frontend change only after the previous checks pass. Do not guess an available Render hostname or leave the form pointed at the company API.
8. Confirm Home/Programs promotions, all six main navigation links, and the Donate equipment-drive section in desktop and mobile layouts, and verify the live page is now talking only to the new Foundation API.

Saving to Sheets happens before email. Staff notification and applicant thank-you are attempted independently, so failure of one does not suppress the other. An email delivery failure does not discard a saved application. The success screen distinguishes a sent thank-you from a failed send; it never asks a family to resubmit just to get an email. Ordinary retries do not send duplicate emails. If the response is lost after a successful Sheet write, a retry returns the existing reference; in that rare case one or both emails may be absent. Email delivery retries are not durably queued. Treat the private Sheet as the record of submissions and check it during the application period.

## 4. Staff selection and reimbursement checklist

1. Use the private review columns: **Review status**, **Cup participation verified**, **Financial need reviewed**, **Selection rationale**, **Approved reimbursement (USD)**, and **Receipts/payment record**. Preserve the original submitted answers and application ID.
2. Foundation reviewers assess the financial need described and verify tournament participation. Record a short, factual selection reason tied to the scholarship's charitable purpose. Do not require tax returns, SSNs, bank statements, or receipt uploads from all applicants.
3. Have Foundation decision-makers approve the recipient independently of the tournament business's sales or promotion. Disclose and manage conflicts; do not favor insiders or require an additional tournament-business purchase to receive a scholarship. Keep the tournament-eligibility restriction in the policy/accounting review rather than assuming that restriction is automatically permissible or automatically prohibited.
4. Contact the selected adult or guardian privately. Collect only receipts needed to show paid, eligible soccer expenses. Ask them to redact card numbers and other unrelated sensitive information. Store receipts in a separate restricted Foundation Drive folder, not in a public upload folder.
5. Check the expense belongs to the recipient, was actually paid, is eligible, and is not being reimbursed twice. Record receipt dates, eligible total, approval, payee, payment date/reference, and a restricted receipt-folder link in **Receipts/payment record**. Never put bank account details in the application Sheet.
6. Reimburse no more than documented eligible costs and no more than $500. If the documents do not support the full award, request eligible receipts or pay only the supported amount. Record the Foundation approver and payment through the normal accounting process.
7. Follow the Foundation accountant's instructions for recipient/payment documentation and any required reporting; do not tell families soccer receipts automatically make the payment tax-free. Keep access and retention consistent with the Foundation's records policy.
8. Do not publish a recipient's name, photo, or story based solely on the application's optional contact checkbox. Obtain separate, specific permission first.

## Technical reference

- GET `/api/foundation/scholarship-applications/status`: readiness and deadline. Reasons include `not_configured`, `temporarily_unavailable`, and `deadline_passed`.
- POST `/api/foundation/scholarship-applications`: validated JSON intake with UUIDv4 `submission_id` and grade restricted to `6th grade` through `12th grade`; returns a saved application reference only after storage succeeds. Success includes independent `notification_sent` and `confirmation_sent` flags; accepted email delivery does not guarantee placement in the inbox.
- Responses: 400 invalid application, 409 earlier application with changed retry payload, 410 deadline passed, 429 rate limit, 502 uncertain/failed storage, 503 missing configuration.
- Client session storage holds only the application reference, not an applicant's essays or personal details. Reloading an unsubmitted form does not restore a draft.
- Backend source of truth for headers: `backend/foundation_scholarships.py`, `SHEET_COLUMNS`. User-provided values are appended with `valueInputOption='RAW'` to prevent formula execution.
- Automated checks use mocked Google/Resend services. They do not establish that production credentials, private Sheet access, or live email work.
