import http.client
import json
import socket
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path

from app.review import MAX_DIFF_BYTES, review_diff
from app.server import (
    DEFAULT_PORT,
    MAX_REQUEST_BYTES,
    FakeModelClient,
    build_client,
    create_server,
    parse_args,
    resolve_port,
)
from app.ollama_client import OllamaClient

DIFF = "--- a/x.py\n+++ b/x.py\n+print(1)\n-print(2)\n"


class FakeClient:
    """Клиент, который запоминает вызовы и не ходит в сеть."""

    def __init__(self, answer="замечаний нет"):
        self.answer = answer
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.answer


class TimeoutClient:
    """Клиент, имитирующий истечение ожидания ответа модели."""

    def complete(self, system, user):
        raise socket.timeout("timed out")


class UnavailableClient:
    """Клиент, имитирующий отсутствие соединения с моделью."""

    def complete(self, system, user):
        raise urllib.error.URLError("connection refused")


class BlockingClient:
    """Клиент, который отвечает только после сигнала — для проверки параллельности."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def complete(self, system, user):
        self.started.set()
        self.release.wait(5)
        return "медленный ответ"


class ServerTestCase(unittest.TestCase):
    """Поднимает настоящий сервер на свободном порту 127.0.0.1 с подставной моделью."""

    client_class = FakeClient

    def setUp(self):
        self.static = tempfile.TemporaryDirectory()
        static_dir = Path(self.static.name)
        (static_dir / "index.html").write_text("<!doctype html><title>t</title>", encoding="utf-8")
        (static_dir / "app.js").write_text("export const x = 1;\n", encoding="utf-8")
        self.client = self.client_class()
        self.server = create_server(port=0, client=self.client, static_dir=static_dir)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.static.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            raw = response.read()
            return response.status, response.headers, raw
        finally:
            conn.close()

    def post_review(self, payload):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        status, headers, raw = self.request(
            "POST", "/api/review", body=body, headers={"Content-Type": "application/json"}
        )
        return status, headers, json.loads(raw)


class BindingTest(ServerTestCase):
    def test_listens_only_on_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


class SuccessTest(ServerTestCase):
    def test_ok_returns_200_and_review_diff_dict_unchanged(self):
        status, headers, body = self.post_review({"diff": DIFF})
        self.assertEqual(status, 200)
        self.assertEqual(body, review_diff(DIFF, client=FakeClient()))
        self.assertIn("application/json", headers["Content-Type"])

    def test_unknown_fields_are_ignored(self):
        status, _, body = self.post_review({"diff": DIFF, "extra": [1, 2]})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_diff_exactly_at_limit_passes_through_json_overhead(self):
        # "ы" — 2 байта в UTF-8 и 6 байт в JSON (ы): тело больше MAX_DIFF_BYTES,
        # но дифф ровно на лимите должен дойти до review_diff.
        diff = "ы" * (MAX_DIFF_BYTES // 2)
        status, _, body = self.post_review({"diff": diff})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")


class RejectTest(ServerTestCase):
    def test_empty_diff_is_400_rejected_without_model_call(self):
        status, _, body = self.post_review({"diff": "   "})
        self.assertEqual(status, 400)
        self.assertEqual((body["status"], body["code"]), ("rejected", "empty_diff"))
        self.assertEqual(self.client.calls, [])

    def test_too_large_diff_is_400_rejected_without_model_call(self):
        status, _, body = self.post_review({"diff": "a" * (MAX_DIFF_BYTES + 1)})
        self.assertEqual(status, 400)
        self.assertEqual((body["status"], body["code"]), ("rejected", "diff_too_large"))
        self.assertEqual(self.client.calls, [])

    def assert_invalid_request(self, payload):
        status, _, body = self.post_review(payload)
        self.assertEqual(status, 400)
        self.assertEqual((body["status"], body["code"]), ("request_error", "invalid_request"))
        self.assertTrue(body["message"])
        self.assertEqual(self.client.calls, [])

    def test_body_that_is_not_json_is_invalid_request(self):
        self.assert_invalid_request(b'{"diff": "oops')

    def test_json_that_is_not_object_is_invalid_request(self):
        self.assert_invalid_request(["--- a"])

    def test_missing_diff_is_invalid_request(self):
        self.assert_invalid_request({"text": DIFF})

    def test_non_string_diff_is_invalid_request(self):
        self.assert_invalid_request({"diff": 42})

    def test_missing_content_length_is_invalid_request(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.putrequest("POST", "/api/review")
            conn.endheaders()
            response = conn.getresponse()
            body = json.loads(response.read())
        finally:
            conn.close()
        self.assertEqual(response.status, 400)
        self.assertEqual(body["code"], "invalid_request")

    def test_oversized_body_is_413_before_body_is_sent(self):
        # Тело не отправляем вовсе: ответ должен прийти по одному заголовку.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            conn.putrequest("POST", "/api/review")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(MAX_REQUEST_BYTES + 1))
            conn.endheaders()
            response = conn.getresponse()
            body = json.loads(response.read())
        finally:
            conn.close()
        self.assertEqual(response.status, 413)
        self.assertTrue(response.will_close)
        self.assertEqual((body["status"], body["code"]), ("request_error", "request_too_large"))
        self.assertEqual(self.client.calls, [])


class RoutingTest(ServerTestCase):
    def assert_request_error(self, method, path, http_status, code):
        status, headers, raw = self.request(method, path)
        self.assertEqual(status, http_status)
        self.assertIn("application/json", headers["Content-Type"])
        body = json.loads(raw)
        self.assertEqual((body["status"], body["code"]), ("request_error", code))

    def test_get_on_review_endpoint_is_405(self):
        self.assert_request_error("GET", "/api/review", 405, "method_not_allowed")

    def test_put_on_review_endpoint_is_405(self):
        self.assert_request_error("PUT", "/api/review", 405, "method_not_allowed")

    def test_unknown_path_get_is_404(self):
        self.assert_request_error("GET", "/nope", 404, "not_found")

    def test_unknown_path_post_is_404(self):
        self.assert_request_error("POST", "/nope", 404, "not_found")


class TimeoutModelTest(ServerTestCase):
    client_class = TimeoutClient

    def test_model_timeout_is_502_with_stats(self):
        status, _, body = self.post_review({"diff": DIFF})
        self.assertEqual(status, 502)
        self.assertEqual((body["status"], body["code"]), ("error", "model_timeout"))
        self.assertEqual(body["stats"], {"files": 1, "added": 1, "removed": 1})


class UnavailableModelTest(ServerTestCase):
    client_class = UnavailableClient

    def test_model_unavailable_is_502_with_stats(self):
        status, _, body = self.post_review({"diff": DIFF})
        self.assertEqual(status, 502)
        self.assertEqual((body["status"], body["code"]), ("error", "model_unavailable"))
        self.assertIn("stats", body)


class StaticTest(ServerTestCase):
    def test_root_serves_index_html(self):
        status, headers, raw = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertEqual(raw, b"<!doctype html><title>t</title>")

    def test_app_js_is_served_as_javascript(self):
        status, headers, raw = self.request("GET", "/app.js?v=1")
        self.assertEqual(status, 200)
        self.assertIn("text/javascript", headers["Content-Type"])
        self.assertEqual(raw, b"export const x = 1;\n")

    def test_missing_static_file_is_404(self):
        (Path(self.static.name) / "app.js").unlink()
        status, _, raw = self.request("GET", "/app.js")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["code"], "not_found")


class ConcurrencyTest(ServerTestCase):
    client_class = BlockingClient

    def test_slow_model_request_does_not_block_other_requests(self):
        results = {}

        def slow():
            results["slow"] = self.post_review({"diff": DIFF})[0]

        worker = threading.Thread(target=slow)
        worker.start()
        self.assertTrue(self.client.started.wait(5))
        status, _, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.client.release.set()
        worker.join(5)
        self.assertEqual(results["slow"], 200)


class LaunchTest(unittest.TestCase):
    def test_fake_model_client_answers_without_network(self):
        self.assertTrue(FakeModelClient().complete("system", "user"))

    def test_fake_model_flag_selects_fake_client(self):
        self.assertIsInstance(build_client(parse_args(["--fake-model"])), FakeModelClient)

    def test_without_flag_real_client_is_used(self):
        self.assertIsInstance(build_client(parse_args([])), OllamaClient)

    def test_port_defaults_to_8055(self):
        self.assertEqual(resolve_port({}), DEFAULT_PORT)
        self.assertEqual(DEFAULT_PORT, 8055)

    def test_port_from_environment(self):
        self.assertEqual(resolve_port({"REVIEW_PORT": "9000"}), 9000)

    def test_invalid_port_is_rejected(self):
        for value in ("abc", "0", "70000"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    resolve_port({"REVIEW_PORT": value})


class DemoModeTest(ServerTestCase):
    client_class = FakeModelClient

    def test_demo_mode_still_validates_input(self):
        status, _, body = self.post_review({"diff": ""})
        self.assertEqual((status, body["code"]), (400, "empty_diff"))

    def test_demo_mode_returns_ok(self):
        status, _, body = self.post_review({"diff": DIFF})
        self.assertEqual((status, body["status"]), (200, "ok"))


if __name__ == "__main__":
    unittest.main()
