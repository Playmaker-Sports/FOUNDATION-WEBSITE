/** @OnlyCurrentDoc */

/**
 * Playmaker Sports Foundation scholarship intake.
 *
 * The website application form posts each application here. The script saves
 * it as a row in the spreadsheet it is attached to; staff review that list.
 * It sends no email, leaving the account's daily email limit for the contact
 * form. Setup and deployment steps are in SCHOLARSHIP_SETUP.md.
 */

// Set to false (then deploy a new version) to close applications early.
const ACCEPTING_APPLICATIONS = true;

const SHEET_NAME = 'Applications';
const TIME_ZONE = 'America/Los_Angeles';
// First moment applications are closed: November 21, 2026, 12:00 a.m. Pacific.
const CLOSES_AT = new Date('2026-11-21T00:00:00-08:00');
const CLOSED_MESSAGE = 'Applications closed on November 20, 2026, at 11:59 p.m. Pacific.';
const GRADES = ['6th grade', '7th grade', '8th grade', '9th grade', '10th grade', '11th grade', '12th grade'];
const EXPENSES = ['Club soccer fees', 'Soccer equipment'];
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Field name: [label for error messages, maximum length, required for everyone].
const TEXT_FIELDS = {
  applicant_name: ['Player’s full name', 200, true],
  date_of_birth: ['Date of birth', 10, true],
  grade_level: ['Grade level', 100, true],
  city: ['City', 120, true],
  school: ['Current school', 200, true],
  guardian_name: ['Parent/guardian name', 200, false],
  guardian_email: ['Parent/guardian email', 254, false],
  applicant_email: ['Applicant email', 254, false],
  club_team: ['Club and team', 250, true],
  team_age_group: ['Team age group', 100, true],
  growth: ['the soccer and personal growth response', 5000, true],
  challenge: ['the challenge response', 5000, true],
  goals: ['the future goals response', 5000, true],
  financial_need: ['the financial need response', 5000, true],
  additional_context: ['the additional context response', 3000, false],
};
const MULTILINE_FIELDS = ['growth', 'challenge', 'goals', 'financial_need', 'additional_context'];
const REQUIRED_CONFIRMATIONS = {
  participation_confirmed: 'the Cup participation confirmation',
  accuracy_ack: 'the accuracy acknowledgment',
  privacy_ack: 'the privacy acknowledgment',
  payment_ack: 'the reimbursement acknowledgment',
};

// Columns are found by header text, so staff can reorder columns or add their
// own. Renaming or deleting one of these headers stops new applications saving.
const HEADERS = [
  'Submitted (Pacific)', 'Application ID', 'Player name', 'Date of birth', 'Age', 'Grade',
  'City', 'School', 'Guardian name', 'Guardian email', 'Applicant email',
  'Club and team', 'Team age group', 'Soccer and personal growth', 'Challenge and response',
  'Future goals', 'Financial need', 'Expenses', 'Additional context',
  'Cup participation confirmed', 'Guardian acknowledgment', 'Accuracy acknowledgment',
  'Privacy acknowledgment', 'Reimbursement acknowledgment', 'Publicity contact OK',
  'Review status', 'Cup participation verified', 'Financial need reviewed',
  'Selection rationale', 'Approved reimbursement (USD)', 'Receipts/payment record',
];

function doGet() {
  // Opening the web app URL in a browser shows whether it is accepting.
  return reply_({ ok: true, accepting_applications: accepting_() });
}

function doPost(event) {
  try {
    const input = parse_(event);
    if (!input) return reply_({ ok: false, message: 'Your application could not be read. Please try again.' });
    if (typeof input._honey === 'string' && input._honey.trim()) {
      // Only bots fill the hidden field. Tell them it worked and save nothing.
      return reply_({ ok: true, id: String(input.submission_id || '') });
    }
    if (!accepting_()) return reply_({ ok: false, closed: true, message: CLOSED_MESSAGE });
    const checked = validate_(input);
    if (checked.error) return reply_({ ok: false, message: checked.error });
    return reply_(save_(checked.application));
  } catch (error) {
    // Never log the error message: it can contain applicant answers.
    console.error('Scholarship application failed: ' + error.name);
    return reply_({ ok: false, message: 'Your application could not be saved. Your answers are still here; please try again.' });
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
  // The script runs only when the website posts, so it keeps no scheduled triggers.
  for (const trigger of ScriptApp.getProjectTriggers()) ScriptApp.deleteTrigger(trigger);
  console.log('Setup finished. Applications will be saved to the ' + SHEET_NAME + ' tab.');
}

function save_(application) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) {
    return { ok: false, message: 'The application service is busy. Please wait a moment and try again.' };
  }
  try {
    const sheet = sheet_();
    const columns = columns_(sheet);
    const last = sheet.getLastRow();
    // A retry after a lost reply reuses the same ID; don't save it twice.
    const duplicate = last > 1 && sheet.getRange(2, columns['Application ID'], last - 1, 1)
      .createTextFinder(application.submission_id).matchEntireCell(true).findNext();
    if (duplicate) return { ok: true, id: application.submission_id };

    const row = last + 1;
    const values = new Array(sheet.getLastColumn()).fill('');
    const yesNo = flag => flag ? 'Yes' : 'No';
    const fields = {
      'Submitted (Pacific)': Utilities.formatDate(new Date(), TIME_ZONE, 'yyyy-MM-dd HH:mm:ss'),
      'Application ID': application.submission_id,
      'Player name': text_(application.applicant_name),
      'Date of birth': text_(application.date_of_birth),
      'Age': application.age,
      'Grade': text_(application.grade_level),
      'City': text_(application.city),
      'School': text_(application.school),
      'Guardian name': text_(application.guardian_name),
      'Guardian email': text_(application.guardian_email),
      'Applicant email': text_(application.applicant_email),
      'Club and team': text_(application.club_team),
      'Team age group': text_(application.team_age_group),
      'Soccer and personal growth': text_(application.growth),
      'Challenge and response': text_(application.challenge),
      'Future goals': text_(application.goals),
      'Financial need': text_(application.financial_need),
      'Expenses': application.eligible_expenses.join('; '),
      'Additional context': text_(application.additional_context),
      'Cup participation confirmed': 'Yes',
      'Guardian acknowledgment': application.is_minor ? 'Yes' : 'Not needed (18+)',
      'Accuracy acknowledgment': 'Yes',
      'Privacy acknowledgment': 'Yes',
      'Reimbursement acknowledgment': 'Yes',
      'Publicity contact OK': yesNo(application.publicity_consent),
    };
    for (const header in fields) values[columns[header] - 1] = fields[header];
    sheet.getRange(row, 1, 1, values.length).setValues([values]);
    SpreadsheetApp.flush();
    return { ok: true, id: application.submission_id };
  } finally {
    lock.releaseLock();
  }
}

function validate_(input) {
  const application = {};
  for (const field in TEXT_FIELDS) {
    const [label, limit, required] = TEXT_FIELDS[field];
    const raw = input[field] === undefined || input[field] === null ? '' : input[field];
    if (typeof raw !== 'string') return { error: 'Please check ' + label + '.' };
    // Single-line answers come from one-line inputs, so flatten any line breaks.
    const value = (MULTILINE_FIELDS.includes(field) ? raw : raw.replace(/\s+/g, ' ')).trim();
    if (required && !value) return { error: 'Please complete ' + label + '.' };
    if (value.length > limit) return { error: 'Please shorten ' + label + '.' };
    if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/.test(value)) return { error: 'Please check ' + label + '.' };
    application[field] = value;
  }
  if (!GRADES.includes(application.grade_level)) return { error: 'Applicants must currently be in grades 6 through 12.' };
  if (typeof input.submission_id !== 'string' || !UUID_PATTERN.test(input.submission_id)) {
    return { error: 'Please reload the page and submit again.' };
  }
  application.submission_id = input.submission_id.toLowerCase();

  const birth = application.date_of_birth.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const birthDate = birth && new Date(Date.UTC(+birth[1], +birth[2] - 1, +birth[3]));
  if (!birth || birthDate.getUTCMonth() !== +birth[2] - 1 || birthDate.getUTCDate() !== +birth[3]) {
    return { error: 'Please check Date of birth.' };
  }
  const today = Utilities.formatDate(new Date(), TIME_ZONE, 'yyyy-MM-dd');
  if (application.date_of_birth > today) return { error: 'Date of birth cannot be in the future.' };
  const [year, month, day] = today.split('-').map(Number);
  application.age = year - +birth[1] - (month < +birth[2] || (month === +birth[2] && day < +birth[3]) ? 1 : 0);
  application.is_minor = application.age < 18;

  const contactFields = application.is_minor ? ['guardian_name', 'guardian_email'] : ['applicant_email'];
  for (const field of contactFields) {
    if (!application[field]) return { error: 'Please complete ' + TEXT_FIELDS[field][0] + '.' };
  }
  for (const field of ['guardian_email', 'applicant_email']) {
    if (application[field] && !EMAIL_PATTERN.test(application[field])) return { error: 'Please check ' + TEXT_FIELDS[field][0] + '.' };
  }
  if (!application.is_minor) {
    // Adults apply for themselves; drop any leftover guardian details.
    application.guardian_name = '';
    application.guardian_email = '';
  }
  for (const field in REQUIRED_CONFIRMATIONS) {
    if (input[field] !== true) return { error: 'Please check ' + REQUIRED_CONFIRMATIONS[field] + '.' };
  }
  if (application.is_minor && input.guardian_ack !== true) return { error: 'Please check the parent/guardian acknowledgment.' };
  if (input.publicity_consent !== undefined && typeof input.publicity_consent !== 'boolean') {
    return { error: 'Please check the publicity contact permission.' };
  }
  application.publicity_consent = input.publicity_consent === true;

  const expenses = input.eligible_expenses;
  if (!Array.isArray(expenses) || !expenses.length || expenses.length > EXPENSES.length ||
      expenses.some(item => !EXPENSES.includes(item)) || new Set(expenses).size !== expenses.length) {
    return { error: 'Choose club soccer fees, soccer equipment, or both.' };
  }
  application.eligible_expenses = EXPENSES.filter(item => expenses.includes(item));
  return { application };
}

function parse_(event) {
  try {
    const value = JSON.parse(event.postData.contents);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch (error) {
    return null;
  }
}

function accepting_() {
  return ACCEPTING_APPLICATIONS && new Date() < CLOSES_AT;
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

// A leading apostrophe stores the answer as plain text, so an answer that
// starts with "=" is never run as a formula and dates stay as typed.
function text_(value) {
  return value ? "'" + value : '';
}

function reply_(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON);
}
