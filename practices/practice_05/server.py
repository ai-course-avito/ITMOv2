#!/usr/bin/env python3
# Minimal HTTP server using stdlib only, serving API and static UI.
# No external dependencies required.

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote, parse_qs
from pathlib import Path
import json
import sys
import hashlib

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "subscribers.json"
UI_DIR = ROOT / "ui"
APP_VERSION = "0.1.0"


def load_subscribers():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_subscribers(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, body=b"", content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else b""
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            return self._send(200, json.dumps({"status": "ok"}).encode(), "application/json")
        if path == "/version":
            return self._send(200, json.dumps({"version": APP_VERSION}).encode(), "application/json")
        if path == "/subscribers":
            return self._send(200, json.dumps(load_subscribers()).encode(), "application/json")

        if path in ("/api/subscribers/search", "/search/users"):
            # Require auth header per spec
            if not self.headers.get("X-Auth-User"):
                return self._send(401, json.dumps({"error": {"code": "unauthorized", "message": "authentication required"}}).encode())

            params = parse_qs(parsed.query or "")
            # accept both 'query' and legacy 'q'
            q = (params.get("query") or params.get("q") or [""])[0]
            q = (q or "").strip()
            if len(q) < 2:
                return self._send(422, json.dumps({"error": {"code": "validation_error", "message": "query length must be between 2 and 100"}}).encode())
            if len(q) > 100:
                return self._send(422, json.dumps({"error": {"code": "validation_error", "message": "query length must be between 2 and 100"}}).encode())

            try:
                page = int((params.get("page") or ["1"])[0])
            except Exception:
                page = 1
            if page < 1:
                page = 1
            try:
                page_size = int((params.get("page_size") or ["20"])[0])
            except Exception:
                page_size = 20
            if page_size < 1:
                page_size = 20
            if page_size > 50:
                page_size = 50

            # Helpers to produce safe DTOs
            def _safe_username(rec: dict) -> str:
                name = (rec.get("name") or "").strip()
                if name:
                    return name
                email = (rec.get("email") or "").strip()
                if "@" in email:
                    return email.split("@", 1)[0]
                return email

            def _safe_id(email: str) -> str:
                try:
                    digest = hashlib.sha1((email or "").lower().encode("utf-8")).hexdigest()
                except Exception:
                    digest = hashlib.sha1(b"").hexdigest()
                return digest[:12]

            subs = load_subscribers()
            users = []
            for r in subs:
                email = r.get("email") or ""
                users.append({
                    "id": _safe_id(email),
                    "username": _safe_username(r),
                    "status": "active",
                })

            folded = q.casefold()
            matched = [u for u in users if folded in (u.get("username") or "").casefold()]
            matched.sort(key=lambda u: (u.get("username") or "", u.get("id") or ""))

            total = len(matched)
            start = (page - 1) * page_size
            end = start + page_size
            items = matched[start:end]

            body = {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }
            return self._send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json")

        # Static UI: serve from ui directory, default to index.html
        target = UI_DIR / (path.lstrip("/") or "index.html")
        if target.is_dir():
            target = target / "index.html"
        if target.exists():
            ctype = "text/plain"
            if target.suffix == ".html": ctype = "text/html; charset=utf-8"
            elif target.suffix == ".css": ctype = "text/css; charset=utf-8"
            elif target.suffix == ".js": ctype = "application/javascript; charset=utf-8"
            return self._send(200, target.read_bytes(), ctype)

        return self._send(404, json.dumps({"detail": "not found"}).encode(), "application/json")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/subscribe":
            data = self._json() or {}
            email = (data.get("email") or "").strip()
            name = (data.get("name") or None)
            if not email:
                return self._send(400, json.dumps({"detail": "email required"}).encode())
            items = load_subscribers()
            if any(i.get("email") == email for i in items):
                return self._send(409, json.dumps({"detail": "already subscribed"}).encode())
            items.append({"email": email, "name": name})
            save_subscribers(items)
            return self._send(201, json.dumps({"email": email, "status": "subscribed"}).encode())

        return self._send(404, json.dumps({"detail": "not found"}).encode())

    def do_DELETE(self):
        parsed = urlparse(self.path)
        seg = parsed.path.split("/")
        if len(seg) == 3 and seg[1] == "subscribers":
            # decode percent-encoded email from URL path
            email = unquote(seg[2])
            items = load_subscribers()
            before = len(items)
            items = [i for i in items if i.get("email") != email]
            if len(items) == before:
                return self._send(404, json.dumps({"detail": "not found"}).encode())
            save_subscribers(items)
            return self._send(204)
        return self._send(404, json.dumps({"detail": "not found"}).encode())


def main():
    port = 8000
    addr = ("0.0.0.0", port)
    httpd = HTTPServer(addr, Handler)
    print(f"Serving on http://{addr[0]}:{port} (no external deps)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    sys.exit(main())
