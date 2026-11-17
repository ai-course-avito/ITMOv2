"""HTTP-слой review-mini: страница и POST /api/review поверх review_diff.

Внешний контракт — specs/contract/review-api.md. Сервер слушает только
127.0.0.1; клиент модели и каталог статики передаются параметрами, чтобы
тесты поднимали настоящий сервер без сети и без Ollama.
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from app.ollama_client import OllamaClient
from app.review import review_diff

HOST = "127.0.0.1"
DEFAULT_PORT = 8055
MAX_REQUEST_BYTES = 1048576
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

REVIEW_PATH = "/api/review"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
STATUS_TO_HTTP = {"ok": 200, "rejected": 400, "error": 502}
REQUEST_ERRORS = {
    "invalid_request": (400, "тело запроса должно быть JSON-объектом со строковым полем diff"),
    "request_too_large": (413, f"тело запроса больше {MAX_REQUEST_BYTES} байт"),
    "method_not_allowed": (405, f"{REVIEW_PATH} принимает только POST"),
    "not_found": (404, "такого пути нет"),
}


class FakeModelClient:
    """Клиент демо-режима: отвечает фиксированным текстом и не ходит в сеть."""

    def complete(self, system, user):
        return "Демо-режим: настоящая модель не вызывалась. Замечаний нет."


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "review-mini"

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def do_PUT(self):
        self._route()

    def do_DELETE(self):
        self._route()

    def do_PATCH(self):
        self._route()

    def log_message(self, format, *args):
        if self.server.verbose:
            super().log_message(format, *args)

    def _route(self):
        path = urlsplit(self.path).path
        if path == REVIEW_PATH:
            if self.command == "POST":
                self._review()
            else:
                self._send_request_error("method_not_allowed")
        elif path in STATIC_FILES and self.command == "GET":
            self._send_static(*STATIC_FILES[path])
        else:
            self._send_request_error("not_found")

    def _review(self):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if length < 0:
            self._send_request_error("invalid_request")
            return
        if length > MAX_REQUEST_BYTES:
            # Тело не читаем. Сервер говорит HTTP/1.0 и так закрывает соединение
            # после ответа; флаг страхует от непрочитанного тела, если версию
            # протокола поднимут до HTTP/1.1 с keep-alive.
            self.close_connection = True
            self._send_request_error("request_too_large")
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, ValueError):
            payload = None
        if not isinstance(payload, dict) or not isinstance(payload.get("diff"), str):
            self._send_request_error("invalid_request")
            return
        result = review_diff(payload["diff"], client=self.server.model_client)
        self._send_json(STATUS_TO_HTTP[result["status"]], result)

    def _send_static(self, name, content_type):
        try:
            data = (self.server.static_dir / name).read_bytes()
        except OSError:
            self._send_request_error("not_found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_request_error(self, code):
        http_status, message = REQUEST_ERRORS[code]
        self._send_json(http_status, {"status": "request_error", "code": code, "message": message})

    def _send_json(self, http_status, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(http_status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_server(port=0, client=None, static_dir=WEB_DIR, verbose=False):
    server = ThreadingHTTPServer((HOST, port), ReviewHandler)
    server.daemon_threads = True
    server.model_client = client or OllamaClient()
    server.static_dir = Path(static_dir)
    server.verbose = verbose
    return server


def resolve_port(environ):
    raw = environ.get("REVIEW_PORT")
    if raw is None:
        return DEFAULT_PORT
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ValueError(f"REVIEW_PORT вне диапазона 1–65535: {raw}")
    return port


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="python3 -m app.server", description=__doc__.splitlines()[0])
    parser.add_argument("--fake-model", action="store_true", help="демо-режим без Ollama")
    return parser.parse_args(argv)


def build_client(args):
    return FakeModelClient() if args.fake_model else OllamaClient()


def main(argv=None):
    args = parse_args(argv)
    try:
        port = resolve_port(os.environ)
    except ValueError as error:
        print(f"review-mini: неверный REVIEW_PORT: {error}", file=sys.stderr)
        return 2
    server = create_server(port=port, client=build_client(args), verbose=True)
    mode = "демо-режим (--fake-model)" if args.fake_model else "модель Ollama"
    print(f"review-mini: http://{HOST}:{port}/ — {mode}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
