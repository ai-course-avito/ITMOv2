import json
import logging
import unittest
from uuid import UUID

import httpx

from app.api import create_app
from app.config import Settings
from app.errors import ReviewError
from app.review import ReviewService
from tests.test_logic import FakeAdapter, SIMPLE, TRAINING, candidate


class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake = FakeAdapter()
        self.service = ReviewService(Settings(), self.fake)
        self.app = create_app(service=self.service)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        value = response.json()
        UUID(value['request_id'])
        self.assertEqual(set(value), {'request_id', 'error'})
        self.assertEqual(set(value['error']), {'code', 'message'})
        self.assertEqual(value['error']['code'], code)
        self.assertIsInstance(value['error']['message'], str)
        return value

    async def test_success_envelope(self):
        response = await self.client.post('/api/reviews', json={'diff': SIMPLE})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        UUID(body['request_id'])
        self.assertEqual(set(body), {'request_id', 'mode', 'summary', 'risks', 'checks'})
        self.assertEqual(body['mode'], 'demo')
        self.assertEqual(len(self.fake.calls), 1)

    async def test_content_type_json_shape_and_order(self):
        cases = [({'content': 'x'}, 415, 'UNSUPPORTED_MEDIA_TYPE'),
                 ({'content': '{', 'headers': {'content-type': 'application/json'}}, 400, 'INVALID_JSON'),
                 ({'json': []}, 422, 'INVALID_REQUEST'),
                 ({'json': {'diff': None}}, 422, 'INVALID_REQUEST'),
                 ({'json': {'diff': True}}, 422, 'INVALID_REQUEST'),
                 ({'json': {'diff': SIMPLE, 'mode': 'live'}}, 422, 'INVALID_REQUEST'),
                 ({'json': {'diff': ''}}, 422, 'INVALID_REQUEST'),
                 ({'json': {'diff': ' '*20001}}, 413, 'DIFF_TOO_LARGE'),
                 ({'json': {'diff': ' '*20}}, 422, 'INVALID_REQUEST'),
                 ({'json': {'diff': 'not a diff'}}, 422, 'INVALID_DIFF'),
                 ({'json': {'diff': 'diff --cc a\n@@@ -1 -1 +1 @@@'}}, 422, 'UNSUPPORTED_DIFF')]
        for kwargs, status, code in cases:
            with self.subTest(code=code):
                self.assert_error(await self.client.post('/api/reviews', **kwargs), status, code)
        self.assertEqual(self.fake.calls, [])

    async def test_exact_limit_emoji_and_crlf(self):
        base = '--- a/a\r\n+++ b/a\r\n@@ -1 +1 @@\r\n-old\r\n+'
        valid = base + '😀'*(20000-len(base))
        response = await self.client.post('/api/reviews', json={'diff': valid})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.fake.calls), 1)
        self.assert_error(await self.client.post('/api/reviews', json={'diff': valid+'x'}), 413, 'DIFF_TOO_LARGE')
        self.assertEqual(len(self.fake.calls), 1)

    async def test_invalid_model_response_is_atomic(self):
        self.fake.answer = candidate(); self.fake.answer['risks'] *= 4
        self.assert_error(await self.client.post('/api/reviews', json={'diff': SIMPLE}), 502, 'INVALID_MODEL_OUTPUT')

    async def test_invalid_unicode_input_does_not_call_model(self):
        body = json.dumps({'diff': SIMPLE.replace('+new()', '+\ud800')})
        response = await self.client.post('/api/reviews', content=body,
                                          headers={'content-type': 'application/json'})
        self.assert_error(response, 422, 'INVALID_REQUEST')
        self.assertEqual(self.fake.calls, [])

    async def test_invalid_unicode_model_text_is_rejected_atomically(self):
        for field in ['summary', 'risk', 'checks']:
            answer = candidate()
            if field == 'risk':
                answer['risks'][0]['risk'] = '\udfff'
            elif field == 'checks':
                answer['checks'] = ['\udfff']
            else:
                answer[field] = '\udfff'
            self.fake.answer = answer
            with self.subTest(field=field):
                self.assert_error(await self.client.post('/api/reviews', json={'diff': SIMPLE}),
                                  502, 'INVALID_MODEL_OUTPUT')

    async def test_timeout_error_and_internal_safe_messages(self):
        for error, status, code in [(ReviewError('MODEL_UNAVAILABLE'), 502, 'MODEL_UNAVAILABLE'),
                                    (ReviewError('MODEL_TIMEOUT'), 504, 'MODEL_TIMEOUT'),
                                    (RuntimeError('private-provider-data'), 500, 'INTERNAL_ERROR')]:
            self.fake.error = error
            with self.subTest(code=code):
                response = await self.client.post('/api/reviews', json={'diff': SIMPLE})
                self.assert_error(response, status, code)
                self.assertNotIn('private-provider-data', response.text)

    async def test_logging_only_three_fields_on_success_and_failure(self):
        with self.assertLogs('review.audit', level=logging.INFO) as logs:
            success = await self.client.post('/api/reviews', json={'diff': SIMPLE})
            failure = await self.client.post('/api/reviews', json={'diff': ''})
        self.assertEqual(len(logs.records), 2)
        for record, response in zip(logs.records, [success, failure]):
            payload = json.loads(record.getMessage())
            self.assertEqual(set(payload), {'request_id', 'duration_ms', 'status'})
            self.assertEqual(payload['request_id'], response.json()['request_id'])
            self.assertEqual(payload['status'], response.status_code)
            self.assertGreaterEqual(payload['duration_ms'], 0)
            self.assertIsNone(record.exc_info)

    async def test_live_not_configured_is_503_no_fallback(self):
        app = create_app(service=ReviewService(Settings(mode='live'), self.fake))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            self.assert_error(await client.post('/api/reviews', json={'diff': SIMPLE}), 503, 'MODEL_NOT_CONFIGURED')
        self.assertEqual(self.fake.calls, [])

    async def test_static_routes_and_api_are_available(self):
        response = await self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="review-form"', response.text)
        for path in ['/static/app.js', '/static/styles.css']:
            self.assertEqual((await self.client.get(path)).status_code, 200)
        self.assertEqual((await self.client.post('/api/reviews', json={'diff': SIMPLE})).status_code, 200)

    async def test_demo_uses_training_diff_over_actual_api(self):
        app = create_app(service=ReviewService(Settings()))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/api/reviews', json={'diff': TRAINING.read_text()})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['risks']), 3)
        self.assertEqual(response.json()['mode'], 'demo')
