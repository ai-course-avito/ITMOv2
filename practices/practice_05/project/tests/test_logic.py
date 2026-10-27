import asyncio
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx

from app.config import Settings
from app.diff import parse_diff
from app.errors import ReviewError
from app.llm import DemoAdapter, LiveAdapter
from app.review import ReviewService, validate_review
from app.secrets import redact_text, redact_values

TRAINING = Path(__file__).resolve().parents[2] / "inputs" / "TRAINING_PR.diff"
SIMPLE = "--- a/example.py\n+++ b/example.py\n@@ -4,9 +8,12 @@\n-old()\n+new()\n context()\n"


def candidate(diff=SIMPLE):
    line = next(row for row in parse_diff(diff) if row.evidence.startswith("+"))
    return {"summary": "Изменён вызов.", "risks": [{"file": line.file, "line": line.line,
            "evidence": line.evidence, "risk": "Возможное изменение поведения."}],
            "checks": ["Проверить результат вызова на ожидаемом примере."]}


class FakeAdapter:
    def __init__(self, answer=None, error=None, delay=0):
        self.answer = answer
        self.error = error
        self.delay = delay
        self.calls = []
        self.cancelled = False
        self.started = asyncio.Event()

    async def generate(self, diff):
        self.calls.append(diff)
        self.started.set()
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
            return copy.deepcopy(self.answer if self.answer is not None else candidate(diff))
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class DiffTests(unittest.TestCase):
    def test_training_partial_hunks_and_coordinates(self):
        rows = parse_diff(TRAINING.read_text())
        call = next(x for x in rows if x.evidence == '+        answer = self.llm.generate(prompt)')
        self.assertEqual((call.file, call.line, call.side), ('app/review_service.py', 15, 'new'))
        api = next(x for x in rows if 'return review_service.review(payload["diff"])' in x.evidence)
        self.assertEqual((api.file, api.line), ('app/api.py', 10))

    def test_added_deleted_context_and_crlf(self):
        rows = parse_diff(SIMPLE.replace('\n', '\r\n'))
        self.assertEqual([(x.line, x.side, x.evidence) for x in rows],
                         [(4, 'old', '-old()'), (8, 'new', '+new()'), (9, 'new', ' context()')])

    def test_create_delete_and_no_newline_marker(self):
        for text, path in [
            ('--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+x\n\\ No newline at end of file\n', 'new.py'),
            ('--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n', 'gone.py')]:
            with self.subTest(path=path):
                self.assertEqual(parse_diff(text)[0].file, path)

    def test_unsupported_and_invalid(self):
        cases = [("diff --git a/a b/a\nBinary files a/a and b/a differ", 'UNSUPPORTED_DIFF'),
                 ('diff --cc x\n@@@ -1 -1 +1 @@@\n+x', 'UNSUPPORTED_DIFF'),
                 ('diff --git a/a b/b\nsimilarity index 100%\nrename from a\nrename to b', 'UNSUPPORTED_DIFF'),
                 ('--- "a/a\\tb"\n+++ "b/a\\tb"\n@@ -1 +1 @@\n-x\n+y', 'UNSUPPORTED_DIFF'),
                 ('arbitrary text', 'INVALID_DIFF'),
                 ('--- a/a\n+++ b/a\n@@ -1 +1 @@\n context', 'INVALID_DIFF'),
                 ('--- a/a\n+++ b/a\n@@ -1 +1 @@\nnot-prefixed', 'INVALID_DIFF')]
        for diff, code in cases:
            with self.subTest(code=code, diff=diff):
                with self.assertRaises(ReviewError) as ctx:
                    parse_diff(diff)
                self.assertEqual(ctx.exception.code, code)

    def test_new_git_block_cannot_reuse_previous_path(self):
        for suffix in ['diff --git a/b b/b\n', 'diff --git a/b b/b\n@@ -1 +1 @@\n-old\n+new\n']:
            with self.subTest(suffix=suffix):
                with self.assertRaises(ReviewError) as ctx:
                    parse_diff(SIMPLE + suffix)
                self.assertEqual(ctx.exception.code, 'INVALID_DIFF')

    def test_header_shaped_hunk_payload_is_not_a_new_file(self):
        diff = '--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n--- old\n+++ new\n'
        rows = parse_diff(diff)
        self.assertEqual([(row.file, row.line, row.evidence) for row in rows],
                         [('a.txt', 1, '--- old'), ('a.txt', 1, '+++ new')])
        answer = {'summary': 'Изменена строка.', 'risks': [
            {'file': 'a.txt', 'line': 1, 'evidence': '+++ new', 'risk': 'Проверить новое значение.'}],
            'checks': ['Проверить ожидаемое значение строки.']}
        self.assertEqual(validate_review(answer, rows)['risks'][0]['file'], 'a.txt')

    def test_multifile_without_git_marker_keeps_partial_hunks(self):
        diff = SIMPLE + '--- a/second.py\n+++ b/second.py\n@@ -10,99 +20,99 @@\n-old\n+new\n'
        rows = parse_diff(diff)
        self.assertEqual((rows[-2].file, rows[-2].line), ('second.py', 10))
        self.assertEqual((rows[-1].file, rows[-1].line), ('second.py', 20))

    def test_header_shaped_payload_before_next_hunk_keeps_file_and_evidence(self):
        for header, prefix, coordinate in [('@@ -1 +1 @@', '', 1),
                                           ('@@ -1,2 +1,2 @@', ' context\n', 2)]:
            diff = ('--- a/a.txt\n+++ b/a.txt\n' + header + '\n' + prefix
                    + '--- old\n+++ new\n@@ -10 +10 @@\n-last\n+next\n')
            with self.subTest(header=header):
                rows = parse_diff(diff)
                self.assertEqual({row.file for row in rows}, {'a.txt'})
                self.assertIn(('a.txt', coordinate, '+++ new'),
                              [(row.file, row.line, row.evidence) for row in rows])
                self.assertEqual(rows[-1].line, 10)

    def test_excessive_hunk_numbers_are_invalid_diff(self):
        diff = '--- a/a\n+++ b/a\n@@ -' + '9'*5000 + ' +1 @@\n-old\n+new\n'
        with self.assertRaises(ReviewError) as ctx:
            parse_diff(diff)
        self.assertEqual(ctx.exception.code, 'INVALID_DIFF')

    def test_empty_normalized_path_is_invalid_diff(self):
        with self.assertRaises(ReviewError) as ctx:
            parse_diff('--- a/\n+++ b/\n@@ -1 +1 @@\n-old\n+new\n')
        self.assertEqual(ctx.exception.code, 'INVALID_DIFF')

    def test_file_headers_are_not_evidence_and_multiple_hunks(self):
        rows = parse_diff(SIMPLE + '@@ -30 +40 @@\n-other\n+next\n')
        self.assertEqual(rows[-1].line, 40)
        self.assertFalse(any(x.evidence.startswith('+++') for x in rows))


class RedactionTests(unittest.TestCase):
    def test_supported_assignments_and_escaped_quotes(self):
        inputs = [r'+token="top\"secret"', "+PASSWORD: 'hello\\'world'", '+passwd=hidden;',
                  '+"secret": "hidden",', "+api_key = hidden, other=visible", '+password=""']
        for value in inputs:
            with self.subTest(value=value):
                result = redact_text(value)
                self.assertNotIn('hidden', result)
                self.assertNotIn('top', result)
                self.assertNotIn('hello', result)
                self.assertEqual(redact_text(result), result)
        self.assertEqual(redact_text('+password=""'), '+password=""')
        self.assertEqual(redact_text(r'+token="top\"secret"'), '+token="[REDACTED]"')

    def test_prefixes_bearer_and_short_token_boundary(self):
        result = redact_text('ghp_abcdefgh github_pat_12345678 sk-abcdefgh Bearer abc123')
        self.assertEqual(result.count('[REDACTED]'), 4)
        self.assertEqual(redact_text('ghp_short'), 'ghp_short')
        self.assertEqual(redact_text(result), result)

    def test_pem_types_preserve_lines_and_diff_prefixes(self):
        for kind in ['', 'RSA ', 'EC ', 'OPENSSH ']:
            original = f'+-----BEGIN {kind}PRIVATE KEY-----\r\n+secretA\r\n-secretB\r\n contextC\r\n+-----END {kind}PRIVATE KEY-----\r\n+safe()\r\n'
            result = redact_text(original)
            with self.subTest(kind=kind):
                for secret in ['secretA', 'secretB', 'contextC']:
                    self.assertNotIn(secret, result)
                self.assertIn('+safe()', result)
                self.assertEqual(result.count('\r\n'), original.count('\r\n'))
                self.assertIn('-[REDACTED]', result)
                self.assertIn(' [REDACTED]', result)
                self.assertEqual(redact_text(result), result)

    def test_unclosed_pem_keeps_structural_headers_and_masks_following_payload(self):
        source = ('--- a/a\n+++ b/a\n@@ -1 +1 @@\n+-----BEGIN PRIVATE KEY-----\n+secret\n'
                  'diff --git a/b b/b\n--- a/b\n+++ b/b\n@@ -1 +1 @@\n-moresecret\n+secret2\n')
        result = redact_text(source)
        self.assertIn('+++ b/b', result)
        self.assertIn('@@ -1 +1 @@', result)
        self.assertNotIn('secret', result)
        self.assertEqual(redact_text(result), result)
        self.assertEqual(len(source.splitlines()), len(result.splitlines()))
        self.assertEqual(len(parse_diff(source)), len(parse_diff(result)))

    def test_inline_and_unclosed_inline_pem_payload_is_masked(self):
        for kind in ['', 'RSA ', 'EC ', 'OPENSSH ']:
            for suffix in [f'-----END {kind}PRIVATE KEY-----', '']:
                source = f'+key = "-----BEGIN {kind}PRIVATE KEY-----inline-secret{suffix}"'
                with self.subTest(kind=kind, closed=bool(suffix)):
                    result = redact_text(source)
                    self.assertNotIn('inline-secret', result)
                    self.assertIn('[REDACTED]', result)
                    self.assertEqual(redact_text(result), result)
                    self.assertEqual(result.count('\n'), source.count('\n'))

    def test_redaction_all_prefixes_and_recursive_values(self):
        source = '-token=first\n+token=second\n password=third\n'
        result = redact_text(source)
        self.assertEqual(result, '-token=[REDACTED]\n+token=[REDACTED]\n password=[REDACTED]\n')
        obj = {'checks': ['Bearer secret-value'], 'line': 3, 'nested': {'risk': 'token=hidden'}}
        masked = redact_values(obj)
        self.assertEqual(masked['line'], 3)
        self.assertNotIn('hidden', str(masked))
        self.assertEqual(redact_values(masked), masked)


class OutputTests(unittest.TestCase):
    def test_zero_three_and_four_risks(self):
        for count in [0, 3, 4]:
            answer = candidate()
            answer['risks'] *= count
            with self.subTest(count=count):
                if count == 4:
                    with self.assertRaises(ReviewError):
                        validate_review(answer, parse_diff(SIMPLE))
                else:
                    self.assertEqual(len(validate_review(answer, parse_diff(SIMPLE))['risks']), count)

    def test_invalid_fields_and_limits(self):
        alterations = [lambda a: a.update(extra='x'), lambda a: a.update(summary=' '),
                      lambda a: a.update(summary='x'*1501), lambda a: a.update(checks=[]),
                      lambda a: a.update(checks=['x']*11), lambda a: a.update(checks=['x'*501]),
                      lambda a: a['risks'][0].update(line=True), lambda a: a['risks'][0].update(line=None),
                      lambda a: a['risks'][0].update(line=9), lambda a: a['risks'][0].update(file=None),
                      lambda a: a['risks'][0].update(file='unknown.py'),
                      lambda a: a['risks'][0].update(evidence='RULE:SEC-1'),
                      lambda a: a['risks'][0].update(evidence='new()'),
                      lambda a: a['risks'][0].update(risk='x'*1001),
                      lambda a: a['risks'][0].update(extra='x')]
        for change in alterations:
            answer = candidate(); change(answer)
            with self.subTest(answer=answer):
                with self.assertRaises(ReviewError) as ctx:
                    validate_review(answer, parse_diff(SIMPLE))
                self.assertEqual(ctx.exception.code, 'INVALID_MODEL_OUTPUT')

    def test_deleted_line_uses_old_coordinate(self):
        answer = candidate(); answer['risks'][0].update(line=4, evidence='-old()')
        self.assertEqual(validate_review(answer, parse_diff(SIMPLE))['risks'][0]['line'], 4)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_training_has_three_verified_risks(self):
        result = await ReviewService(Settings(), DemoAdapter()).review(TRAINING.read_text())
        self.assertEqual(result['mode'], 'demo')
        self.assertEqual(len(result['risks']), 3)
        self.assertTrue(result['checks'])
        self.assertIn('Демонстрац', result['summary'])

    async def test_no_demo_matching_rules(self):
        result = await ReviewService(Settings(), DemoAdapter()).review(SIMPLE)
        self.assertEqual(result['risks'], [])
        self.assertTrue(result['checks'])

    async def test_output_mask_before_evidence_validation(self):
        diff = '--- a/a\n+++ b/a\n@@ -1 +1 @@\n-token="before"\n+token="hidden-value"\n'
        answer = candidate(diff)
        answer['checks'] = ['Проверить password="secret-check"']
        fake = FakeAdapter(answer)
        result = await ReviewService(Settings(), fake).review(diff)
        self.assertNotIn('hidden-value', fake.calls[0])
        self.assertEqual(result['risks'][0]['evidence'], '+token="[REDACTED]"')
        self.assertNotIn('secret-check', json.dumps(result))

    async def test_timeout_cancels_adapter_once(self):
        fake = FakeAdapter(delay=10)
        with self.assertRaises(ReviewError) as ctx:
            await ReviewService(Settings(), fake, timeout_seconds=0.02).review(SIMPLE)
        self.assertEqual(ctx.exception.code, 'MODEL_TIMEOUT')
        self.assertTrue(fake.cancelled)
        self.assertEqual(len(fake.calls), 1)

    async def test_external_cancellation_propagates(self):
        fake = FakeAdapter(delay=10)
        task = asyncio.create_task(ReviewService(Settings(), fake).review(SIMPLE))
        await fake.started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(fake.cancelled)
        self.assertEqual(len(fake.calls), 1)

    async def test_live_missing_config_no_call_and_no_fallback(self):
        fake = FakeAdapter()
        with self.assertRaises(ReviewError) as ctx:
            await ReviewService(Settings(mode='live'), fake).review(SIMPLE)
        self.assertEqual(ctx.exception.code, 'MODEL_NOT_CONFIGURED')
        self.assertEqual(fake.calls, [])

    async def test_default_budget_ten_seconds(self):
        self.assertEqual(ReviewService(Settings()).timeout_seconds, 10)


class LiveAdapterTests(unittest.IsolatedAsyncioTestCase):
    def settings(self):
        return Settings(mode='live', llm_url='https://llm.test/chat/completions',
                        llm_model='test-model', llm_key='synthetic-key')

    async def test_wire_contract_and_validated_live_result(self):
        requests = []
        def handle(request):
            requests.append(request)
            self.assertEqual(request.headers['authorization'], 'Bearer synthetic-key')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'test-model')
            self.assertIn('SEC-1', body['messages'][0]['content'])
            self.assertIn(SIMPLE, body['messages'][1]['content'])
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(candidate())}}]})
        adapter = LiveAdapter(self.settings(), transport=httpx.MockTransport(handle))
        result = await ReviewService(self.settings(), adapter).review(SIMPLE)
        self.assertEqual(result['mode'], 'live')
        self.assertEqual(len(requests), 1)

    async def test_provider_and_shape_failures(self):
        cases = [(httpx.Response(429, text='private-upstream-body'), 'MODEL_UNAVAILABLE'),
                 (httpx.Response(200, text='invalid json'), 'INVALID_MODEL_OUTPUT'),
                 (httpx.Response(200, json={'choices': []}), 'INVALID_MODEL_OUTPUT'),
                 (httpx.Response(200, json={'choices': [{'message': {'content': '```json\n{}\n```'}}]}), 'INVALID_MODEL_OUTPUT')]
        for response, code in cases:
            requests = []
            def handle(request):
                requests.append(request); return response
            with self.subTest(code=code):
                with self.assertRaises(ReviewError) as ctx:
                    await LiveAdapter(self.settings(), transport=httpx.MockTransport(handle)).generate(SIMPLE)
                self.assertEqual(ctx.exception.code, code)
                self.assertNotIn('private-upstream-body', str(ctx.exception))
                self.assertEqual(len(requests), 1)

    async def test_transport_error_timeout_and_cancellation(self):
        for exception, code in [(httpx.ConnectError('secret-error'), 'MODEL_UNAVAILABLE'),
                                (httpx.ReadTimeout('secret-error'), 'MODEL_TIMEOUT')]:
            def handle(request):
                raise exception
            with self.subTest(code=code):
                with self.assertRaises(ReviewError) as ctx:
                    await LiveAdapter(self.settings(), transport=httpx.MockTransport(handle)).generate(SIMPLE)
                self.assertEqual(ctx.exception.code, code)
        cancelled = asyncio.Event()
        started = asyncio.Event()
        async def hanging(request):
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set(); raise
        task = asyncio.create_task(LiveAdapter(self.settings(), transport=httpx.MockTransport(hanging)).generate(SIMPLE))
        await started.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cancelled.is_set())


class SettingsTests(unittest.TestCase):
    def test_env_default_demo_and_configured_live(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(Settings.from_env().mode, 'demo')
        with patch.dict('os.environ', {'REVIEW_MODE': 'live', 'REVIEW_LLM_URL': 'https://example.test',
                                      'REVIEW_LLM_MODEL': 'm', 'REVIEW_LLM_KEY': 'synthetic'}, clear=True):
            self.assertEqual(Settings.from_env().llm_model, 'm')
