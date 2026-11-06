"""Сквозная проверка стыка двух команд: сервер отдаёт настоящие файлы web/.

Команда логики проверяла сервер на временной статике, команда UI — логику
страницы без сервера. Здесь — то, что видит браузер: настоящие index.html и
app.js через настоящий сервер, и полный путь POST /api/review.
"""

import http.client
import json
import re
import threading
import unittest

from app.server import WEB_DIR, create_server


class FakeClient:
    def complete(self, system, user):
        return "сквозной ответ"


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.server = create_server(port=0, client=FakeClient(), static_dir=WEB_DIR)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            return response.status, response.headers, response.read().decode("utf-8")
        finally:
            conn.close()

    def test_page_loads_script_from_contract_route(self):
        status, headers, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn('<script type="module" src="/app.js">', html)

    def test_script_is_served_and_calls_contract_endpoint(self):
        status, headers, js = self.request("GET", "/app.js")
        self.assertEqual(status, 200)
        self.assertIn("text/javascript", headers["Content-Type"])
        self.assertIn('"/api/review"', js)

    def test_every_element_the_script_needs_exists_on_the_page(self):
        _, _, html = self.request("GET", "/")
        _, _, js = self.request("GET", "/app.js")
        needed = set(re.findall(r'getElementById\("([^"]+)"\)', js))
        present = set(re.findall(r'id="([^"]+)"', html))
        self.assertTrue(needed)
        self.assertEqual(needed - present, set())

    def test_review_round_trip(self):
        diff = "--- a/x.py\n+++ b/x.py\n+print(1)\n"
        status, _, body = self.request("POST", "/api/review", json.dumps({"diff": diff}))
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body),
            {"status": "ok", "review": "сквозной ответ", "stats": {"files": 1, "added": 1, "removed": 0}},
        )


if __name__ == "__main__":
    unittest.main()
