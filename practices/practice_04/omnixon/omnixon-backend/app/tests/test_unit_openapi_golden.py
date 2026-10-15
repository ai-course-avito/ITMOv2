"""The OpenAPI schema is the contract the library and the panel read: the restructuring must not move it."""

import json
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden_openapi.json"


def _differences(a, b, path="$"):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                yield f"{path}.{key}: only in {'golden' if key in a else 'now'}"
            else:
                yield from _differences(a[key], b[key], f"{path}.{key}")
    elif a != b:
        yield f"{path}: {str(a)[:60]!r} != {str(b)[:60]!r}"


def test_the_openapi_schema_is_the_golden_one():
    from main import app

    golden, now = json.loads(GOLDEN.read_text()), json.loads(json.dumps(app.openapi()))
    assert not list(_differences(golden, now)), list(_differences(golden, now))[:20]
