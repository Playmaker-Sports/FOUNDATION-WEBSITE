"""Signed server-to-server Google Forms adapter; never logs answers or secrets."""

from datetime import datetime
import hashlib
import hmac
import json
import os
import re
import threading
import time
from urllib.parse import urlsplit

import requests


STATUS_CACHE_SECONDS = 60
MAX_REPLY_BYTES = 16 * 1024
REQUEST_TIMEOUT = (5, 25)
STATUS_REASONS = frozenset({'deadline_passed', 'not_configured', 'temporarily_unavailable'})
ERROR_REASONS = STATUS_REASONS | {'conflict', 'closed', 'unavailable', 'unknown'}


class BridgeConfigurationError(RuntimeError):
    """The signed bridge has not been explicitly configured."""


class BridgeError(RuntimeError):
    def __init__(self, reason='unknown'):
        self.reason = reason if reason in ERROR_REASONS else 'unknown'
        # No response text, request parameters, URLs, or credential values.
        super().__init__('Scholarship bridge request could not be verified')


def _settings():
    url = os.environ.get('FOUNDATION_SCHOLARSHIP_BRIDGE_URL', '').strip()
    secret = os.environ.get('FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET', '')
    if not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url):
        raise BridgeConfigurationError('Scholarship bridge URL is not configured')
    if not secret.strip() or not 32 <= len(secret.encode('utf-8')) <= 1024:
        raise BridgeConfigurationError('Scholarship bridge signing key is not configured')
    return url, secret


def _envelope(action, payload, secret):
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    timestamp = int(time.time())
    signed_text = f'1\n{action}\n{timestamp}\n{payload_text}'
    signature = hmac.new(secret.encode('utf-8'), signed_text.encode('utf-8'), hashlib.sha256).hexdigest()
    return {'version': 1, 'action': action, 'timestamp': timestamp,
            'payload': payload_text, 'signature': signature}


def _google_content_redirect(url):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'https' and parsed.hostname == 'script.googleusercontent.com'
                and parsed.username is None and parsed.password is None
                and parsed.port is None and not parsed.fragment)
    except (TypeError, ValueError):
        return False


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-finite JSON value')


def _read_reply(response):
    if response.status_code != 200:
        raise BridgeError('unavailable' if response.status_code in (429, 503) else 'unknown')
    content_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    if content_type != 'application/json':
        raise BridgeError()
    chunks = []
    length = 0
    for chunk in response.iter_content(chunk_size=MAX_REPLY_BYTES):
        length += len(chunk)
        if length > MAX_REPLY_BYTES:
            raise BridgeError()
        chunks.append(chunk)
    try:
        reply = json.loads(b''.join(chunks).decode('utf-8'),
                           object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError):
        raise BridgeError() from None
    if not isinstance(reply, dict) or reply.get('success') is not True:
        reason = reply.get('reason', 'unknown') if isinstance(reply, dict) else 'unknown'
        raise BridgeError(reason if isinstance(reason, str) else 'unknown')
    return reply


def _exchange(url, secret, action, payload):
    response = None
    redirected = None
    try:
        # requests' json= defaults to ASCII escapes. Explicit UTF-8 prevents
        # valid non-ASCII essays growing beyond the receiver's 128 KiB cap.
        body = json.dumps(_envelope(action, payload, secret), ensure_ascii=False,
                          separators=(',', ':')).encode('utf-8')
        response = requests.post(
            url, data=body, headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=REQUEST_TIMEOUT, allow_redirects=False, stream=True,
        )
        if response.status_code in (302, 303):
            location = response.headers.get('Location', '')
            if not _google_content_redirect(location):
                raise BridgeError()
            # ContentService returns its result on this separate Google host.
            # Never forward the signed POST body to any redirect destination.
            redirected = requests.get(location, timeout=REQUEST_TIMEOUT,
                                      allow_redirects=False, stream=True)
        return _read_reply(redirected if redirected is not None else response)
    except requests.RequestException:
        raise BridgeError('unavailable') from None
    finally:
        if response is not None:
            response.close()
        if redirected is not None:
            redirected.close()


class GoogleFormBridge:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def status(self):
        url, secret = _settings()
        key = (url, hashlib.sha256(secret.encode('utf-8')).digest())
        with self._lock:
            if self._cache.get('key') == key and self._cache['expires'] > time.monotonic():
                if self._cache.get('error'):
                    raise BridgeError(self._cache['error'])
                return dict(self._cache['result'])
            try:
                reply = _exchange(url, secret, 'status', {})
                if type(reply.get('accepting_applications')) is not bool:
                    raise BridgeError()
                result = {'accepting_applications': reply['accepting_applications']}
                if not result['accepting_applications']:
                    reason = reply.get('reason')
                    if not isinstance(reason, str) or reason not in STATUS_REASONS:
                        raise BridgeError()
                    result['reason'] = reason
            except BridgeError as error:
                self._cache = {'key': key, 'expires': time.monotonic() + STATUS_CACHE_SECONDS,
                               'error': error.reason}
                raise
            self._cache = {'key': key, 'expires': time.monotonic() + STATUS_CACHE_SECONDS,
                           'result': result}
            return dict(result)

    def submit(self, application):
        url, secret = _settings()
        reply = _exchange(url, secret, 'submit', application)
        if (reply.get('accepted') is not True
                or reply.get('application_id') != application['submission_id']
                or type(reply.get('already_submitted')) is not bool
                or not isinstance(reply.get('response_id'), str)
                or not 1 <= len(reply['response_id']) <= 300):
            raise BridgeError()
        submitted_at = reply.get('submitted_at')
        try:
            if not isinstance(submitted_at, str) or not re.fullmatch(
                    r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', submitted_at):
                raise ValueError
            parsed = datetime.fromisoformat(submitted_at)
            if parsed.utcoffset() is None:
                raise ValueError
        except ValueError:
            raise BridgeError() from None
        # Google response/edit identifiers never leave this server.
        return {'success': True, 'application_id': application['submission_id'],
                'submitted_at': submitted_at, 'already_submitted': reply['already_submitted']}
