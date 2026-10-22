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
  const submissionId = crypto.randomUUID();
  let sending = false;

  // Sends the message, trying again when Google's reply is garbled (right after
  // a script update it can briefly return an error page or the wrong reply even
  // though the save worked).
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
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const result = await send(JSON.stringify(payload), controller.signal);
      if (result.ok !== true || result.id !== submissionId) {
        throw new Error(typeof result.message === 'string' && result.message ? result.message : 'Your message could not be sent. It is still here; please try again.');
      }
      // Thank the sender only after the script confirms this exact message was saved.
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
})();
