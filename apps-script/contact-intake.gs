/** @OnlyCurrentDoc */

/**
 * Playmaker Sports Foundation contact form.
 *
 * The website contact form posts each message here. The script saves it as a
 * row in the spreadsheet it is attached to, then emails NOTIFY_TO with the
 * sender as Reply-To. Setup and deployment steps are in CONTACT_SETUP.md.
 */

// Who gets each message. Each address uses one email from the account's daily
// limit per message, so keep this to one address.
const NOTIFY_TO = 'info@playmakersportsfoundation.org';
// The daily email limit is shared by every script this account runs, including
// the scholarship form. Contact emails stop while fewer than this many are left;
// the hourly catch-up sends them after the limit resets.
const KEEP_FOR_OTHER_EMAILS = 20;
// Most catch-up emails sent per hourly run.
const CATCH_UP_BATCH = 25;

const SHEET_NAME = 'Messages';
const TIME_ZONE = 'America/Los_Angeles';
// Must match the topic options in contact.html.
const TOPICS = [
  'Athlete Scholarship', 'Soccer Clinic Information', 'Partnership / Sponsorship', 'Volunteering',
  'Coaching Education', 'Equipment Assistance', 'Donation Inquiry', 'General Inquiry',
];
// The sender's address becomes the email's Reply-To, so it can't hold a list.
const EMAIL_PATTERN = /^[^\s@,;<>"]+@[^\s@,;<>"]+\.[^\s@,;<>"]+$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Field name: [label for error messages, maximum length].
const TEXT_FIELDS = {
  first_name: ['First name', 100],
  last_name: ['Last name', 100],
  email: ['Email address', 254],
  subject: ['the topic', 100],
  message: ['Message', 5000],
};

// Columns are found by header text, so staff can reorder columns or add their
// own. Renaming or deleting one of these headers stops new messages saving.
const HEADERS = [
  'Received (Pacific)', 'Message ID', 'First name', 'Last name', 'Email', 'Topic', 'Message',
  'Staff notified', 'Status', 'Staff notes',
];

function doGet() {
  // Opening the web app URL in a browser shows that the contact script is live.
  return reply_({ ok: true, form: 'contact' });
}

function doPost(event) {
  try {
    const input = parse_(event);
    if (!input) return reply_({ ok: false, message: 'Your message could not be read. Please try again.' });
    if (typeof input._honey === 'string' && input._honey.trim()) {
      // Only bots fill the hidden field. Tell them it worked and save nothing.
      return reply_({ ok: true, id: String(input.submission_id || '') });
    }
    const checked = validate_(input);
    if (checked.error) return reply_({ ok: false, message: checked.error });
    return reply_(save_(checked.contact));
  } catch (error) {
    // Never log the error message: it can contain the sender's message.
    console.error('Contact message failed: ' + error.name);
    return reply_({ ok: false, message: 'Your message could not be sent. It is still in the form; please try again.' });
  }
}

// Runs every hour (installed by setup). Emails any message whose email was not
// sent, for example after the daily limit.
function sendMissedNotifications() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;
  try {
    const sheet = sheet_();
    const columns = columns_(sheet);
    const last = sheet.getLastRow();
    if (last < 2) return;
    const flags = sheet.getRange(2, columns['Staff notified'], last - 1, 1).getValues();
    const pending = [];
    flags.forEach((flag, index) => { if (flag[0] === 'No') pending.push(index + 2); });
    for (const row of pending.slice(0, CATCH_UP_BATCH)) {
      if (!notify_(sheet, columns, row, true)) break;
    }
  } finally {
    lock.releaseLock();
  }
}

// Run once from the Apps Script editor after pasting this script.
function setup() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(SHEET_NAME) || spreadsheet.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  columns_(sheet);
  for (const trigger of ScriptApp.getProjectTriggers()) {
    if (trigger.getHandlerFunction() === 'sendMissedNotifications') ScriptApp.deleteTrigger(trigger);
  }
  ScriptApp.newTrigger('sendMissedNotifications').timeBased().everyHours(1).create();
  const remaining = MailApp.getRemainingDailyQuota();
  console.log('Emails left today: ' + remaining + ' (about 100 a day means a regular Gmail account; about 1,500 means Google Workspace).');
  MailApp.sendEmail(NOTIFY_TO, 'Website contact form emails are set up',
    'Messages from the Foundation website contact form will be emailed to this address. Reply to one to answer the sender.\n\n' +
    'Messages spreadsheet: ' + sheetUrl_(sheet));
  console.log('Setup finished. A test email was sent to ' + NOTIFY_TO + '.');
}

function save_(contact) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) {
    return { ok: false, message: 'The contact form is busy. Please wait a moment and try again.' };
  }
  try {
    const sheet = sheet_();
    const columns = columns_(sheet);
    const last = sheet.getLastRow();
    // A retry after a lost reply reuses the same ID; don't save it twice.
    const duplicate = last > 1 && sheet.getRange(2, columns['Message ID'], last - 1, 1)
      .createTextFinder(contact.submission_id).matchEntireCell(true).findNext();
    if (duplicate) return { ok: true, id: contact.submission_id };

    const row = last + 1;
    const values = new Array(sheet.getLastColumn()).fill('');
    const fields = {
      'Received (Pacific)': Utilities.formatDate(new Date(), TIME_ZONE, 'yyyy-MM-dd HH:mm:ss'),
      'Message ID': contact.submission_id,
      'First name': text_(contact.first_name),
      'Last name': text_(contact.last_name),
      'Email': text_(contact.email),
      'Topic': text_(contact.subject),
      'Message': text_(contact.message),
      'Staff notified': 'No',
      'Status': 'New',
    };
    for (const header in fields) values[columns[header] - 1] = fields[header];
    sheet.getRange(row, 1, 1, values.length).setValues([values]);
    SpreadsheetApp.flush();
    // The row is saved; a failed email is retried by sendMissedNotifications.
    notify_(sheet, columns, row, false);
    return { ok: true, id: contact.submission_id };
  } finally {
    lock.releaseLock();
  }
}

// Emails one saved message to NOTIFY_TO. Returns false when no email could be
// sent, so the catch-up stops instead of trying the rest.
function notify_(sheet, columns, row, late) {
  try {
    if (MailApp.getRemainingDailyQuota() <= KEEP_FOR_OTHER_EMAILS) return false;
    const cell = header => sheet.getRange(row, columns[header]).getDisplayValue();
    const name = (cell('First name') + ' ' + cell('Last name')).trim();
    const email = cell('Email');
    const body = [
      late
        ? 'This message was saved earlier, but its email could not be sent at the time (usually the daily email limit).'
        : 'New message from the Foundation website contact form. Reply to this email to answer ' + name + '.',
      '',
      'Name: ' + name,
      'Email: ' + email,
      'Topic: ' + cell('Topic'),
      'Received: ' + cell('Received (Pacific)') + ' Pacific',
      '',
      cell('Message'),
      '',
      '---',
      'All messages: ' + sheetUrl_(sheet),
    ].join('\n');
    const options = { name: 'Foundation website' };
    if (EMAIL_PATTERN.test(email)) options.replyTo = email;
    MailApp.sendEmail(NOTIFY_TO, 'Website message: ' + cell('Topic') + ' from ' + name, body, options);
    sheet.getRange(row, columns['Staff notified']).setValue('Yes');
    return true;
  } catch (error) {
    console.warn('Contact notification not sent: ' + error.name);
    return false;
  }
}

function validate_(input) {
  const contact = {};
  for (const field in TEXT_FIELDS) {
    const [label, limit] = TEXT_FIELDS[field];
    const raw = input[field] === undefined || input[field] === null ? '' : input[field];
    if (typeof raw !== 'string') return { error: 'Please check ' + label + '.' };
    // Single-line answers end up in email subjects, so flatten any line breaks.
    const value = (field === 'message' ? raw : raw.replace(/\s+/g, ' ')).trim();
    if (!value) return { error: 'Please complete ' + label + '.' };
    if (value.length > limit) return { error: 'Please shorten ' + label + '.' };
    if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/.test(value)) return { error: 'Please check ' + label + '.' };
    contact[field] = value;
  }
  if (!EMAIL_PATTERN.test(contact.email)) return { error: 'Please check Email address.' };
  if (!TOPICS.includes(contact.subject)) return { error: 'Please choose a topic from the list.' };
  if (typeof input.submission_id !== 'string' || !UUID_PATTERN.test(input.submission_id)) {
    return { error: 'Please reload the page and send your message again.' };
  }
  contact.submission_id = input.submission_id.toLowerCase();
  return { contact };
}

function parse_(event) {
  try {
    const value = JSON.parse(event.postData.contents);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch (error) {
    return null;
  }
}

function sheet_() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) throw new Error('Run setup() first: the ' + SHEET_NAME + ' tab is missing.');
  return sheet;
}

function columns_(sheet) {
  const width = Math.max(sheet.getLastColumn(), 1);
  const found = {};
  sheet.getRange(1, 1, 1, width).getValues()[0].forEach((header, index) => { found[String(header).trim()] = index + 1; });
  const missing = HEADERS.filter(header => !found[header]);
  if (missing.length) throw new Error('The ' + SHEET_NAME + ' tab is missing these column headers: ' + missing.join(', '));
  return found;
}

function sheetUrl_(sheet) {
  return SpreadsheetApp.getActiveSpreadsheet().getUrl() + '#gid=' + sheet.getSheetId();
}

// A leading apostrophe stores the answer as plain text, so an answer that
// starts with "=" is never run as a formula.
function text_(value) {
  return value ? "'" + value : '';
}

function reply_(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON);
}
