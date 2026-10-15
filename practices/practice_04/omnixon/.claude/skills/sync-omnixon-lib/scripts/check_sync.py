"""Show what omnixon-library must change to match omnixon-backend.

Dumps the service's OpenAPI schema, compares it with the library's snapshot
(tests/server_openapi.json) and with the routes omnixon/main.py calls, and prints
a list of differences. Exit code: 0 in sync, 1 differences found, 2 dump failed.

    python3 check_sync.py            # report only, the snapshot is not touched
    python3 check_sync.py --write    # report, then replace the snapshot with the fresh schema
    python3 check_sync.py --fresh F  # compare with an existing dump F instead of dumping

Standard library only, so it runs without either project's virtualenv.
"""

from __future__ import annotations  # `str | None` on the macOS system python3 (3.9)

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

METHODS = ("get", "post", "put", "patch", "delete")

# Routes the client reaches without a "{self.base_url}..." f-string, or does not need
IGNORED_ROUTES = {
    ("GET", "/api/v1/"),  # check_connection() calls the bare base_url
    ("GET", "/healthz"),  # liveness, for orchestrators
    ("GET", "/readyz"),  # ready() builds it from the root url
    ("GET", "/metrics"),  # Prometheus
}

# A call in main.py: `.get(f"{self.admin_url}agents/{agent_id}"` or `"POST", f"{client.base_url}request-stream"`
CALL = re.compile(
    r'(?:\.(get|post|put|patch|delete)\(|"(GET|POST|PUT|PATCH|DELETE)",)\s*'
    r'f"\{(?:self|client)\.(base_url|admin_url)\}([^"?]*)"'
)
PREFIX = {"base_url": "/api/v1/", "admin_url": "/api/v1/admin/"}


def kind(prop: dict) -> str:
    """Type of a property, written the way tests/test_server_contract.py compares them."""
    if "$ref" in prop:
        return "ref:" + prop["$ref"].split("/")[-1].replace("-Input", "").replace("-Output", "")
    if "anyOf" in prop:
        parts = sorted(kind(p) for p in prop["anyOf"] if p.get("type") != "null")
        nullable = any(p.get("type") == "null" for p in prop["anyOf"])
        return "|".join(parts) + ("?" if nullable else "")
    if prop.get("type") == "array":
        return "array[" + kind(prop.get("items", {})) + "]"
    return prop.get("type", "any")


def fields(schema: dict) -> dict:
    required = set(schema.get("required", []))
    return {
        name: kind(prop) + ("" if name in required else " (optional)")
        for name, prop in schema.get("properties", {}).items()
    }


def body_of(op: dict) -> str | None:
    content = op.get("requestBody", {}).get("content", {})
    for media in content.values():
        return kind(media.get("schema", {}))
    return None


def answer_of(op: dict) -> str | None:
    for status, response in op.get("responses", {}).items():
        if status.startswith("2"):
            for media in response.get("content", {}).values():
                return kind(media.get("schema", {}))
    return None


def operations(spec: dict) -> dict:
    """(METHOD, path) -> {"params": {...}, "body": ..., "answer": ...}"""
    ops = {}
    for path, item in spec.get("paths", {}).items():
        for method, op in item.items():
            if method not in METHODS:
                continue
            params = {
                f"{p['in']}:{p['name']}": kind(p.get("schema", {}))
                + ("" if p.get("required") else " (optional)")
                for p in op.get("parameters", [])
                if p["in"] in ("path", "query")
            }
            ops[(method.upper(), path)] = {
                "params": params,
                "body": body_of(op),
                "answer": answer_of(op),
            }
    return ops


def compare_maps(old: dict, new: dict) -> list[str]:
    lines = []
    for key in sorted(set(new) - set(old)):
        lines.append(f"+ {key}: {new[key]}")
    for key in sorted(set(old) - set(new)):
        lines.append(f"- {key}: {old[key]}")
    for key in sorted(set(old) & set(new)):
        if old[key] != new[key]:
            lines.append(f"~ {key}: {old[key]} -> {new[key]}")
    return lines


def route_changes(old: dict, new: dict) -> list[str]:
    old_ops, new_ops = operations(old), operations(new)
    out = []
    for key in sorted(set(new_ops) - set(old_ops)):
        op = new_ops[key]
        out.append(f"NEW ROUTE {key[0]} {key[1]}  params={op['params']} body={op['body']} answer={op['answer']}")
    for key in sorted(set(old_ops) - set(new_ops)):
        out.append(f"REMOVED ROUTE {key[0]} {key[1]}")
    for key in sorted(set(old_ops) & set(new_ops)):
        a, b = old_ops[key], new_ops[key]
        changes = compare_maps(a["params"], b["params"])
        for part in ("body", "answer"):
            if a[part] != b[part]:
                changes.append(f"~ {part}: {a[part]} -> {b[part]}")
        if changes:
            out.append(f"CHANGED ROUTE {key[0]} {key[1]}")
            out.extend("    " + line for line in changes)
    return out


def model_changes(old: dict, new: dict) -> list[str]:
    def models(spec):
        schemas = spec.get("components", {}).get("schemas", {})
        return {name.replace("-Input", "").replace("-Output", ""): s for name, s in schemas.items()}

    old_m, new_m = models(old), models(new)
    out = []
    for name in sorted(set(new_m) - set(old_m)):
        out.append(f"NEW MODEL {name}: {fields(new_m[name])}")
    for name in sorted(set(old_m) - set(new_m)):
        out.append(f"REMOVED MODEL {name}")
    for name in sorted(set(old_m) & set(new_m)):
        changes = compare_maps(fields(old_m[name]), fields(new_m[name]))
        if changes:
            out.append(f"CHANGED MODEL {name}")
            out.extend("    " + line for line in changes)
    return out


def shape(path: str) -> str:
    """/users/{user_id}/chats/{chat_id} -> /users/{}/chats/{}: the client names placeholders its own way."""
    return re.sub(r"\{[^}]*\}", "{}", path)


def client_routes(main_py: str) -> set:
    calls = set()
    for m in CALL.finditer(main_py):
        method = (m.group(1) or m.group(2)).upper()
        calls.add((method, shape(PREFIX[m.group(3)] + m.group(4))))
    return calls


def coverage(spec: dict, main_py: str) -> list[str]:
    served = {(method, shape(path)) for method, path in operations(spec)}
    called = client_routes(main_py)
    ignored = {(m, shape(p)) for m, p in IGNORED_ROUTES}
    out = [f"NOT CALLED BY THE CLIENT {m} {p}" for m, p in sorted(served - called - ignored)]
    out += [f"CLIENT CALLS A ROUTE THE SERVICE DOES NOT HAVE {m} {p}" for m, p in sorted(called - served)]
    return out


def dump(backend: Path, target: Path) -> None:
    result = subprocess.run(
        ["uv", "run", "--quiet", "python", "scripts/dump_openapi.py", str(target)],
        cwd=backend,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-4000:])
        sys.exit(f"dump_openapi.py failed in {backend} (exit {result.returncode}); the backend does not import")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4],
                        help="folder with omnixon-backend and omnixon-library (default: the project of this skill)")
    parser.add_argument("--fresh", type=Path, help="use this OpenAPI dump instead of dumping the backend")
    parser.add_argument("--write", action="store_true", help="replace the library's snapshot with the fresh schema")
    args = parser.parse_args()

    backend, library = args.root / "omnixon-backend", args.root / "omnixon-library"
    snapshot = library / "tests" / "server_openapi.json"

    if args.fresh:
        fresh_text = args.fresh.read_text()
    else:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "openapi.json"
            try:
                dump(backend, target)
            except SystemExit as exc:
                print(exc, file=sys.stderr)
                sys.exit(2)
            fresh_text = target.read_text()

    old, new = json.loads(snapshot.read_text()), json.loads(fresh_text)
    main_py = (library / "omnixon" / "main.py").read_text()

    sections = {
        "Routes changed in the service since the snapshot": route_changes(old, new),
        "Models changed in the service since the snapshot": model_changes(old, new),
        "Routes the client and the service disagree on": coverage(new, main_py),
    }
    found = False
    for title, lines in sections.items():
        print(f"## {title}")
        print("\n".join(lines) if lines else "(none)")
        print()
        found = found or bool(lines)

    if args.write and snapshot.read_text() != fresh_text:
        snapshot.write_text(fresh_text)
        print(f"Snapshot updated: {snapshot}")
    elif not args.write and old != new:
        print("The snapshot is out of date: run again with --write, then `uv run pytest` in omnixon-library.")

    print("RESULT:", "differences found" if found else "in sync")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
