"""Deliberately vulnerable local shop. All identities and data are synthetic."""

import argparse
import html
import json
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from sandbox import Sandbox


class Shop:
    def __init__(self):
        self.sandbox = Sandbox()
        self.lock = threading.RLock()
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE profiles(id INTEGER PRIMARY KEY, name TEXT, email TEXT, address TEXT);
            INSERT INTO profiles VALUES
                (1, 'TEST_ALICE', 'alice@example.invalid', 'TEST_ADDRESS_A'),
                (2, 'TEST_BOB', 'bob@example.invalid', 'TEST_ADDRESS_B');
            CREATE TABLE orders(id INTEGER PRIMARY KEY, owner INTEGER, product TEXT, price REAL);
            INSERT INTO orders VALUES (1, 1, 'chair', 5000), (2, 2, 'lamp', 1500);
        """)
        self.accounts = {
            "alice": ("learn-alice", 1, "customer"),
            "bob": ("learn-bob", 2, "customer"),
            "staff": ("learn-staff", 0, "staff"),
        }
        # Reverse index to resolve username by id for authorization checks
        self.usernames_by_id = {uid: name for name, (_, uid, _) in self.accounts.items()}
        self.sessions = {}
        self.products = {"chair": 5000, "lamp": 1500}
        self.reviews = []
        self.logs = []

    def rows(self, query):
        return [dict(row) for row in self.db.execute(query)]

    def dispatch(self, method, target, body, headers):
        url = urlsplit(target)
        query = {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        self.logs.append({"method": method, "target": target, "body": body, "headers": dict(headers)})
        if method == "GET" and url.path == "/health":
            return 200, {"status": "ok"}
        if method == "GET" and url.path == "/products":
            return 200, self.products
        if method == "POST" and url.path == "/login":
            account = self.accounts.get(body.get("username"))
            if not account or body.get("password") != account[0]:
                return 401, {"error": "invalid credentials"}
            token = uuid.uuid4().hex
            self.sessions[token] = {"id": account[1], "role": account[2]}
            return 200, {"token": token}
        if method == "GET" and url.path == "/profile":
            # Validate id as integer to prevent SQL injection
            raw_id = query.get('id', '1')
            try:
                user_id = int(raw_id)
            except (TypeError, ValueError):
                return 400, {"error": "invalid id"}
            cursor = self.db.execute("SELECT * FROM profiles WHERE id = ?", (user_id,))
            return 200, [dict(row) for row in cursor]
        if method == "GET" and url.path == "/search":
            q = query.get('q', '')
            if not isinstance(q, str):
                return 400, {"error": "invalid q"}
            cursor = self.db.execute("SELECT * FROM profiles WHERE name LIKE ?", (f"%{q}%",))
            return 200, [dict(row) for row in cursor]
        if method == "GET" and url.path == "/orders":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            owner = session["id"]
            cursor = self.db.execute("SELECT * FROM orders WHERE owner = ?", (owner,))
            return 200, [dict(row) for row in cursor]
        if method == "POST" and url.path == "/orders":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            product = body["product"]
            if product not in self.products:
                return 400, {"error": "unknown product"}
            # Always use catalog price, ignore client-provided price
            price = self.products[product]
            cursor = self.db.execute("INSERT INTO orders(owner, product, price) VALUES (?, ?, ?)",
                                     (session["id"], product, price))
            self.db.commit()
            return 201, {"id": cursor.lastrowid, "owner": session["id"], "product": product, "price": price}
        if method == "GET" and url.path == "/admin/export":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            if session.get("role") != "staff":
                return 403, {"error": "staff only"}
            return 200, self.rows("SELECT * FROM profiles")
        if method == "GET" and url.path == "/files":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            requested_user = query.get('user')
            current_user = self.usernames_by_id.get(session["id"])  # maps 1->alice, 2->bob
            if requested_user != current_user:
                return 403, {"error": "forbidden"}
            # Only allow reading the known receipt file
            requested_path = query.get('path', 'receipt.txt')
            if requested_path != 'receipt.txt':
                return 403, {"error": "forbidden"}
            name = f"files/{current_user}/receipt.txt"
            return 200, {"content": self.sandbox.read(name)}
        if method == "GET" and url.path == "/debug/logs":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            if session.get("role") != "staff":
                return 403, {"error": "staff only"}
            # Sanitize sensitive data before returning logs and limit size
            redacted = []
            for entry in self.logs[-200:]:
                e = {"method": entry.get("method"), "target": entry.get("target")}
                headers_copy = dict(entry.get("headers", {}))
                for key, val in list(headers_copy.items()):
                    lk = key.lower()
                    if lk in ("x-token", "authorization"):
                        headers_copy[key] = "***"
                e["headers"] = headers_copy
                body = entry.get("body")
                if isinstance(body, dict):
                    masked = dict(body)
                    if "password" in masked:
                        masked["password"] = "***"
                    e["body"] = masked
                else:
                    e["body"] = body
                redacted.append(e)
            return 200, redacted
        if method == "POST" and url.path == "/reviews":
            self.reviews.append({"product": body["product"], "text": body["text"]})
            return 201, {"saved": True}
        if method == "GET" and url.path == "/reviews/view":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            # Escape user-generated content to prevent XSS
            body_html = "".join(f"<p>{html.escape(str(r['text']))}</p>" for r in self.reviews)
            return 200, "<html><body>" + body_html + "</body></html>"
        if method == "GET" and url.path == "/assistant/context":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            # Validate order_id as integer and parameterize
            raw_oid = query.get('order_id', '1')
            try:
                order_id = int(raw_oid)
            except (TypeError, ValueError):
                return 400, {"error": "invalid order_id"}
            cursor = self.db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            orders = [dict(row) for row in cursor]
            if not orders:
                return 404, {"error": "order not found"}
            # Enforce ownership
            if orders[0].get("owner") != session["id"]:
                return 403, {"error": "forbidden"}
            # Minimize context: no system prompt or tool list; limit reviews size/length
            limited_reviews = [{"product": r.get("product"), "text": str(r.get("text", ""))[:200]} for r in self.reviews[-5:]]
            prompt = (
                f"Контекст заказа: {json.dumps(orders, ensure_ascii=False)}\n"
                f"Отзывы (фрагменты): {json.dumps(limited_reviews, ensure_ascii=False)}\n"
                f"Запрос пользователя: {query.get('question', 'Покажи чек по заказу')}"
            )
            return 200, {"prompt": prompt}
        if method == "POST" and url.path == "/assistant/execute":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            try:
                decision = body["decision"]
                tool = decision["tool"]
                arguments = decision.get("arguments", {})
            except Exception:
                return 400, {"error": "invalid decision"}
            user_name = self.usernames_by_id.get(session["id"])  # alice/bob
            role = session.get("role")
            if tool == "read_file":
                # Only allow reading own receipt
                path = arguments.get("path")
                if path != f"files/{user_name}/receipt.txt":
                    return 403, {"error": "forbidden"}
                return 200, {"content": self.sandbox.read(path)}
            if tool == "export_profiles":
                if role != "staff":
                    return 403, {"error": "staff only"}
                return 200, self.rows("SELECT * FROM profiles")
            if tool == "delete_tree":
                # Dangerous operation: disallow via assistant
                return 403, {"error": "forbidden"}
            return 400, {"error": "unknown tool"}
        return 404, {"error": "not found"}

    def close(self):
        self.db.close()
        self.sandbox.close()


def make_handler(shop):
    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 <= size <= 65536:
                    self.send_error(413)
                    return
                # Parse JSON body if present; treat malformed JSON as 400 without leaking details
                raw = self.rfile.read(size) if size else b""
                if raw:
                    try:
                        body = json.loads(raw)
                    except json.JSONDecodeError:
                        self.send_response(400)
                        data = json.dumps({"error": "invalid JSON"}, ensure_ascii=False).encode("utf-8")
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                else:
                    body = {}
                with shop.lock:
                    status, result = shop.dispatch(self.command, self.path, body, self.headers)
            except Exception:
                # Do not leak exception types/messages to clients
                status, result = 500, {"error": "internal error"}
            html = isinstance(result, str)
            data = (result if html else json.dumps(result, ensure_ascii=False)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = handle_request

        def log_message(self, format, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8066)
    args = parser.parse_args()
    shop = Shop()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(shop))
    server.daemon_threads = True
    print(f"Local exercise: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Disposable fixture files: {shop.sandbox.root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        shop.close()


if __name__ == "__main__":
    main()
