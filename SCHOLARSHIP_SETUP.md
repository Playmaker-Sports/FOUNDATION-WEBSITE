# 2026 Playmakers Cup scholarship: setup and administration

## How applications work

**Home → Apply Here → `scholarship.html` (details) → Apply Now → `scholarship-application.html` → `scholarship-thank-you.html`.**

`scholarship.js` sends each application to a Google Apps Script web app (`apps-script/scholarship-intake.gs`) attached to the Foundation's applications spreadsheet. The script:

1. checks the answers and the deadline,
2. adds one row to the **Applications** tab (a retry with the same application ID is not saved twice),
3. replies to the page, which then goes to the thank-you page. If the save fails, the applicant sees an error and their answers stay in the form.

**No emails are sent**, to staff or applicants. Staff review new applications in the Sheet, and the thank-you page is the applicant's confirmation. Sending no email leaves the account's whole daily email limit (100 a day for `info@playmakersportsfoundation.org`) for the contact form. No server, Render service, or API key is involved.

The live setup is the **2026 Playmakers Cup Scholarship Applications** Sheet in `info@`'s Drive, with its **Scholarship intake** Apps Script deployed as a web app (Execute as: Me, Who has access: Anyone). The form's `action` is that web app's `/exec` URL.

## One-time setup

1. Sign in to the Google Workspace account that should own the applications. Create a new Google Sheet in its Drive and keep sharing **Restricted** to Foundation reviewers.
2. In the Sheet, open **Extensions → Apps Script** and replace the editor contents with `apps-script/scholarship-intake.gs`.
3. Select `setup` in the function menu and click **Run**, then approve the permissions. Setup creates the **Applications** tab with its headers.
4. Click **Deploy → New deployment → Web app**. Set **Execute as: Me** and **Who has access: Anyone**, then click **Deploy** and copy the URL that ends in `/exec`. If **Anyone** isn't offered, a Workspace admin needs to allow web apps to be shared outside the organization.
5. Open the `/exec` URL in a browser. It should show `{"ok":true,"accepting_applications":true}`.
6. Put the URL in the `action` attribute of the form in `scholarship-application.html`, then publish the website.
7. Submit one clearly fake application on the live page (for example, player name "TEST ONLY"). Confirm the row and the thank-you page, then delete the test row.

Column headers can be moved, and staff can add their own columns. Don't rename or delete the script's headers, or new applications stop saving.

## Changing the script later

After editing the code, click **Deploy → Manage deployments**, edit the existing web app deployment, choose **Version: New version**, and click **Deploy**. This keeps the same URL. Creating a *new* deployment produces a different URL that the website doesn't know about.

To close applications early, set `ACCEPTING_APPLICATIONS = false` and deploy a new version. The page and the script both stop accepting applications at the deadline on their own.

## Spam

A hidden field catches basic bots: the script replies "saved" and stores nothing. The script also checks every answer itself. If real spam shows up, add Cloudflare Turnstile to the form and check its token in the script.

## Agreed award rules

- One need-based recipient receives reimbursement of up to $500 for paid club soccer fees or soccer equipment/gear.
- Applicants must currently be in grades 6–12 and be registered players participating with a team in the 2026 Playmakers Cup. Verify participation against tournament records. There is no separate age cutoff.
- For applicants under 18, guardian name, email, and acknowledgment are required; the applicant's own email is optional. Adults must provide their own email.
- Applications close **November 20, 2026, at 11:59 p.m. Pacific** (`America/Los_Angeles`).
- **A selection date has not been set.** Do not invent an announcement, decision, or payment date.
- Selection is based on demonstrated financial need and the application. Receipts substantiate expenses, not financial need. Do not require tax returns, bank statements, SSNs, or receipt uploads with the application.
- Only the selected recipient supplies receipts before reimbursement. Pay the smaller of $500 or eligible documented expenses; a guardian handles payment for a minor.
- Publicity contact permission is separate, optional, and does not affect selection. Obtain separate, specific permission before publishing identifying information or photos, including guardian permission for minors.
- Do not promise tax-free treatment. Follow the Foundation accountant's policy, documentation, and payment/reporting guidance, including review of the tournament-participation restriction and related-business conflicts.

## Staff selection and reimbursement

1. Preserve original answers. Use the review columns (status, verified Cup participation, financial-need review, selection rationale, approved reimbursement, receipts/payment record) for staff notes.
2. Have Foundation decision-makers assess need and approve the recipient independently of business sales/promotion. Manage conflicts; do not favor insiders or require an additional business purchase. Record a factual reason tied to the charitable purpose and retain the tournament-eligibility restriction in policy/accounting review.
3. Contact the selected adult or guardian privately. Collect only necessary paid-expense receipts, with card numbers and unrelated sensitive information redacted, in a separate restricted Foundation Drive folder. Never put bank details in the application Sheet.
4. Verify expenses belong to the recipient, were paid, are eligible, and are not reimbursed twice. Record receipt dates, eligible total, approver, payee, payment date/reference, and private receipt-folder link. Reimburse no more than documented eligible costs or $500.
5. Follow the accountant's required documentation/reporting and the Foundation's access/retention policy. Obtain separate publicity permission before sharing any name, image, or story.
