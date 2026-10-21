"""Signed Google Forms relay checks: all HTTP and Google dependencies are mocked."""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import Mock, patch

import requests

from app import create_app
import foundation_scholarships as scholarships
import google_form_bridge as bridge_module
from test_foundation_scholarships import valid_application


ROUTE = '/api/foundation/scholarship-applications'
BRIDGE_URL = 'https://script.google.com/macros/s/test-only-not-a-deployment-id/exec'
SECRET = 'test-only-signing-key-0123456789abcdef'
NOW = datetime(2026, 10, 20, 23, 0, tzinfo=timezone.utc)


def http_response(reply=None, *, status=200, headers=None, raw=None):
    response = Mock()
    response.status_code = status
    response.headers = {'Content-Type': 'application/json; charset=utf-8'} if headers is None else headers
    body = json.dumps(reply).encode('utf-8') if raw is None else raw
    response.iter_content.return_value = [body]
    return response


def accepted_reply(application, **changes):
    return dict({
        'success': True, 'accepted': True,
        'application_id': application['submission_id'],
        'submitted_at': '2026-10-20T23:00:00.000Z',
        'already_submitted': False, 'response_id': 'private-google-response-id',
    }, **changes)


class GoogleFormBridgeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'FOUNDATION_SCHOLARSHIP_API_ENABLED': 'true',
            'FOUNDATION_SCHOLARSHIP_STORE': 'google_form',
            'FOUNDATION_SCHOLARSHIP_BRIDGE_URL': BRIDGE_URL,
            'FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET': SECRET,
            'GOOGLE_CREDENTIALS': '',
            # A leftover sheet configuration must never cause silent fallback.
            'FOUNDATION_SCHOLARSHIP_SHEET_ID': 'private-unused-sheet',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        clock = patch.object(scholarships, 'utc_now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.adapters = {name: Mock(side_effect=AssertionError('No Sheets API access'))
                         for name in ('load_credentials', 'build_service', 'authorized_http')}
        self.client = create_app({'TESTING': True, 'RATELIMIT_ENABLED': False}, **self.adapters).test_client()
        post_patch = patch.object(bridge_module.requests, 'post')
        get_patch = patch.object(bridge_module.requests, 'get')
        self.post = post_patch.start()
        self.get = get_patch.start()
        self.addCleanup(post_patch.stop)
        self.addCleanup(get_patch.stop)

    def assert_no_sheet_calls(self):
        for adapter in self.adapters.values():
            adapter.assert_not_called()

    def test_signed_status_and_cleaned_utf8_submission_contract(self):
        application = valid_application(applicant_name='  Jos\u00e9 Player  ')
        self.post.side_effect = [http_response({'success': True, 'accepting_applications': True}),
                                 http_response(accepted_reply(application))]
        with patch.object(bridge_module.time, 'time', return_value=1792537200):
            status = self.client.get(f'{ROUTE}/status')
            response = self.client.post(ROUTE, json=application)
        self.assertTrue(status.json['accepting_applications'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'success': True, 'application_id': application['submission_id'],
            'submitted_at': '2026-10-20T23:00:00.000Z', 'already_submitted': False,
        })
        self.assertNotIn('response_id', response.json)
        self.assertNotIn(SECRET, response.get_data(as_text=True))
        for call, action in zip(self.post.call_args_list, ('status', 'submit'), strict=True):
            self.assertEqual(call.args, (BRIDGE_URL,))
            self.assertEqual(call.kwargs['timeout'], (5, 25))
            self.assertFalse(call.kwargs['allow_redirects'])
            self.assertTrue(call.kwargs['stream'])
            self.assertEqual(call.kwargs['headers'], {'Content-Type': 'application/json; charset=utf-8'})
            self.assertIsInstance(call.kwargs['data'], bytes)
            envelope = json.loads(call.kwargs['data'].decode('utf-8'))
            self.assertEqual(set(envelope), {'version', 'action', 'timestamp', 'payload', 'signature'})
            self.assertEqual(envelope['action'], action)
            self.assertEqual(envelope['version'], 1)
            self.assertEqual(envelope['timestamp'], 1792537200)
            expected = hmac.new(SECRET.encode(), f"1\n{action}\n1792537200\n{envelope['payload']}".encode(), hashlib.sha256).hexdigest()
            self.assertEqual(envelope['signature'], expected)
            payload = json.loads(envelope['payload'])
            if action == 'status':
                self.assertEqual(envelope['payload'], '{}')
            else:
                self.assertEqual(payload['applicant_name'], 'Jos\u00e9 Player')
                self.assertNotIn('_honey', payload)
                self.assertEqual(payload['submission_id'], application['submission_id'])
                self.assertEqual(envelope['payload'], json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        self.get.assert_not_called()
        self.assert_no_sheet_calls()

    def test_maximum_unicode_essays_fit_the_receiver_envelope_limit(self):
        application = valid_application(
            growth='\U0001f3c6' * 5000, challenge='\U0001f3c6' * 5000,
            goals='\U0001f3c6' * 5000, financial_need='\U0001f3c6' * 5000,
            additional_context='\U0001f3c6' * 3000,
        )
        self.post.return_value = http_response(accepted_reply(application))
        request_body = json.dumps(application, ensure_ascii=False).encode('utf-8')
        self.assertEqual(self.client.post(ROUTE, data=request_body, content_type='application/json').status_code, 200)
        body = self.post.call_args.kwargs['data']
        self.assertLess(len(body), 128 * 1024)
        envelope = json.loads(body.decode('utf-8'))
        self.assertEqual(json.loads(envelope['payload'])['growth'], application['growth'])

    def test_del_control_character_is_rejected_before_bridge(self):
        response = self.client.post(ROUTE, json=valid_application(city='Moorpark\x7f'))
        self.assertEqual(response.status_code, 400)
        self.post.assert_not_called()

    def test_native_city_and_club_team_length_limits_are_enforced(self):
        for field, limit in (('city', 120), ('club_team', 250)):
            with self.subTest(field=field):
                application = valid_application(**{field: 'x' * limit})
                self.post.return_value = http_response(accepted_reply(application))
                self.assertEqual(self.client.post(ROUTE, json=application).status_code, 200)
                self.assertEqual(self.client.post(ROUTE, json=valid_application(**{field: 'x' * (limit + 1)})).status_code, 400)

    def test_google_content_redirect_is_get_only_without_post_credentials(self):
        application = valid_application()
        location = 'https://script.googleusercontent.com/macros/echo?user_content_key=test-only'
        initial = http_response(status=302, headers={'Location': location})
        final = http_response(accepted_reply(application))
        self.post.return_value = initial
        self.get.return_value = final
        self.assertEqual(self.client.post(ROUTE, json=application).status_code, 200)
        self.get.assert_called_once_with(location, timeout=(5, 25), allow_redirects=False, stream=True)
        initial.close.assert_called_once()
        final.close.assert_called_once()
        self.assert_no_sheet_calls()

    def test_rejects_all_untrusted_redirects_and_never_reposts(self):
        for location in ('https://evil.example/exec', 'http://script.googleusercontent.com/echo',
                         'https://script.googleusercontent.com.evil.example/echo',
                         'https://user@script.googleusercontent.com/echo',
                         'https://script.googleusercontent.com:444/echo',
                         'https://script.google.com/macros/s/other/exec', '/relative', ''):
            with self.subTest(location=location):
                self.post.return_value = http_response(status=302, headers={'Location': location})
                response = self.client.post(ROUTE, json=valid_application())
                self.assertEqual(response.status_code, 502)
                self.assertFalse(response.json['success'])
        self.assertEqual(self.post.call_count, 8)
        self.get.assert_not_called()
        self.assert_no_sheet_calls()

    def test_redirect_chain_and_post_preserving_redirects_are_rejected(self):
        location = 'https://script.googleusercontent.com/macros/echo?test=1'
        for status in (301, 307, 308):
            with self.subTest(status=status):
                self.post.return_value = http_response(status=status, headers={'Location': location})
                self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 502)
        self.get.assert_not_called()
        self.post.return_value = http_response(status=303, headers={'Location': location})
        self.get.return_value = http_response(status=302, headers={'Location': location})
        self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 502)
        self.get.assert_called_once()

    def test_configuration_must_choose_mode_and_valid_bridge_explicitly(self):
        cases = (
            {'FOUNDATION_SCHOLARSHIP_STORE': ''}, {'FOUNDATION_SCHOLARSHIP_STORE': 'auto'},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_URL': ''},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_URL': 'http://script.google.com/macros/s/id/exec'},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_URL': 'https://evil.example/macros/s/id/exec'},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_URL': BRIDGE_URL + '?secret=not-allowed'},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_URL': BRIDGE_URL.replace('/exec', '/dev')},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET': 'x' * 31},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET': 'x' * 1025},
            {'FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET': ' ' * 32},
        )
        for settings in cases:
            with self.subTest(settings=settings), patch.dict(os.environ, settings):
                self.assertEqual(self.client.get(f'{ROUTE}/status').json['reason'], 'not_configured')
                response = self.client.post(ROUTE, json=valid_application())
                self.assertEqual(response.status_code, 503)
                self.assertFalse(response.json['success'])
        self.post.assert_not_called()
        self.get.assert_not_called()
        self.assert_no_sheet_calls()

    def test_disabled_api_ignores_otherwise_complete_bridge_configuration(self):
        with patch.dict(os.environ, {'FOUNDATION_SCHOLARSHIP_API_ENABLED': ''}):
            self.assertEqual(self.client.get(f'{ROUTE}/status').json['reason'], 'intake_retired')
            self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 410)
        self.post.assert_not_called()
        self.assert_no_sheet_calls()

    def test_status_cache_avoids_quota_amplification_and_expires_after_60_seconds(self):
        self.post.return_value = http_response({'success': True, 'accepting_applications': True})
        with patch.object(bridge_module.time, 'monotonic', side_effect=(100, 110, 161, 161)):
            for unused in range(3):
                self.assertTrue(self.client.get(f'{ROUTE}/status').json['accepting_applications'])
        self.assertEqual(self.post.call_count, 2)

    def test_status_failures_are_cached_and_never_advertise_acceptance(self):
        self.post.side_effect = requests.Timeout('PRIVATE_VALUE_AND_SECRET')
        with patch.object(bridge_module.time, 'monotonic', return_value=100):
            for unused in range(2):
                response = self.client.get(f'{ROUTE}/status')
                self.assertFalse(response.json['accepting_applications'])
                self.assertEqual(response.json['reason'], 'temporarily_unavailable')
        self.post.assert_called_once()
        self.assert_no_sheet_calls()

    def test_rotating_bridge_secret_invalidates_status_cache(self):
        self.post.return_value = http_response({'success': True, 'accepting_applications': True})
        self.assertTrue(self.client.get(f'{ROUTE}/status').json['accepting_applications'])
        with patch.dict(os.environ, {'FOUNDATION_SCHOLARSHIP_BRIDGE_SECRET': 'new-test-only-signing-key-0123456789abcdef'}):
            self.assertTrue(self.client.get(f'{ROUTE}/status').json['accepting_applications'])
        self.assertEqual(self.post.call_count, 2)

    def test_status_false_reasons_are_verified_not_coerced(self):
        for reason in ('deadline_passed', 'not_configured', 'temporarily_unavailable'):
            with self.subTest(reason=reason):
                adapter = bridge_module.GoogleFormBridge()
                self.post.return_value = http_response({'success': True, 'accepting_applications': False, 'reason': reason})
                self.assertEqual(adapter.status(), {'accepting_applications': False, 'reason': reason})
        for reply in ({'success': True, 'accepting_applications': 'true'},
                      {'success': True, 'accepting_applications': False},
                      {'success': True, 'accepting_applications': False, 'reason': 'PRIVATE'}):
            with self.subTest(reply=reply):
                self.post.return_value = http_response(reply)
                with self.assertRaises(bridge_module.BridgeError):
                    bridge_module.GoogleFormBridge().status()

    def test_submit_errors_map_to_safe_http_statuses_without_fallback_or_private_text(self):
        for reason, expected in (('conflict', 409), ('closed', 410), ('deadline_passed', 410),
                                 ('unavailable', 503), ('not_configured', 503),
                                 ('temporarily_unavailable', 503), ('PRIVATE_SECRET', 502)):
            with self.subTest(reason=reason):
                self.post.return_value = http_response({'success': False, 'reason': reason, 'message': 'PRIVATE_ESSAY'})
                response = self.client.post(ROUTE, json=valid_application())
                self.assertEqual(response.status_code, expected)
                self.assertFalse(response.json['success'])
                self.assertNotIn('PRIVATE', response.get_data(as_text=True))
        self.assert_no_sheet_calls()

    def test_only_verified_submit_success_reaches_the_client(self):
        application = valid_application()
        changes = ({'accepted': False}, {'accepted': 'true'}, {'application_id': 'wrong-uuid'},
                   {'submitted_at': ''}, {'submitted_at': '2026-10-20T23:00:00'},
                   {'submitted_at': '2026-02-30T23:00:00Z'}, {'already_submitted': 0},
                   {'response_id': ''}, {'response_id': 123})
        for change in changes:
            with self.subTest(change=change):
                self.post.return_value = http_response(accepted_reply(application, **change))
                response = self.client.post(ROUTE, json=application)
                self.assertEqual(response.status_code, 502)
                self.assertFalse(response.json['success'])
        self.assert_no_sheet_calls()

    def test_duplicate_success_is_preserved_without_exposing_google_id(self):
        application = valid_application()
        self.post.return_value = http_response(accepted_reply(application, already_submitted=True))
        response = self.client.post(ROUTE, json=application)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['already_submitted'])
        self.assertNotIn('response_id', response.json)

    def test_http_errors_malformed_json_html_duplicate_keys_and_oversize_fail_closed(self):
        cases = [
            http_response(status=500), http_response(status=503),
            http_response(raw=b'not json'), http_response(reply=[]),
            http_response(raw=b'{"success":true,"success":false}'),
            http_response(raw=b'{"success":true,"value":NaN}'),
            http_response(raw=b'\xff'), http_response(raw=b'x' * (bridge_module.MAX_REPLY_BYTES + 1)),
            http_response({'success': True}, headers={'Content-Type': 'text/html'}),
            http_response({'success': 1}),
        ]
        for reply in cases:
            with self.subTest(reply=reply):
                self.post.return_value = reply
                response = self.client.post(ROUTE, json=valid_application())
                self.assertIn(response.status_code, (502, 503))
                self.assertFalse(response.json['success'])
        self.assert_no_sheet_calls()

    def test_deadline_validation_and_honeypot_do_not_contact_bridge(self):
        self.assertEqual(self.client.post(ROUTE, json={'_honey': 'spam'}).status_code, 400)
        self.assertEqual(self.client.post(ROUTE, json=valid_application(privacy_ack=False)).status_code, 400)
        with patch.object(scholarships, 'utc_now', return_value=datetime(2026, 11, 21, 8, tzinfo=timezone.utc)):
            self.assertEqual(self.client.get(f'{ROUTE}/status').json['reason'], 'deadline_passed')
            self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 410)
        self.post.assert_not_called()
        self.assert_no_sheet_calls()

    def test_network_timeout_returns_safe_503_and_logs_no_answers_or_secrets(self):
        self.post.side_effect = requests.Timeout('PRIVATE_ESSAY_AND_SIGNING_SECRET')
        with self.assertLogs('foundation_scholarships', level='WARNING') as logs:
            response = self.client.post(ROUTE, json=valid_application())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json['success'])
        self.assertNotIn('PRIVATE', '\n'.join(logs.output))
        self.assertNotIn(SECRET, '\n'.join(logs.output))
        self.assert_no_sheet_calls()

    def test_status_and_post_keep_their_public_per_ip_limits(self):
        self.post.return_value = http_response({'success': True, 'accepting_applications': True})
        client = create_app({'TESTING': True}, **self.adapters).test_client()
        responses = [client.get(f'{ROUTE}/status') for unused in range(61)]
        self.assertTrue(all(response.status_code == 200 for response in responses[:60]))
        self.assertEqual(responses[-1].status_code, 429)
        self.post.assert_called_once()
        responses = [client.post(ROUTE, json={}) for unused in range(6)]
        self.assertEqual([response.status_code for response in responses], [400] * 5 + [429])
        self.post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
