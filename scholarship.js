(() => {
  'use strict';
  const form = document.getElementById('scholarship-form');
  if (!form) return;
  const submit = document.getElementById('submit-application');
  const statusMessage = document.getElementById('availability-message');
  const statusBox = document.getElementById('availability');
  const errorBox = document.getElementById('form-error');
  const success = document.getElementById('application-success');
  const dob = document.getElementById('dob');
  const expenseInputs = [...form.querySelectorAll('[name="eligible_expenses"]')];
  const localPreview = location.protocol === 'file:';
  // The form's action is the Foundation's Apps Script web app, which saves each
  // application to the scholarship Sheet and emails staff (SCHOLARSHIP_SETUP.md).
  const endpoint = (() => {
    try {
      const url = new URL(form.getAttribute('action') || '');
      return url.protocol === 'https:' && url.hostname === 'script.google.com' && !url.search && !url.hash &&
        /^\/(?:a\/macros\/[^/]+|macros)\/s\/[\w-]+\/exec$/.test(url.pathname) ? url.href : null;
    } catch { return null; }
  })();
  const deadlineExclusive = Date.parse('2026-11-21T00:00:00-08:00');
  const closedMessage = 'Applications closed on November 20, 2026, at 11:59 p.m. Pacific.';
  const idKey = 'foundation-cup-2026-submission-id';
  const receivedKey = 'foundation-cup-2026-received-id';
  let accepting = false;
  let sending = false;

  const stored = {
    get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, value); } catch { /* Session storage is optional. */ } },
    remove(key) { try { sessionStorage.removeItem(key); } catch { /* Session storage is optional. */ } }
  };
  const submissionId = stored.get(idKey) || crypto.randomUUID();
  stored.set(idKey, submissionId);

  function pacificToday() {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone:'America/Los_Angeles', year:'numeric', month:'2-digit', day:'2-digit' }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function updateAgeRequirements() {
    const today = pacificToday();
    dob.max = today;
    const [year, month, day] = today.split('-').map(Number);
    const [birthYear, birthMonth, birthDay] = dob.value.split('-').map(Number);
    const age = year - birthYear - (month < birthMonth || (month === birthMonth && day < birthDay) ? 1 : 0);
    const adult = dob.value && dob.value <= today && age >= 18;
    dob.setCustomValidity(dob.value > today ? 'Date of birth cannot be in the future.' : '');
    document.getElementById('guardian-fields').hidden = Boolean(adult);
    document.getElementById('guardian-ack-row').hidden = Boolean(adult);
    for (const name of ['guardian_name','guardian_email','guardian_ack']) {
      form.elements[name].required = !adult;
      form.elements[name].disabled = Boolean(adult);
    }
    form.elements.applicant_email.required = Boolean(adult);
    document.getElementById('applicant-email-required').hidden = !adult;
  }

  function validateExpenses() {
    expenseInputs[0].setCustomValidity(expenseInputs.some(input => input.checked) ? '' : 'Choose at least one expense the scholarship would help cover.');
  }

  function showReceived(reference) {
    accepting = false;
    form.hidden = true;
    statusBox.hidden = true;
    success.hidden = false;
    document.getElementById('application-reference').textContent = reference;
  }

  // Sends the application, trying again when Google's reply is garbled (right
  // after a script update it can briefly return an error page or the wrong
  // reply even though the save worked). Retries reuse the same application ID,
  // which the script never saves twice.
  async function send(body, signal) {
    for (let attempt = 1; ; attempt++) {
      try {
        // A text/plain body keeps this a simple cross-site request; Apps Script
        // cannot answer the preflight that an application/json body triggers.
        const response = await fetch(endpoint, { method:'POST', headers:{ 'Content-Type':'text/plain;charset=utf-8' }, body, signal });
        const result = await response.json().catch(() => ({}));
        if (result.ok === false || (result.ok === true && result.id === submissionId)) return result;
        if (attempt >= 3) return {};
      } catch (error) {
        if (error.name === 'AbortError' || attempt >= 3) throw error;
      }
      await new Promise(resolve => setTimeout(resolve, 2000 * attempt));
    }
  }

  function closeApplications() {
    accepting = false;
    submit.disabled = true;
    form.hidden = true;
    statusMessage.textContent = closedMessage;
  }

  function showAvailability() {
    form.hidden = false;
    if (localPreview) {
      statusMessage.textContent = 'Local preview. You can review the form here, but applications cannot be submitted from this file.';
    } else if (Date.now() >= deadlineExclusive) {
      closeApplications();
    } else if (!endpoint) {
      statusMessage.textContent = 'Application preview. Submissions are not connected yet.';
    } else {
      accepting = true;
      submit.disabled = false;
      statusMessage.textContent = 'Apply by November 20, 2026, at 11:59 p.m. Pacific. No receipt uploads are needed with your application.';
    }
  }

  for (const textarea of form.querySelectorAll('textarea')) {
    const counter = document.querySelector(`[data-count-for="${textarea.id}"]`);
    if (counter) textarea.addEventListener('input', () => {
      const words = textarea.value.trim().split(/\s+/).filter(Boolean).length;
      counter.textContent = `${words} ${words === 1 ? 'word' : 'words'}`;
    });
  }
  dob.addEventListener('input', updateAgeRequirements);
  for (const input of expenseInputs) input.addEventListener('change', validateExpenses);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!accepting || !endpoint || sending) return;
    errorBox.hidden = true;
    if (Date.now() >= deadlineExclusive) return closeApplications();
    updateAgeRequirements();
    validateExpenses();
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.submission_id = submissionId;
    payload.eligible_expenses = expenseInputs.filter(input => input.checked).map(input => input.value);
    for (const name of ['participation_confirmed','guardian_ack','accuracy_ack','privacy_ack','payment_ack','publicity_consent']) {
      payload[name] = !form.elements[name].disabled && form.elements[name].checked;
    }
    sending = true;
    submit.disabled = true;
    submit.textContent = 'Submitting application…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const result = await send(JSON.stringify(payload), controller.signal);
      if (result.ok !== true || result.id !== submissionId) {
        if (result.closed === true) closeApplications();
        throw new Error(typeof result.message === 'string' && result.message ? result.message : 'Your application could not be saved. Your answers are still here; please try again.');
      }
      stored.set(receivedKey, submissionId);
      stored.remove(idKey);
      // Navigate only after the script confirms this exact application was saved.
      // Keep names, email addresses, and answers out of the destination URL.
      location.assign('scholarship-thank-you.html');
    } catch (error) {
      errorBox.textContent = error.name === 'AbortError' ? 'The request took too long. Your answers are still here; please try again. Trying again will not create a duplicate application.' : error instanceof TypeError ? 'We could not reach the application service. Your answers are still here; please try again.' : error.message;
      errorBox.hidden = false;
      errorBox.focus();
    } finally {
      clearTimeout(timeout);
      sending = false;
      submit.disabled = !accepting;
      submit.textContent = 'Submit application';
    }
  });

  updateAgeRequirements();
  validateExpenses();
  const received = stored.get(receivedKey);
  if (received) showReceived(received);
  else showAvailability();
})();
