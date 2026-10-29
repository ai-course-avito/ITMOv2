"""Regression tests for the vulnerabilities found and fixed in this exercise.

Each test encodes one finding from ../REPORT_01.md (attack IDs in the docstrings refer to
../evidence/attack.py, where the same scenarios were run as standalone HTTP attacks against a
real server process, before and after the fix: ../evidence/before/attacks.json and
../evidence/after/attacks.json). These tests run against the in-process Shop directly, the same
way test_service.py does, so they are part of `make test` and catch any regression of the fix.
"""

import unittest

from sandbox import Sandbox
from service import Shop


class SecurityFixTest(unittest.TestCase):
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

    # A01 / A10 — IDOR on /profile and /files
    def test_customer_cannot_read_another_customers_profile(self):
        status, profile = self.request("GET", "/profile?id=2", headers=self.login("alice"))
        self.assertEqual(status, 200)
        self.assertEqual(profile[0]["name"], "TEST_ALICE")

    def test_customer_cannot_read_another_customers_receipt(self):
        status, _ = self.request("GET", "/files?user=bob&path=receipt.txt", headers=self.login("alice"))
        self.assertEqual(status, 403)

    # A02 / A03 / A04 — SQL injection
    def test_profile_sql_injection_is_neutralized(self):
        status, profile = self.request("GET", "/profile?id=" + "0 OR 1=1", headers=self.login("alice"))
        self.assertEqual(status, 200)
        # Even a staff session, which is allowed to pass an explicit id, gets it as data, not SQL.
        status, profile = self.request("GET", "/profile?id=" + "0 OR 1=1",
                                       headers=self.login("staff", "learn-staff"))
        self.assertEqual(status, 400)

    def test_search_requires_staff_and_is_parameterized(self):
        status, _ = self.request("GET", "/search?q=" + "' OR '1'='1", headers=self.login("alice"))
        self.assertEqual(status, 403)
        status, rows = self.request("GET", "/search?q=TEST", headers=self.login("staff", "learn-staff"))
        self.assertEqual(status, 200)
        self.assertTrue(all("TEST" in r["name"] for r in rows))

    # A05 — broken access control on /orders
    def test_orders_require_a_session_and_are_scoped_to_owner(self):
        self.assertEqual(self.request("GET", "/orders")[0], 401)
        status, orders = self.request("GET", "/orders", headers=self.login("alice"))
        self.assertEqual(status, 200)
        self.assertTrue(all(o["owner"] == 1 for o in orders))

    # A06 / A07 — client-supplied price
    def test_order_price_ignores_client_value(self):
        status, order = self.request("POST", "/orders", {"product": "chair", "price": -5000},
                                     self.login("alice"))
        self.assertEqual(status, 201)
        self.assertEqual(order["price"], 5000)

    # A08 / A09 — forged X-Role header
    def test_forged_role_header_does_not_grant_staff_access(self):
        headers = {**self.login("bob", "learn-bob"), "X-Role": "staff"}
        self.assertEqual(self.request("GET", "/admin/export", headers=headers)[0], 403)
        self.assertEqual(self.request("GET", "/admin/export", headers={"X-Role": "staff"})[0], 403)

    # A11 — path traversal inside the sandbox to the private operator note
    def test_customer_cannot_reach_private_operator_note(self):
        status, _ = self.request(
            "GET", "/files?user=..&path=private/operator-note.txt", headers=self.login("alice"))
        self.assertEqual(status, 403)

    # A12 — unauthenticated, unredacted debug logs
    def test_debug_logs_require_staff_and_redact_secrets(self):
        self.request("POST", "/login", {"username": "bob", "password": "learn-bob"})
        self.assertEqual(self.request("GET", "/debug/logs")[0], 403)
        status, logs = self.request("GET", "/debug/logs", headers=self.login("staff", "learn-staff"))
        self.assertEqual(status, 200)
        dump = str(logs)
        self.assertNotIn("learn-bob", dump)

    # A13 — anonymous review submission
    def test_reviews_require_authentication(self):
        self.assertEqual(self.request("POST", "/reviews", {"product": "chair", "text": "x"})[0], 401)

    # A14 — stored XSS
    def test_review_html_is_escaped_on_render(self):
        self.request("POST", "/reviews", {"product": "chair", "text": "<script>alert(1)</script>"},
                     headers=self.login("alice"))
        _, page = self.request("GET", "/reviews/view")
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    # A15 — IDOR on the assistant context (someone else's order)
    def test_assistant_context_is_scoped_to_own_order(self):
        status, _ = self.request("GET", "/assistant/context?order_id=2", headers=self.login("alice"))
        self.assertEqual(status, 403)

    # A18 / A26 — forced decision, facade does not blindly trust arbitrary tool calls
    def test_execute_rejects_read_file_without_a_matching_grant(self):
        auth = self.login("alice")
        status, _ = self.request("POST", "/assistant/execute",
                                 {"decision": {"tool": "read_file", "arguments": {"path": "files/bob/receipt.txt"}}},
                                 headers=auth)
        self.assertEqual(status, 403)

    def test_execute_allows_read_file_only_after_a_legitimate_context_grant(self):
        auth = self.login("alice")
        self.request("GET", "/assistant/context?order_id=1", headers=auth)
        status, result = self.request(
            "POST", "/assistant/execute",
            {"decision": {"tool": "read_file", "arguments": {"path": "files/alice/receipt.txt"}}}, headers=auth)
        self.assertEqual(status, 200)
        self.assertIn("TEST_ALICE", result["content"])

    # A20 — export_profiles from a non-staff session
    def test_execute_rejects_export_profiles_for_customers(self):
        status, _ = self.request("POST", "/assistant/execute", {"decision": {"tool": "export_profiles"}},
                                 self.login("alice"))
        self.assertEqual(status, 403)

    # A19 / A21 / A22 — the most severe finding: delete_tree through the AI facade
    def test_execute_never_allows_delete_tree_even_with_no_session(self):
        status, _ = self.request("POST", "/assistant/execute",
                                 {"decision": {"tool": "delete_tree", "arguments": {"path": "."}}})
        self.assertEqual(status, 401)
        self.assertTrue(self.shop.sandbox.root.exists())

    def test_execute_never_allows_delete_tree_even_from_a_valid_session(self):
        auth = self.login("alice")
        status, _ = self.request("POST", "/assistant/execute",
                                 {"decision": {"tool": "delete_tree", "arguments": {"path": "."}}}, auth)
        self.assertEqual(status, 403)
        self.assertTrue(self.shop.sandbox.root.exists())

    # A23 — internal error details (paths, exception types) no longer leak to the client
    def test_file_not_found_does_not_leak_internal_path(self):
        auth = self.login("alice")
        self.request("GET", "/assistant/context?order_id=1", headers=auth)
        # Forge a grant-shaped path that does not exist to exercise the error path.
        self.shop.assistant_grants[auth["X-Token"]].add("files/alice/missing.txt")
        status, result = self.request(
            "POST", "/assistant/execute",
            {"decision": {"tool": "read_file", "arguments": {"path": "files/alice/missing.txt"}}}, headers=auth)
        self.assertEqual(status, 404)
        self.assertNotIn("Temp", str(result))
        self.assertNotIn("FileNotFoundError", str(result))

    # A24 — malformed bodies return 400, not an unhandled 500
    def test_malformed_bodies_return_400_not_500(self):
        auth = self.login("alice")
        status, _ = self.request("POST", "/orders", {"nothing": 1}, headers=auth)
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/assistant/execute", {"decision": "not-a-dict"}, headers=auth)
        self.assertEqual(status, 400)

    # A25 — brute force protection on /login
    def test_login_locks_out_after_repeated_failures(self):
        for _ in range(5):
            self.request("POST", "/login", {"username": "staff", "password": "wrong"})
        status, result = self.request("POST", "/login", {"username": "staff", "password": "wrong"})
        self.assertEqual(status, 429)
        # Even the correct password is locked out until the counter resets (new Shop instance).
        status, _ = self.request("POST", "/login", {"username": "staff", "password": "learn-staff"})
        self.assertEqual(status, 429)


class SandboxUnchangedTest(unittest.TestCase):
    """Sanity check that the untouched sandbox.py still enforces its own physical boundary."""

    def test_sandbox_still_rejects_traversal_outside_its_root(self):
        sandbox = Sandbox()
        self.addCleanup(sandbox.close)
        with self.assertRaises(ValueError):
            sandbox.read("../../outside.txt")


if __name__ == "__main__":
    unittest.main()
