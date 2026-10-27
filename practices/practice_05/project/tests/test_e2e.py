"""Browser checks: real demo round-trip plus explicitly controlled UI failures."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

PROJECT = Path(__file__).resolve().parents[1]
EVIDENCE = PROJECT.parent / 'evidence'
TRAINING_DIFF = (PROJECT.parent / 'inputs/TRAINING_PR.diff').read_text()
SMALL_DIFF = '--- a/example.py\n+++ b/example.py\n@@ -1 +1 @@\n-old()\n+new()\n'
REVIEW = {
    'request_id': 'f2a7a4a0-8e22-4b26-a616-607993d0fb17',
    'mode': 'demo', 'summary': 'Учебное изменение',
    'risks': [{'file': 'example.py', 'line': 1, 'evidence': '+new()', 'risk': 'Проверьте новый вызов.'}],
    'checks': ['Проверить успешный вызов и обработку исключения.'],
}


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        EVIDENCE.mkdir(exist_ok=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.base_url = f'http://127.0.0.1:{port}'
        cls.server_output = tempfile.TemporaryFile(mode='w+')
        cls.addClassCleanup(cls.server_output.close)
        env = dict(os.environ, REVIEW_MODE='demo', REVIEW_LLM_KEY='')
        cls.server = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'app.api:app', '--host', '127.0.0.1',
             '--port', str(port), '--no-access-log'], cwd=PROJECT, env=env,
            stdout=cls.server_output, stderr=subprocess.STDOUT,
        )
        cls.addClassCleanup(cls.stop_server)
        deadline = time.monotonic() + 10
        while True:
            try:
                with urlopen(cls.base_url, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError):
                pass
            if cls.server.poll() is not None or time.monotonic() > deadline:
                cls.server_output.seek(0)
                raise RuntimeError('Local server failed: ' + cls.server_output.read())
            time.sleep(0.1)
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        # Use a new temporary browser profile, never the user's browser session.
        cls.browser = cls.playwright.chromium.launch(
            channel=os.environ.get('PLAYWRIGHT_CHANNEL', 'chrome'), headless=True,
        )
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def stop_server(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
            try:
                cls.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=5)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page.set_default_timeout(5000)
        self.page_errors = []
        self.page.on('pageerror', lambda error: self.page_errors.append(str(error)))
        self.page.goto(self.base_url)
        self.field = self.page.get_by_role('textbox', name='Diff одного PR', exact=True)
        self.submit = self.page.get_by_role('button', name='Проверить diff', exact=True)
        self.clear = self.page.get_by_role('button', name='Очистить', exact=True)
        self.result = self.page.get_by_role('heading', name='Краткое описание', exact=True)
        self.alert = self.page.get_by_role('alert')

    def tearDown(self):
        self.assertEqual(self.page_errors, [])

    def send(self, diff=SMALL_DIFF):
        self.field.fill(diff)
        self.submit.click()

    def test_header_shaped_lines_keep_real_file_in_browser_result(self):
        diff = ('--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n--- old\n+++ new\n'
                '@@ -10 +10 @@\n-old\n+return payload["diff"]\n')
        self.send(diff)
        expect(self.result).to_be_visible()
        expect(self.page.locator('.risk-location')).to_have_text('a.txt:10 · новая версия')
        expect(self.page.locator('#summary')).to_contain_text('в 1 файле')

    def fulfill(self, data, status=200):
        self.page.route('**/api/reviews', lambda route: route.fulfill(
            status=status, content_type='application/json', body=json.dumps(data)))

    def test_real_demo_roundtrip_and_clear(self):
        with self.page.expect_response('**/api/reviews') as pending:
            self.send(TRAINING_DIFF)
        response = pending.value
        self.assertEqual(response.status, 200)
        body = response.json()
        self.assertEqual(body['mode'], 'demo')
        self.assertGreaterEqual(len(body['risks']), 1)
        self.assertLessEqual(len(body['risks']), 3)
        expect(self.result).to_be_visible()
        expect(self.page.get_by_role('heading', name='Возможные риски', exact=False)).to_be_visible()
        expect(self.page.get_by_text('ДЕМО — воспроизводимая подмена модели', exact=True)).to_be_visible()
        expect(self.page.get_by_role('heading', name='Что проверить', exact=True)).to_be_visible()
        self.page.screenshot(path=str(EVIDENCE / 'ui-desktop.png'), full_page=True)
        (EVIDENCE / 'browser-demo-response.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
        self.field.fill(SMALL_DIFF)
        expect(self.result).to_be_hidden()
        self.clear.click()
        expect(self.field).to_have_value('')
        expect(self.field).to_be_focused()
        expect(self.result).to_be_hidden()

    def test_empty_and_oversized_stay_local(self):
        requests = []
        self.page.on('request', lambda request: requests.append(request) if request.url.endswith('/api/reviews') else None)
        self.submit.click()
        expect(self.alert).to_be_visible()
        expect(self.field).to_be_focused()
        expect(self.field).to_have_attribute('aria-invalid', 'true')
        self.send('я' * 20001)
        expect(self.alert).to_contain_text('20 000')
        expect(self.field).to_have_value('я' * 20001)
        self.assertEqual(requests, [])

    def test_exact_unicode_boundary_real_server(self):
        prefix = '--- a/a.py\n+++ b/a.py\n@@ -0,0 +1 @@\n+'
        diff = prefix + '😀' * (20000 - len(prefix) - 1) + '\n'
        with self.page.expect_response('**/api/reviews') as pending:
            self.send(diff)
        response = pending.value
        self.assertEqual(response.status, 200)
        self.assertEqual(response.request.post_data_json, {'diff': diff})
        expect(self.result).to_be_visible()
        expect(self.page.get_by_text('Возможных рисков не найдено. Это не гарантирует отсутствие ошибок', exact=False)).to_be_visible()

    def test_invalid_diff_and_manual_retry_real_server(self):
        self.send('Это не diff')
        expect(self.alert).to_contain_text('unified diff')
        expect(self.field).to_have_value('Это не diff')
        expect(self.submit).to_be_enabled()
        expect(self.result).to_be_hidden()
        self.send(TRAINING_DIFF)
        expect(self.result).to_be_visible()
        expect(self.alert).to_be_hidden()

    def test_provider_error_and_retry_ui(self):
        self.fulfill({'request_id': 'safe-id', 'error': {'code': 'MODEL_UNAVAILABLE', 'message': 'private-provider-body'}}, 502)
        self.send()
        expect(self.alert).to_contain_text('Анализ сейчас недоступен')
        expect(self.field).to_have_value(SMALL_DIFF)
        self.assertNotIn('private-provider-body', self.page.locator('body').inner_text())
        self.page.screenshot(path=str(EVIDENCE / 'ui-error.png'), full_page=True)
        self.page.unroute('**/api/reviews')
        self.submit.click()
        expect(self.result).to_be_visible()

    def test_network_error_ui(self):
        self.page.route('**/api/reviews', lambda route: route.abort('failed'))
        self.send()
        expect(self.alert).to_contain_text('Не удалось связаться')
        expect(self.submit).to_be_enabled()
        expect(self.field).to_have_value(SMALL_DIFF)

    def test_loading_single_attempt_and_late_response(self):
        # Freeze a response beyond the UI's *real* 15-second deadline. Route control
        # affects only this UI test; backend timeout has independent async tests.
        pending = []
        self.page.route('**/api/reviews', lambda route: pending.append(route))
        self.send()
        expect(self.field).to_be_disabled()
        expect(self.submit).to_be_disabled()
        expect(self.clear).to_be_disabled()
        self.submit.evaluate('(button) => button.form.requestSubmit()')
        self.assertEqual(len(pending), 1)
        expect(self.alert).to_contain_text('Время ожидания истекло', timeout=18000)
        expect(self.field).to_be_enabled()
        self.submit.click()
        self.page.wait_for_function('document.querySelector("textarea").disabled')
        self.assertEqual(len(pending), 2)
        newer = dict(REVIEW, summary='Новый результат')
        pending[1].fulfill(status=200, content_type='application/json', body=json.dumps(newer))
        expect(self.page.get_by_text('Новый результат', exact=True)).to_be_visible()
        pending[0].fulfill(status=200, content_type='application/json', body=json.dumps(dict(REVIEW, summary='Устаревший результат')))
        expect(self.page.get_by_text('Новый результат', exact=True)).to_be_visible()
        expect(self.page.get_by_text('Устаревший результат', exact=True)).to_have_count(0)

    def test_malformed_success_rejected_wholly(self):
        bad_risk = dict(REVIEW['risks'][0], line=True)
        variants = [dict(REVIEW, checks=[]), dict(REVIEW, risks=REVIEW['risks']*4),
                    dict(REVIEW, risks=[bad_risk]), dict(REVIEW, mode='fake'),
                    dict(REVIEW, summary='x'*1501)]
        for payload in variants:
            with self.subTest(payload=str(payload)[:80]):
                self.fulfill(payload)
                self.send()
                expect(self.alert).to_contain_text('некорректный результат')
                expect(self.result).to_be_hidden()
                self.page.unroute('**/api/reviews')

    def test_literal_rendering_three_risks_live_label(self):
        text = '<img src=x onerror="window.__executed=true">'
        payload = copy.deepcopy(REVIEW)
        payload.update(mode='live', summary=text)
        payload['risks'] = [dict(REVIEW['risks'][0], file=text, risk=text, evidence='+'+text) for _ in range(3)]
        self.fulfill(payload)
        self.send()
        expect(self.result).to_be_visible()
        expect(self.page.get_by_text('Реальный анализ', exact=True)).to_be_visible()
        self.assertIsNone(self.page.evaluate('window.__executed'))
        self.assertEqual(self.page.locator('img').count(), 0)
        self.assertIn(text, self.page.locator('body').inner_text())
        self.assertEqual(self.page.evaluate('localStorage.length'), 0)
        self.assertEqual(self.page.evaluate('sessionStorage.length'), 0)

    def test_mobile_layout_keyboard_and_aria(self):
        self.page.set_viewport_size({'width': 360, 'height': 800})
        self.field.focus()
        self.field.fill(TRAINING_DIFF)
        self.page.keyboard.press('Tab')
        expect(self.submit).to_be_focused()
        self.page.keyboard.press('Enter')
        expect(self.result).to_be_visible()
        expect(self.page.get_by_role('status')).to_be_visible()
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 360)
        self.page.screenshot(path=str(EVIDENCE / 'ui-mobile.png'), full_page=True)
        # A 640 CSS-pixel viewport is the reflow width of 1280px at 200% zoom.
        self.page.set_viewport_size({'width': 640, 'height': 450})
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 640)
        self.clear.focus()
        self.page.keyboard.press('Space')
        expect(self.field).to_be_focused()
        expect(self.field).to_have_value('')
