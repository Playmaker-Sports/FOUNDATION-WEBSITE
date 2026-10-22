(() => {
  'use strict';
  const form = document.getElementById('contactForm');
  if (!form) return;
  const submit = form.querySelector('[type="submit"]');
  const errorBox = document.getElementById('contactError');
  const success = document.getElementById('formSuccess');
  // The form's action is the Foundation's contact Apps Script web app, which
  // saves each message to the contact Sheet and emails staff (CONTACT_SETUP.md).
  const endpoint = (() => {
    try {
      const url = new URL(form.getAttribute('action') || '');
      return url.protocol === 'https:' && url.hostname === 'script.google.com' && !url.search && !url.hash &&
        /^\/(?:a\/macros\/[^/]+|macros)\/s\/[\w-]+\/exec$/.test(url.pathname) ? url.href : null;
    } catch { return null; }
  })();
  // A retry of the same message reuses its ID, so the script never saves it twice.
  let submissionId = crypto.randomUUID();
  let sending = false;

  if (!endpoint) {
    submit.disabled = true;
    document.getElementById('contactNotice').hidden = false;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!endpoint || sending) return;
    errorBox.hidden = true;
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.submission_id = submissionId;
    sending = true;
    submit.disabled = true;
    submit.textContent = 'Sending…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      // A text/plain body keeps this a simple cross-site request; Apps Script
      // cannot answer the preflight that an application/json body triggers.
      const response = await fetch(endpoint, { method:'POST', headers:{ 'Content-Type':'text/plain;charset=utf-8' }, body:JSON.stringify(payload), signal:controller.signal });
      const result = await response.json().catch(() => ({}));
      if (result.ok !== true || result.id !== submissionId) {
        throw new Error(typeof result.message === 'string' && result.message ? result.message : 'Your message could not be sent. It is still here; please try again.');
      }
      // Thank the sender only after the script confirms this exact message was saved.
      submissionId = crypto.randomUUID();
      form.reset();
      form.hidden = true;
      success.hidden = false;
      success.focus({ preventScroll: true });
      // Hiding the form shortens the page, which can leave the thank-you off screen.
      success.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (error) {
      errorBox.textContent = error.name === 'AbortError' ? 'Sending took too long. Your message is still here; please try again. Trying again will not send it twice.' : error instanceof TypeError ? 'We could not reach the contact form. Your message is still here; please try again, or email info@playmakersportsfoundation.org.' : error.message;
      errorBox.hidden = false;
      errorBox.focus();
    } finally {
      clearTimeout(timeout);
      sending = false;
      submit.disabled = false;
      submit.textContent = 'Send Message';
    }
  });

  document.getElementById('sendAnother').addEventListener('click', () => {
    success.hidden = true;
    form.hidden = false;
    form.elements.first_name.focus();
  });
})();
