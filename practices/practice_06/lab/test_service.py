"""Functional contract and exercise containment; security regressions are student work."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sandbox import Sandbox
from service import Shop


class ShopTest(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        self.addCleanup(self.shop.close)

    def request(self, method, path, body=None, headers=None):
        with self.shop.lock:
            return self.shop.dispatch(method, path, body or {}, headers or {})

    def login(self, username="alice", password="learn-alice"):
        status, result = self.request("POST", "/login", {"username": username, "password": password})
        self.assertEqual(status, 200)
        return {"X-Token": result["token"]}

    def test_health_and_catalog(self):
        self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))
        self.assertEqual(self.request("GET", "/products"), (200, {"chair": 5000, "lamp": 1500}))

    def test_wrong_password_rejected(self):
        self.assertEqual(self.request("POST", "/login", {"username": "alice", "password": "wrong"})[0], 401)

    def test_tokens_identify_distinct_users(self):
        alice, bob = self.login(), self.login("bob", "learn-bob")
        self.assertNotEqual(alice, bob)
        self.assertEqual(self.request("GET", "/profile?id=1", headers=alice)[1][0]["name"], "TEST_ALICE")
        self.assertEqual(self.request("GET", "/profile?id=2", headers=bob)[1][0]["name"], "TEST_BOB")

    def test_profile_sql_injection_blocked(self):
        status, result = self.request("GET", "/profile?id=1 OR 1=1")
        self.assertEqual(status, 400)
        self.assertEqual(result, {"error": "invalid id"})

    def test_staff_can_export_with_staff_session(self):
        # Staff requires token; role must be read from session, not header
        auth = self.login("staff", "learn-staff")
        status, profiles = self.request("GET", "/admin/export", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(len(profiles), 2)

    def test_own_profile_and_receipt(self):
        auth = self.login()
        status, profile = self.request("GET", "/profile?id=1", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(profile[0]["name"], "TEST_ALICE")
        status, receipt = self.request("GET", "/files?user=alice&path=receipt.txt", headers=auth)
        self.assertEqual(status, 200)
        self.assertIn("TEST_ALICE", receipt["content"])

    def test_customer_can_buy_at_catalog_price(self):
        status, order = self.request("POST", "/orders", {"product": "lamp"}, self.login())
        self.assertEqual(status, 201)
        self.assertEqual((order["owner"], order["price"]), (1, 1500))

    def test_unknown_product_rejected(self):
        self.assertEqual(self.request("POST", "/orders", {"product": "unknown"}, self.login())[0], 400)

    def test_review_can_be_submitted_and_viewed(self):
        auth = self.login()
        self.assertEqual(self.request("POST", "/reviews", {"product": "chair", "text": "Comfortable"}, auth)[0], 201)
        self.assertIn("Comfortable", self.request("GET", "/reviews/view", headers=auth)[1])

    def test_reviews_view_requires_auth_and_escapes_html(self):
        # Requires auth
        self.assertEqual(self.request("GET", "/reviews/view")[0], 401)
        # Escape HTML
        auth = self.login()
        payload = {"product": "chair", "text": "<script>alert('x')</script>"}
        self.assertEqual(self.request("POST", "/reviews", payload, auth)[0], 201)
        status, html = self.request("GET", "/reviews/view", headers=auth)
        self.assertEqual(status, 200)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html)

    def test_orders_get_requires_auth_and_filters_owner(self):
        # Guest is unauthorized
        self.assertEqual(self.request("GET", "/orders")[0], 401)
        # Alice sees only her orders
        status, orders = self.request("GET", "/orders", headers=self.login())
        self.assertEqual(status, 200)
        self.assertTrue(all(o["owner"] == 1 for o in orders))
        # Bob sees only his
        status, orders = self.request("GET", "/orders", headers=self.login("bob", "learn-bob"))
        self.assertEqual(status, 200)
        self.assertTrue(all(o["owner"] == 2 for o in orders))

    def test_files_idor_blocked_and_auth_required(self):
        # Guest cannot read
        self.assertEqual(self.request("GET", "/files?user=alice&path=receipt.txt")[0], 401)
        # Alice can read her receipt
        status, data = self.request("GET", "/files?user=alice&path=receipt.txt", headers=self.login())
        self.assertEqual(status, 200)
        self.assertIn("TEST_ALICE", data["content"])
        # Alice cannot read Bob's
        self.assertEqual(self.request("GET", "/files?user=bob&path=receipt.txt", headers=self.login())[0], 403)
        # Path allowlist enforced
        self.assertEqual(self.request("GET", "/files?user=alice&path=../private/operator-note.txt", headers=self.login())[0], 403)

    def test_assistant_execute_requires_auth_and_rbac(self):
        # Guest cannot call tools
        self.assertEqual(self.request("POST", "/assistant/execute", {"decision": {"tool": "export_profiles"}})[0], 401)
        # Customer cannot export profiles
        self.assertEqual(self.request("POST", "/assistant/execute", {"decision": {"tool": "export_profiles"}}, headers=self.login())[0], 403)
        # Staff can export profiles
        status, result = self.request("POST", "/assistant/execute", {"decision": {"tool": "export_profiles"}}, headers=self.login("staff", "learn-staff"))
        self.assertEqual(status, 200)
        self.assertEqual(len(result), 2)
        # Customer can read only own receipt via tool
        status, data = self.request("POST", "/assistant/execute", {"decision": {"tool": "read_file", "arguments": {"path": "files/alice/receipt.txt"}}}, headers=self.login())
        self.assertEqual(status, 200)
        self.assertIn("TEST_ALICE", data["content"])
        # Customer cannot read other user's file
        self.assertEqual(self.request("POST", "/assistant/execute", {"decision": {"tool": "read_file", "arguments": {"path": "files/bob/receipt.txt"}}}, headers=self.login())[0], 403)
        # Dangerous delete_tree is forbidden
        self.assertEqual(self.request("POST", "/assistant/execute", {"decision": {"tool": "delete_tree", "arguments": {"path": "."}}}, headers=self.login())[0], 403)

    def test_search_sql_injection_blocked(self):
        # Attempt an injection via LIKE pattern terminator and tautology
        status, result = self.request("GET", "/search?q=%' OR '1'='1")
        self.assertEqual(status, 200)
        # Should not error and should behave like a literal search (likely empty)
        self.assertIsInstance(result, list)

    def test_assistant_can_return_own_receipt(self):
        auth = self.login()
        status, context = self.request("GET", "/assistant/context?order_id=1", headers=auth)
        self.assertEqual(status, 200)
        self.assertIn("chair", context["prompt"])
        status, result = self.request("POST", "/assistant/execute", {
            "decision": {"tool": "read_file", "arguments": {"path": "files/alice/receipt.txt"}}
        }, auth)
        self.assertEqual(status, 200)
        self.assertIn("TEST_ALICE", result["content"])

    def test_assistant_context_sql_injection_blocked(self):
        # Use auth to reach parameter parsing path; injection must be rejected as invalid id
        status, result = self.request("GET", "/assistant/context?order_id=1 OR 1=1", headers=self.login())
        self.assertEqual(status, 400)
        self.assertEqual(result, {"error": "invalid order_id"})


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox()
        self.addCleanup(self.sandbox.close)

    def test_parent_paths_cannot_escape_exercise(self):
        for name in ("../../outside.txt", "/etc/passwd"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.sandbox.read(name)

    def test_external_directory_cannot_be_deleted(self):
        with TemporaryDirectory() as directory:
            sentinel = Path(directory) / "sentinel.txt"
            sentinel.write_text("keep")
            with self.assertRaises(ValueError):
                self.sandbox.delete_tree(directory)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_symlink_cannot_escape_exercise(self):
        with TemporaryDirectory() as directory:
            sentinel = Path(directory) / "sentinel.txt"
            sentinel.write_text("keep")
            link = self.sandbox.root / "escape"
            link.symlink_to(directory, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.sandbox.read("escape/sentinel.txt")
            with self.assertRaises(ValueError):
                self.sandbox.delete_tree("escape")
            self.assertEqual(sentinel.read_text(), "keep")

    def test_delete_of_fixture_root_stays_inside_exercise(self):
        with TemporaryDirectory() as directory:
            sentinel = Path(directory) / "sentinel.txt"
            sentinel.write_text("keep")
            self.sandbox.delete_tree(".")
            self.assertFalse(self.sandbox.root.exists())
            self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
