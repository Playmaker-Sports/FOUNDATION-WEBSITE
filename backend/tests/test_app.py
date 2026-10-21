"""Standalone Foundation entrypoint checks; no live services or applicant data."""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import Mock, patch

from app import MAX_REQUEST_BYTES, create_app
import foundation_scholarships as scholarships
from test_foundation_scholarships import valid_application


ROUTE = '/api/foundation/scholarship-applications'


class FoundationAppTests(unittest.TestCase):
    def setUp(self):
        clock = patch.object(scholarships, 'utc_now', return_value=datetime(2026, 10, 20, tzinfo=timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        self.env = patch.dict(os.environ, {
            # Exercise the preserved fallback deliberately; production defaults
            # to retired and has separate no-opt-in tests below.
            'FOUNDATION_SCHOLARSHIP_API_ENABLED': 'true',
            'FOUNDATION_SCHOLARSHIP_SHEET_ID': '',
            'GOOGLE_CREDENTIALS': '',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.adapters = {
            name: Mock(side_effect=AssertionError('No external service should be used'))
            for name in ('load_credentials', 'build_service', 'authorized_http')
        }
        self.app = create_app({'TESTING': True, 'RATELIMIT_ENABLED': False}, **self.adapters)
        self.client = self.app.test_client()

    def test_startup_and_health_need_no_credentials_google_or_email(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok', 'service': 'foundation-scholarship-api'})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        for adapter in self.adapters.values():
            adapter.assert_not_called()
        self.assertNotIn('PlaymakerSportsApp_API', sys.modules)
        self.assertNotIn('ops_app', sys.modules)

    def test_only_foundation_intake_and_health_routes_exist(self):
        self.assertEqual({str(rule) for rule in self.app.url_map.iter_rules()}, {
            '/health', ROUTE, f'{ROUTE}/status',
        })
        for path in ('/', '/api/events', '/api/contact', '/api/foundation/registrations', '/api/force-refresh/100'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertFalse(response.json['success'])

    def test_missing_configuration_never_advertises_accepting(self):
        response = self.client.get(f'{ROUTE}/status')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['accepting_applications'])
        self.assertNotIn('email_configured', response.json)
        self.assertEqual(response.json['reason'], 'not_configured')
        self.adapters['load_credentials'].assert_not_called()

    def test_retired_by_default_rejects_before_json_or_google_even_with_old_config(self):
        with patch.dict(os.environ, {
            'FOUNDATION_SCHOLARSHIP_SHEET_ID': 'private-test-sheet',
            'GOOGLE_CREDENTIALS': 'not-read-retired-placeholder',
        }), patch('flask.wrappers.Request.get_json', side_effect=AssertionError('Do not parse retired submissions')):
            os.environ.pop('FOUNDATION_SCHOLARSHIP_API_ENABLED', None)
            status = self.client.get(f'{ROUTE}/status', headers={'Origin': scholarships.FOUNDATION_ORIGINS[0]})
            response = self.client.post(ROUTE, data='not-json', content_type='application/json',
                                        headers={'Origin': scholarships.FOUNDATION_ORIGINS[0]})
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json['accepting_applications'])
        self.assertEqual(status.json['reason'], 'intake_retired')
        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.json['success'])
        self.assertEqual(response.json['reason'], 'intake_retired')
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], scholarships.FOUNDATION_ORIGINS[0])
        self.assertEqual(self.client.get('/health').status_code, 200)
        for adapter in self.adapters.values():
            adapter.assert_not_called()

    def test_api_rollback_requires_exact_explicit_true(self):
        for value in ('', 'false', '0', '1', 'yes', 'TRUE', 'enabled'):
            with self.subTest(value=value), patch.dict(os.environ, {'FOUNDATION_SCHOLARSHIP_API_ENABLED': value}):
                self.assertEqual(self.client.get(f'{ROUTE}/status').json['reason'], 'intake_retired')
                self.assertEqual(self.client.post(ROUTE, json=valid_application()).status_code, 410)
        for adapter in self.adapters.values():
            adapter.assert_not_called()

    def test_sheet_readiness_is_not_a_write_or_notification_check(self):
        self.adapters['load_credentials'].side_effect = None
        self.adapters['build_service'].side_effect = None
        self.adapters['authorized_http'].side_effect = None
        values = self.adapters['build_service'].return_value.spreadsheets.return_value.values.return_value
        values.get.return_value.execute.return_value = {'values': [list(scholarships.SHEET_COLUMNS)]}
        with patch.dict(os.environ, {
            'FOUNDATION_SCHOLARSHIP_SHEET_ID': 'private-test-sheet',
        }):
            response = self.client.get(f'{ROUTE}/status')
        self.assertTrue(response.json['accepting_applications'])
        self.assertNotIn('email_configured', response.json)
        values.append.assert_not_called()

    def test_oversize_request_returns_json_413_with_foundation_cors(self):
        response = self.client.post(
            ROUTE, data=b'x' * (MAX_REQUEST_BYTES + 1), content_type='application/json',
            headers={'Origin': scholarships.FOUNDATION_ORIGINS[0]},
        )
        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.json['success'])
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], scholarships.FOUNDATION_ORIGINS[0])
        self.adapters['load_credentials'].assert_not_called()

    def test_request_cap_accepts_maximum_length_unicode_responses(self):
        payload = valid_application(
            growth='\U0001f3c6' * 5000, challenge='\U0001f3c6' * 5000,
            goals='\U0001f3c6' * 5000, financial_need='\U0001f3c6' * 5000,
            additional_context='\U0001f3c6' * 3000,
        )
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.assertGreater(len(body), 64 * 1024)
        self.assertLess(len(body), MAX_REQUEST_BYTES)
        response = self.client.post(ROUTE, data=body, content_type='application/json')
        # Parsed/validated successfully; missing configuration (not body size)
        # prevents storage in this offline startup test.
        self.assertEqual(response.status_code, 503)
        self.adapters['load_credentials'].assert_not_called()

    def test_unexpected_errors_and_logs_do_not_echo_private_values(self):
        @self.app.get('/test-error')
        def broken_route():
            raise ValueError('PRIVATE_APPLICANT_RESPONSE_AND_SECRET')

        with self.assertLogs('app', level='ERROR') as captured:
            response = self.client.get('/test-error')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('PRIVATE_APPLICANT', response.get_data(as_text=True))
        self.assertNotIn('PRIVATE_APPLICANT', '\n'.join(captured.output))
        self.assertIn('ValueError', '\n'.join(captured.output))

    def test_proxy_last_hop_is_used_for_rate_limits_and_health_is_exempt(self):
        client = create_app({'TESTING': True}, **self.adapters).test_client()
        responses = [client.post(ROUTE, json={}, headers={
            'X-Forwarded-For': f'198.51.100.{index}, 203.0.113.10',
            'X-Forwarded-Proto': 'https',
        }) for index in range(6)]
        self.assertEqual([response.status_code for response in responses], [400] * 5 + [429])
        other = client.post(ROUTE, json={}, headers={'X-Forwarded-For': '203.0.113.11'})
        self.assertEqual(other.status_code, 400)
        self.assertTrue(all(client.get('/health').status_code == 200 for _ in range(65)))

    def test_gunicorn_keeps_one_worker_four_threads_and_no_request_logs(self):
        config = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'gunicorn.conf.py'))
        self.assertEqual(config['workers'], 1)
        self.assertEqual(config['threads'], 4)
        self.assertEqual(config['timeout'], 120)
        self.assertIsNone(config['accesslog'])


if __name__ == '__main__':
    unittest.main()
