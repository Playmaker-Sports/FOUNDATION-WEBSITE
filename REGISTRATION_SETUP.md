# Foundation registration setup

The Foundation registration page is a first-party form. It does not submit to or depend on Google Forms. The page sends registration data to the Playmaker API, which appends a row to a private Google Sheet and sends a staff notification through Resend.

## 1. Create the private spreadsheet

1. In the Foundation Google Drive, create a spreadsheet named **Foundation Clinic Registrations**.
2. Rename its first tab to **Registrations**.
3. Paste these headings into row 1, columns A through L:

   `Submitted at (UTC) | Child first name | Child last name | Date of birth | Gender | Guardian first name | Guardian last name | Guardian email | Home address | Phone | Consent | Source`

4. Copy the spreadsheet ID from its URL. It is the text between `/d/` and `/edit`.
5. In the existing Render `GOOGLE_CREDENTIALS` environment variable, find the service account's `client_email` value.
6. Share the spreadsheet with that service-account email as an **Editor**. Do not make the sheet public.
7. In the Google Cloud project used by that service account, confirm the **Google Sheets API** is enabled.

## 2. Configure the API on Render

Open the `playmakersportsapp-api` service in Render and add:

| Environment variable | Value |
| --- | --- |
| `FOUNDATION_REGISTRATION_SHEET_ID` | The spreadsheet ID copied above |
| `FOUNDATION_REGISTRATION_SHEET_RANGE` | `Registrations!A:L` |
| `FOUNDATION_REGISTRATION_TO_EMAIL` | The staff inbox that should receive alerts, such as `info@playmakersportsfoundation.org` |
| `FOUNDATION_REGISTRATION_FROM_EMAIL` | `Playmaker Sports Foundation <registration@send.playmakersports.us>` |

The API reuses the existing `GOOGLE_CREDENTIALS` and `RESEND_API_KEY` values used by Playmaker services. If either is absent, add it securely in Render; never commit the credential or API key to GitHub.

Deploy the API changes before publishing the Foundation website changes.

## 3. Verify before announcing registration

1. Open the published Foundation registration page.
2. Submit one clearly labeled internal test registration.
3. Confirm one row appears in the private Sheet.
4. Confirm the Foundation inbox receives a Resend notification.
5. Delete the test row from the Sheet.

The email is intentionally a notification rather than a full copy of the response. Date of birth and home address remain only in the access-controlled spreadsheet.
