"""Deliberately vulnerable local shop. All identities and data are synthetic."""

import argparse
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
        self.sessions = {}
        self.products = {"chair": 5000, "lamp": 1500}
        self.reviews = []
        self.logs = []
        # Reverse map to derive a stable username by account id
        self.usernames_by_id = {acc[1]: name for name, acc in self.accounts.items()}

    def rows(self, query):
        return [dict(row) for row in self.db.execute(query)]

    def rows_params(self, query, params=()):
        """Execute a parameterized SQL query and return list of dict rows."""
        cursor = self.db.execute(query, params)
        return [dict(row) for row in cursor]

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
            # Store session with id, role, and username for later checks
            self.sessions[token] = {"id": account[1], "role": account[2], "username": body.get("username")}
            return 200, {"token": token}
        if method == "GET" and url.path == "/profile":
            # Require auth and use only session id (prevent IDOR + SQLi)
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            return 200, self.rows_params("SELECT * FROM profiles WHERE id = ?", (session["id"],))
        if method == "GET" and url.path == "/search":
            # Parameterized LIKE search to avoid SQL injection
            q = query.get("q", "")
            return 200, self.rows_params("SELECT * FROM profiles WHERE name LIKE ?", (f"%{q}%",))
        if method == "GET" and url.path == "/orders":
            # Only return current user's orders
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            return 200, self.rows_params("SELECT * FROM orders WHERE owner = ?", (session["id"],))
        if method == "POST" and url.path == "/orders":
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            product = body["product"]
            if product not in self.products:
                return 400, {"error": "unknown product"}
            # Take price only from catalog to prevent tampering
            price = self.products[product]
            cursor = self.db.execute("INSERT INTO orders(owner, product, price) VALUES (?, ?, ?)",
                                     (session["id"], product, price))
            self.db.commit()
            return 201, {"id": cursor.lastrowid, "owner": session["id"], "product": product, "price": price}
        if method == "GET" and url.path == "/admin/export":
            # Check actual session role; do not trust headers
            session = self.sessions.get(headers.get("X-Token"))
            if not session or session.get("role") != "staff":
                return 403, {"error": "staff only"}
            return 200, self.rows("SELECT * FROM profiles")
        if method == "GET" and url.path == "/files":
            # Allow only reading own files; verify against session
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            requested_user = query.get("user", "")
            allowed_username = self.usernames_by_id.get(session["id"]) or session.get("username")
            # If client provides a user, it must match own username or numeric id
            if requested_user and requested_user not in (allowed_username, str(session["id"])):
                return 403, {"error": "forbidden"}
            # Build path and ensure it stays under the allowed directory
            rel_path = query.get("path", "receipt.txt")
            allowed_dir = self.sandbox.path(f"files/{allowed_username}")
            candidate = self.sandbox.path(f"files/{allowed_username}/{rel_path}")
            if allowed_dir not in candidate.parents and candidate != allowed_dir:
                return 403, {"error": "forbidden"}
            return 200, {"content": candidate.read_text(encoding="utf-8")}
        if method == "GET" and url.path == "/debug/logs":
            return 200, self.logs.copy()
        if method == "POST" and url.path == "/reviews":
            self.reviews.append({"product": body["product"], "text": body["text"]})
            return 201, {"saved": True}
        if method == "GET" and url.path == "/reviews/view":
            return 200, "<html><body>" + "".join(f"<p>{r['text']}</p>" for r in self.reviews) + "</body></html>"
        if method == "GET" and url.path == "/assistant/context":
            # Parameterized query and structured context to reduce prompt injection risk
            order_id = query.get("order_id", "1")
            try:
                order_id_int = int(order_id)
            except ValueError:
                order_id_int = 1
            orders = self.rows_params("SELECT * FROM orders WHERE id = ?", (order_id_int,))
            reviews_json = json.dumps(self.reviews, ensure_ascii=False)
            orders_json = json.dumps(orders, ensure_ascii=False)
            user_question = query.get("question", "Покажи чек по заказу")
            prompt = (
                "Ты помощник магазина. Верни JSON с полями tool и arguments.\n"
                "Инструменты: read_file(path), export_profiles(), delete_tree(path).\n"
                "<review_data>" + reviews_json + "</review_data>\n"
                "<order_data>" + orders_json + "</order_data>\n"
                "<user_question>" + user_question + "</user_question>"
            )
            return 200, {"prompt": prompt}
        if method == "POST" and url.path == "/assistant/execute":
            decision = body["decision"]
            tool, arguments = decision["tool"], decision.get("arguments", {})
            session = self.sessions.get(headers.get("X-Token"))
            if not session:
                return 401, {"error": "login required"}
            allowed_username = self.usernames_by_id.get(session["id"]) or session.get("username")
            allowed_dir = self.sandbox.path(f"files/{allowed_username}")
            if tool == "read_file":
                # Normalize to user's files directory and forbid cross-user prefixes
                path_raw = arguments["path"].lstrip("/")
                if path_raw.startswith("files/"):
                    first = path_raw.split("/", 2)[1] if "/" in path_raw else path_raw
                    if first != allowed_username:
                        return 403, {"error": "forbidden"}
                if not path_raw.startswith(f"files/{allowed_username}/"):
                    path_raw = f"files/{allowed_username}/" + path_raw
                candidate = self.sandbox.path(path_raw)
                if allowed_dir not in candidate.parents and candidate != allowed_dir:
                    return 403, {"error": "forbidden"}
                try:
                    return 200, {"content": candidate.read_text(encoding="utf-8")}
                except FileNotFoundError:
                    return 404, {"error": "not found"}
            if tool == "export_profiles":
                if session.get("role") != "staff":
                    return 403, {"error": "staff only"}
                return 200, self.rows("SELECT * FROM profiles")
            if tool == "delete_tree":
                path_raw = arguments["path"].lstrip("/")
                if path_raw.startswith("files/"):
                    first = path_raw.split("/", 2)[1] if "/" in path_raw else path_raw
                    if first != allowed_username:
                        return 403, {"error": "forbidden"}
                if not path_raw.startswith(f"files/{allowed_username}/"):
                    path_raw = f"files/{allowed_username}/" + path_raw
                candidate = self.sandbox.path(path_raw)
                if allowed_dir not in candidate.parents and candidate != allowed_dir:
                    return 403, {"error": "forbidden"}
                # Call sandbox with normalized relative path string
                self.sandbox.delete_tree(str(candidate.relative_to(self.sandbox.root)))
                return 200, {"deleted": str(candidate)}
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
                body = json.loads(self.rfile.read(size)) if size else {}
                with shop.lock:
                    status, result = shop.dispatch(self.command, self.path, body, self.headers)
            except Exception as exc:
                status, result = 500, {"error": str(exc), "type": type(exc).__name__}
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
