(() => {
  'use strict';
  const form = document.getElementById('scholarship-form');
  const submit = document.getElementById('submit-application');
  const statusMessage = document.getElementById('availability-message');
  const statusBox = document.getElementById('availability');
  const retryStatus = document.getElementById('retry-availability');
  const errorBox = document.getElementById('form-error');
  const success = document.getElementById('application-success');
  const dob = document.getElementById('dob');
  const expenseInputs = [...form.querySelectorAll('[name="eligible_expenses"]')];
  const localPreview = location.protocol === 'file:';
  const deadlineExclusive = Date.parse('2026-11-21T00:00:00-08:00');
  const idKey = 'foundation-cup-2026-submission-id';
  const receivedKey = 'foundation-cup-2026-received-id';
  let accepting = false;
  let sending = false;
  let checking = false;
  let availabilityGeneration = 0;

  const stored = {
    get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, value); } catch { /* Session storage is optional. */ } },
    remove(key) { try { sessionStorage.removeItem(key); } catch { /* Session storage is optional. */ } }
  };
  let submissionId = stored.get(idKey) || crypto.randomUUID();
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
    expenseInputs[0].setCustomValidity(expenseInputs.some(input => input.checked) ? '' : 'Choose at least one expense the assistance would help cover.');
  }

  function showReceived(reference, confirmationSent = null) {
    accepting = false;
    form.hidden = true;
    statusBox.hidden = true;
    success.hidden = false;
    document.getElementById('application-reference').textContent = reference;
    document.getElementById('confirmation-email-status').textContent = confirmationSent === true ? 'A thank-you email has been sent to your contact email. If you do not see it, check your spam folder. Keep this reference for your records.' : confirmationSent === false ? 'Your application was saved, but we could not confirm the thank-you email was sent. Keep this reference; you do not need to submit again.' : 'Keep this reference even if you do not receive a thank-you email. You do not need to submit again.';
  }

  async function checkAvailability() {
    if (checking || sending || !success.hidden) return;
    checking = true;
    accepting = false;
    submit.disabled = true;
    retryStatus.hidden = true;
    const generation = ++availabilityGeneration;
    if (localPreview) {
      form.hidden = false;
      statusMessage.textContent = 'Local preview. You can review the form here, but applications cannot be submitted from this file.';
      checking = false;
      return;
    }
    if (Date.now() >= deadlineExclusive) {
      statusMessage.textContent = 'Applications closed on November 20, 2026, at 11:59 p.m. Pacific.';
      form.hidden = true;
      checking = false;
      return;
    }
    statusMessage.textContent = 'Checking application availability…';
    form.hidden = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${form.action}/status`, { headers:{ Accept:'application/json' }, signal:controller.signal, cache:'no-store' });
      const result = await response.json();
      if (generation !== availabilityGeneration || !success.hidden) return;
      if (!response.ok || result.accepting_applications !== true) {
        const closed = result.reason === 'deadline_passed';
        statusMessage.textContent = closed ? 'Applications closed on November 20, 2026, at 11:59 p.m. Pacific.' : result.reason === 'temporarily_unavailable' ? 'The application service is temporarily unavailable. Please try again shortly or contact info@playmakersportsfoundation.org.' : 'Applications are not available yet. Please check back or contact info@playmakersportsfoundation.org for assistance.';
        retryStatus.hidden = closed;
        return;
      }
      accepting = true;
      form.hidden = false;
      submit.disabled = false;
      statusMessage.textContent = 'Apply by November 20, 2026, at 11:59 p.m. Pacific. No receipt uploads are needed with your application.';
    } catch {
      if (generation !== availabilityGeneration || !success.hidden) return;
      statusMessage.textContent = 'We could not check application availability. Please try again or contact info@playmakersportsfoundation.org.';
      retryStatus.hidden = false;
    } finally {
      clearTimeout(timeout);
      checking = false;
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
  retryStatus.addEventListener('click', checkAvailability);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!accepting || localPreview || sending) return;
    errorBox.hidden = true;
    if (Date.now() >= deadlineExclusive) {
      accepting = false;
      submit.disabled = true;
      errorBox.textContent = 'The application deadline has passed. Applications closed November 20, 2026, at 11:59 p.m. Pacific.';
      errorBox.hidden = false;
      errorBox.focus();
      return;
    }
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
    submit.textContent = 'Saving application…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(form.action, { method:'POST', headers:{ 'Accept':'application/json', 'Content-Type':'application/json' }, body:JSON.stringify(payload), signal:controller.signal });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.success !== true) {
        if (response.status === 410 || response.status === 409) accepting = false;
        const fieldNames = { applicant_name:'Player’s full name', date_of_birth:'Date of birth', grade_level:'Grade level', city:'City', school:'Current school', guardian_name:'Parent/guardian name', guardian_email:'Parent/guardian email', applicant_email:'Applicant email', club_team:'Club and team', team_age_group:'Team age group', growth:'Soccer and personal growth response', challenge:'Challenge response', goals:'Future goals response', financial_need:'Financial need response', eligible_expenses:'Expense selection', guardian_ack:'Parent/guardian acknowledgment', participation_confirmed:'Cup participation confirmation', accuracy_ack:'Accuracy acknowledgment', privacy_ack:'Privacy acknowledgment', payment_ack:'Reimbursement acknowledgment' };
        let message = response.status === 429 ? 'Too many attempts. Please wait a minute and try again.' : response.status === 410 ? 'Applications have closed. The deadline was November 20, 2026, at 11:59 p.m. Pacific.' : response.status === 503 ? 'Applications are temporarily unavailable. Please try again later or email the Foundation.' : 'Your application could not be saved. Your answers are still here; please try again.';
        if (response.status === 409) message = `An earlier version of this application was already saved under reference ${submissionId}. The changes currently shown have not been saved. Please email info@playmakersportsfoundation.org with this reference to request a correction; do not submit a second application.`;
        if (response.status === 400 && typeof result.message === 'string') {
          const field = Object.keys(fieldNames).find(name => result.message.startsWith(name));
          if (field) message = `Please check ${fieldNames[field]}. ${result.message.includes('too long') ? 'Please shorten the response.' : 'Complete the field or correct its value, then try again.'}`;
        }
        throw new Error(message);
      }
      const reference = result.application_id || submissionId;
      stored.set(receivedKey, reference);
      stored.remove(idKey);
      showReceived(reference, result.already_submitted ? null : typeof result.confirmation_sent === 'boolean' ? result.confirmation_sent : null);
      form.reset();
      success.focus();
      success.scrollIntoView({ behavior:'smooth', block:'start' });
    } catch (error) {
      errorBox.textContent = error.name === 'AbortError' ? 'The request took too long. Your answers are still here. Please retry; your application reference is reused to avoid duplicate submissions.' : error.message === 'Failed to fetch' ? 'We could not reach the application service. Your answers are still here; please try again.' : error.message;
      errorBox.hidden = false;
      errorBox.focus();
    } finally {
      clearTimeout(timeout);
      sending = false;
      submit.disabled = !accepting;
      submit.textContent = 'Submit application';
    }
  });

  document.getElementById('another-application').addEventListener('click', () => {
    stored.remove(receivedKey);
    submissionId = crypto.randomUUID();
    stored.set(idKey, submissionId);
    form.reset();
    errorBox.hidden = true;
    success.hidden = true;
    statusBox.hidden = false;
    updateAgeRequirements();
    for (const counter of document.querySelectorAll('[data-count-for]')) counter.textContent = '0 words';
    checkAvailability();
    document.getElementById('application-title').scrollIntoView({ behavior:'smooth', block:'start' });
  });
  updateAgeRequirements();
  validateExpenses();
  const received = stored.get(receivedKey);
  if (received) showReceived(received);
  else checkAvailability();
})();
