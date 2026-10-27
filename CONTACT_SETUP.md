# Contact form: setup and administration

## How messages work

`contact.html` → `contact.js` sends each message to a Google Apps Script web app (`apps-script/contact-intake.gs`) attached to the Foundation's contact messages spreadsheet. The script:

1. checks the message (required fields, lengths, a valid email address, a topic from the list),
2. adds one row to the **Messages** tab (a retry with the same message ID is not saved twice),
3. emails `NOTIFY_TO` (info@playmakersportsfoundation.org) the full message. The email's Reply-To is the sender, so staff can just hit **Reply**.
4. replies to the page, which shows the thank-you. If the send fails, the visitor sees an error and their message stays in the form.

Senders never get an email; the thank-you on the page is their confirmation. This is a separate script and spreadsheet from the scholarship form, and it does not go through `playmaker-api`.

Until the form has a web app URL, the page disables the button and asks visitors to email info@playmakersportsfoundation.org. Publishing the page before the URL is ready is safe.

## Email limits

The daily email limit (about **100 a day on a regular Gmail account**, up to about **1,500 on Google Workspace**) belongs to the account that deploys the script and is shared by every script that account runs. The Foundation's `info@playmakersportsfoundation.org` account reported **100 a day** on October 21, 2026. The scholarship script sends no email, so the contact form has the whole limit.

The live setup is the **Foundation Contact Messages** Sheet in `info@`'s Drive, with its **Contact form** Apps Script deployed as a web app (Execute as: Me, Who has access: Anyone). The form's `action` is that web app's `/exec` URL.

Messages always save, even when no email goes out. Their **Staff notified** cell stays `No`, and an hourly job emails them (up to 25 per run) once the limit resets.

## One-time setup

1. Sign in to the Foundation's Google Workspace account (the same one that runs the scholarship script). Create a new Google Sheet named **Foundation Contact Messages**. Keep sharing **Restricted** to Foundation staff; messages contain names and email addresses.
2. In the Sheet, open **Extensions → Apps Script**. Replace the editor contents with `apps-script/contact-intake.gs`, and check `NOTIFY_TO` at the top.
3. Select `setup` in the function menu and click **Run**. Approve the permissions (sending email as you, this spreadsheet, and running on a schedule). Setup creates the **Messages** tab with its headers, installs the hourly catch-up job, logs the daily email limit, and sends a test email to `NOTIFY_TO`.
4. Click **Deploy → New deployment → Web app**. Set **Execute as: Me** and **Who has access: Anyone**, then click **Deploy** and copy the URL that ends in `/exec`. If **Anyone** isn't offered, a Workspace admin needs to allow web apps to be shared outside the organization.
5. Open the `/exec` URL in a browser. It should show `{"ok":true,"form":"contact"}`. (The scholarship URL shows `accepting_applications` instead, which is how to tell the two apart.)
6. Put the URL in the `action` attribute of `<form id="contactForm">` in `contact.html`, then publish the website.
7. Send one clearly fake message on the live page (for example, last name "TEST ONLY"). Confirm the row, the email, that **Reply** addresses the sender, and the thank-you. Then delete the test row.

Column headers can be moved, and staff can add their own columns. Don't rename or delete the script's headers, or new messages stop saving.

## Working the inbox

- Reply from the notification email. The Sheet keeps the record.
- Use the **Status** column (new rows start as `New`; for example, change to `Replied` or `Closed`) and **Staff notes** to track follow-up.
- If someone says they never heard back, search the Sheet for their email address.

## Changing the script later

After editing the code, click **Deploy → Manage deployments**, edit the existing web app deployment, choose **Version: New version**, and click **Deploy**. This keeps the same URL. Creating a *new* deployment produces a different URL that the website doesn't know about.

To change the topic list, edit it in both `contact.html` and `TOPICS` in the script, then deploy a new version. A topic missing from the script is rejected.

## Spam

A hidden field catches basic bots. A person's autofill can fill it too, so a message with that field filled is still saved, with **Status** set to `Possible spam` and **Staff notified** set to `Skipped (possible spam)`. It is not emailed, so bots can't use up the daily limit. Check those rows now and then for real messages.

The script also checks every field itself. Rejected messages are logged by reason (never their contents) under **Executions** in the Apps Script project. If real spam shows up, add Cloudflare Turnstile to the form and check its token in the script.
