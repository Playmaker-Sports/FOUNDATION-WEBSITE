# 2026 Playmakers Cup scholarship: setup and administration

## Approved target and current status

The approved intake is a **native Google Form owned by theplaymakersportsfoundation@gmail.com**, linked to a private Google Sheet in that account's Drive. Applicants must be able to respond without signing in. Staff will use Google's native new-response notifications. Do not send automatic applicant emails or response copies, or configure Resend, Gmail API sending, or a MailApp substitute.

The native Google Form was **created successfully on October 20, 2026**, with 24 questions and seven layout items. It is linked to the existing private Foundation spreadsheet, where Forms created **Form Responses 1** with a timestamp column and 24 answer columns. Drive metadata confirmed Foundation ownership of both files. The linked response Sheet remains owner-only; publishing a responder link does not make the response Sheet public.

The owner enabled Google's new-response email notifications in the Form UI. Applicant response receipts, the one-response limit, and respondent results summaries are off, and the confirmation message is set. Automatic applicant emails are off in settings; their non-delivery was not separately tested. Native Form preview checks with fictional details verified both paths: under-18 applicants must provide guardian name, email, and acknowledgment (their own email is optional), then reach the Cup section without the adult section; adults must provide their own email, then reach the Cup section without the guardian section.

The user authorized publishing, connecting the website, pushing changes, and one fictional end-to-end submission. **The Form is published for Anyone with the link**, and its native closing deadline was saved and verified as **November 20, 2026, at 11:59 p.m. PST**. One authorized fictional minor application was submitted while signed out on **October 20, 2026, at 5:35:57 p.m. Pacific**. Google displayed the successful confirmation, and row 2 of the native linked response tab matched all 24 question fields, including the correctly blank optional publicity, minor applicant-email, and skipped adult-email fields. The response Sheet's owner-only access was verified again. The Foundation owner's Gmail received Google's native new-response notification at **5:36 p.m. Pacific**. Both age routes were preview-tested; only the minor route has an actual signed-out submission.

The clearly labeled **TEST ONLY — DO NOT REVIEW** response is intentionally retained and must be excluded from scholarship selection. No test-response deletion was authorized. This release connects the website through Google's supported native iframe and a direct responder-link fallback. Verify the deployed page after publishing each release; the eventual deadline closed-state behavior remains untested.

The website remains on GitHub Pages from Playmaker-Sports/FOUNDATION-WEBSITE main, behind Cloudflare. This release replaces the custom form with the native Form embed, not an API connection, and removes Foundation email sending. The backend is a **disabled-by-default, storage-only fallback**, not the native Form or a source of Google response notifications. A local or GitHub update alone does not establish that the deployed website or backend has been updated; verify the public page and deployed API status separately.

Do not put private Sheet IDs/URLs, Form edit URLs, credentials, applications, or receipts in this public repository. Only a verified public **responder** link or embed URL belongs on the website. Keep Foundation ownership and access separate from the tournament company.

## Agreed award rules

- One recipient, a need-based soccer scholarship of up to $500.
- Applicants must currently be in grades 6–12 and be registered players participating with a team in the 2026 Playmakers Cup. Staff verify participation against tournament registration records. There is no separate age cutoff; applicants under 18 require guardian acknowledgment.
- Application deadline: November 20, 2026, at 11:59 p.m. America/Los_Angeles. The matching native Form close time is saved as 11:59 p.m. PST; eventual closed-state behavior remains untested. The API deadline does not close a Google Form.
- **A selection date has not been set.** Do not invent an announcement, decision, or payment date.
- Selection is based on demonstrated financial need and the application. Receipts substantiate expenses, not financial need.
- Only the selected recipient supplies paid club soccer fee or soccer equipment receipts, before reimbursement. Pay the smaller of $500 or total eligible documented expenses; a guardian handles payment for a minor.
- Publicity contact permission is optional and does not affect selection. Obtain separate permission before publishing identifying information or photos; obtain guardian permission for minors.
- The application makes no promise that an award is tax-free. These rules do not establish a recipient's tax treatment or replace accounting/reporting review.

## 1. Create the native Form and private response Sheet

1. Create the Form while signed in as the Foundation account above. Preserve the approved applicant information, Cup participation, soccer/personal-development, financial-need, expense, and acknowledgment questions. Financial need remains required; expense choices remain club soccer fees and soccer equipment.
2. Preserve minor/adult contact and consent requirements using verified section branching. Under-18 applicants need guardian name, email, and acknowledgment; adults need their own contact email. Do not assume Forms automatically calculates these requirements from DOB.
3. Retain contact-email questions for later staff follow-up, but turn off automatic verified-email collection, response receipts, and applicant response-copy emails. Collecting a contact address is different from sending an email.
4. Allow public responses without Google sign-in. Do not enable a one-response limit or organization restriction that requires sign-in. Do not add uploads; receipts are collected privately only from the selected recipient. Keep publicity consent separate and optional.
5. From the Form's **Responses** area, link a spreadsheet owned by the Foundation. Keep general access **Restricted**, with access only for authorized Foundation reviewers. Do not publish it, enable anyone-with-link access, or expose response summaries/results to applicants.
6. Let Forms create its linked response tab, commonly **Form Responses 1**, with timestamp/question-based columns. This is **not** the old 36-column Applications!A:AJ API schema. Linking an existing spreadsheet can create a new response tab rather than populating an old Applications tab. Verify the actual destination with a test response.
7. Do not point the API at the native response tab or rename/reorder headers to make the schemas appear interchangeable. Preserve original answers; use a separate restricted review tab or deliberately verified staff area for review/payment records.
8. Configure and verify closing on November 20, 2026, at 11:59 p.m. Pacific. Check what supported scheduled-close controls the account actually provides. If automatic closing is unavailable, document an explicit manual-closure plan rather than promising automatic closure. Test the closed-state message.

The native Forms/Sheets interface does not require the fallback Render service's service-account key or email-provider credentials. Do not route native responses through the company API or undocumented Google Form submission endpoints.

The blank workbook at templates/2026-playmakers-cup-applications.xlsx remains an **API-fallback template**, not the native Form response schema. Keep it blank in GitHub. No private spreadsheet ID or edit URL belongs in these setup instructions.

## 2. Manually enable Foundation staff notifications

While signed in as the Foundation account, open the native Form's **Responses** area, use its more-options menu, and enable **Get email notifications for new responses**. Confirm that the account enabling the setting is the intended staff recipient. Other authorized reviewers must configure their own notifications as needed; creating a Form does not automatically subscribe everyone.

This is native **Google Form response** notification, not a Sheets “any changes” rule, an Apps Script edit trigger, or a custom applicant email. The backend cannot inspect or certify this setting. A Sheet edit, API append, or healthy Render service does not prove it works. Verify that an actual native Form response produces the intended Foundation notification.

Do not promise unlimited responses, unlimited storage, immediate notification delivery, or uninterrupted availability. Google account/platform limits still apply. Review the private Form/Sheet during the application period; email is not the sole submission record.

## 3. Confirmation and website connection

Configure the native Form's confirmation message to thank the applicant, confirm submission for review, and explain that submission is not an award decision. Do not promise an applicant email or a selection date. It can include a link to the on-site next-steps page:

https://playmakersportsfoundation.org/scholarship-thank-you.html

Google Forms does **not** automatically redirect the applicant to that page. Use an explicit confirmation-message link. Visiting the public thank-you page alone is not proof of a saved application. Do not promise custom API reference numbers or UUID duplicate protection for native Form responses.

Connect only the verified public Form responder link or supported embed to the website; the native iframe is now implemented locally, pending deployment verification. Keep the custom/API path disabled rather than reactivating a custom form. Native responses do not use Flask's per-IP rate limit or custom session-reference behavior.

## 4. Release verification before accepting applications

1. Confirm Foundation ownership and the intended restricted response destination. Keep private Sheet and Form-edit links out of GitHub.
2. Test the real responder URL while signed out of Google, including a fresh private-browser session. It must not require sign-in, uploads, or organization membership. Confirm applicants cannot see other responses.
3. Submit clearly labeled internal tests with invented details and an authorized staff contact address, not real child information. Test both minor/adult branches, required financial need and consents, expense choices, and optional publicity.
4. Confirm every test appears correctly in the native linked response tab and the Foundation receives the native new-response notification. Confirm applicants receive no automatic emails or response copies.
5. Check the confirmation message and optional next-steps link. Verify there is no claim of automatic redirect, an award decision, a selection date, or an unimplemented reference/duplicate guarantee.
6. Verify and record the native closing-time setting or manual-closure plan and the closed-state message. The API's Pacific deadline is not a substitute.
7. Remove only clearly identified internal test responses through the normal authorized cleanup process, checking Forms and Sheets as appropriate. Do not delete real applications or assume cleanup in one removes both copies.
8. Publish the verified responder link/embed, then check desktop/mobile access from the scholarship page, Home, Programs, navigation, and footer. Confirm the custom form remains disabled and nothing targets the company API.

## 5. Staff selection and reimbursement checklist

1. Use private review fields for **Review status**, **Cup participation verified**, **Financial need reviewed**, **Selection rationale**, **Approved reimbursement (USD)**, and **Receipts/payment record**. Preserve original answers and relate each review to the correct native response.
2. Foundation reviewers assess the financial need described and verify tournament participation. Record a short, factual selection reason tied to the scholarship's charitable purpose. Do not require tax returns, SSNs, bank statements, or receipt uploads from all applicants.
3. Have Foundation decision-makers approve the recipient independently of the tournament business's sales or promotion. Disclose and manage conflicts; do not favor insiders or require an additional tournament-business purchase to receive a scholarship. Keep the tournament-eligibility restriction in the policy/accounting review rather than assuming that restriction is automatically permissible or automatically prohibited.
4. Contact the selected adult or guardian privately. Collect only receipts needed to show paid, eligible soccer expenses. Ask them to redact card numbers and other unrelated sensitive information. Store receipts in a separate restricted Foundation Drive folder, not a public upload folder.
5. Check the expense belongs to the recipient, was actually paid, is eligible, and is not being reimbursed twice. Record receipt dates, eligible total, approval, payee, payment date/reference, and a restricted receipt-folder link privately. Never put bank account details in the application Sheet.
6. Reimburse no more than documented eligible costs and no more than $500. If the documents do not support the full award, request eligible receipts or pay only the supported amount. Record the Foundation approver and payment through the normal accounting process.
7. Follow the Foundation accountant's instructions for recipient/payment documentation and required reporting; do not tell families soccer receipts automatically make payment tax-free. Keep access and retention consistent with the Foundation's records policy.
8. Do not publish a recipient's name, photo, or story based solely on the optional contact checkbox. Obtain separate, specific permission first.

## Storage-only API fallback reference

The independent backend/app.py is disabled by default. Its preserved fallback saves applications only when deliberately enabled; it does not send staff or applicant emails, create a Google Form, or configure notifications. Resend/Gmail/MailApp sending is removed. See backend/README.md for isolated deployment settings; do not copy company credentials or environment groups.

- GET /health is cheap liveness only. The deployed Foundation URL is https://foundation-website-7o9d.onrender.com. The independent .github/workflows/foundation-keepalive.yml now retains manual dispatch only; its automatic schedule and push triggers are removed. A manual diagnostic does not prove Form/Sheet/notification readiness, and native Forms does not need the retired API kept warm.
- Leave FOUNDATION_SCHOLARSHIP_API_ENABLED unset or false. Only the exact value true intentionally enables an approved API rollback; existing Google credentials alone cannot enable it.
- GET /api/foundation/scholarship-applications/status returns accepting_applications=false and reason=intake_retired without Google calls by default. Only under explicit opt-in does it check the fallback deadline and private Applications tab/header readiness. It never establishes native Form readiness, closing settings, or notification delivery.
- POST /api/foundation/scholarship-applications returns HTTP 410 while retired, before parsing answers or contacting Google. Only under explicit opt-in does it preserve validated storage with the unchanged 36-column SHEET_COLUMNS schema and RAW values. The fallback requires financial need, grades 6–12, consents, and the Pacific deadline. UUID retries prevent duplicate API rows; changed answers under an already-saved UUID receive HTTP 409. These protections do not apply to native Forms.
- A successful API save returns success, application_id, submitted_at, and already_submitted. The old notification_sent, confirmation_sent, and email_configured flags are removed.
- Do not activate the fallback custom form or point it at a native response tab for the Google Forms launch. Choosing the fallback would require its own setup and verification.

Render/GitHub limits still apply to the fallback and manual diagnostic. A manual health check does not guarantee continuous uptime or unlimited free usage. Google Forms itself does not depend on Render or this workflow. Automated backend tests use mocked Google services; they do not establish that the live native Form/Sheet/notification flow works.
