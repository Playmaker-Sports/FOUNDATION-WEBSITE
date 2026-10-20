# Foundation registration setup

**Legacy clinic-registration reference, not the scholarship deployment guide.** The separate Foundation API in `backend/` currently supports scholarship applications only. It does not deploy the clinic-registration route. Use `SCHOLARSHIP_SETUP.md` for the new Foundation service; do not configure the company API or reuse company Google/email secrets to launch the scholarship application.

The existing clinic registration page is a first-party form with its own legacy endpoint. It does not submit to or depend on Google Forms. Clinic registration needs a separate Foundation-only migration and verification before a future launch; these historical field definitions are retained for that work.

## 1. Create the private spreadsheet

1. In the Foundation Google Drive, create a spreadsheet named **Foundation Clinic Registrations**.
2. Rename its first tab to **Registrations**.
3. Paste these headings into row 1, columns A through L:

   `Submitted at (UTC) | Child first name | Child last name | Date of birth | Gender | Guardian first name | Guardian last name | Guardian email | Home address | Phone | Consent | Source`

4. Copy the spreadsheet ID from its URL. It is the text between `/d/` and `/edit`.
5. Use a Foundation-controlled service account's `client_email` value, not the company's account.
6. Share the spreadsheet with that service-account email as an **Editor**. Do not make the sheet public.
7. In the Google Cloud project used by that service account, confirm the **Google Sheets API** is enabled.

## 2. Configure the API on Render

For a future Foundation-only registration service, once its registration route has been implemented and tested, configure:

| Environment variable | Value |
| --- | --- |
| `FOUNDATION_REGISTRATION_SHEET_ID` | The spreadsheet ID copied above |
| `FOUNDATION_REGISTRATION_SHEET_RANGE` | `Registrations!A:L` |
| `FOUNDATION_REGISTRATION_TO_EMAIL` | The staff inbox that should receive alerts, such as `info@playmakersportsfoundation.org` |
| `FOUNDATION_REGISTRATION_FROM_EMAIL` | An explicitly configured, verified Foundation-controlled sender |

Use Foundation-owned `GOOGLE_CREDENTIALS` and `RESEND_API_KEY` secrets on that Foundation service only. Never copy company credentials, and never commit a credential or API key to GitHub. These variables do not add a registration route to the scholarship-only API.

Deploy the API changes before publishing the Foundation website changes.

## 3. Verify before announcing registration

1. Open the published Foundation registration page.
2. Submit one clearly labeled internal test registration.
3. Confirm one row appears in the private Sheet.
4. Confirm the Foundation inbox receives a Resend notification.
5. Delete the test row from the Sheet.

The email is intentionally a notification rather than a full copy of the response. Date of birth and home address remain only in the access-controlled spreadsheet.
