import json
from pathlib import Path

from fastapi.testclient import TestClient
import sys
from pathlib import Path as _Path

# Ensure practice_05 module root is on sys.path for direct imports
_ROOT = _Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from service.app import app, DATA_DIR, DATA_FILE, save_subscribers


client = TestClient(app)


def setup_module(module):
    # Ensure clean data dir
    if DATA_FILE.exists():
        DATA_FILE.unlink()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Seed subscribers
    seed = [
        {"email": "ivan@example.com", "name": "ivan"},
        {"email": "ivana@example.com", "name": "Ivana"},
        {"email": "petr@example.com", "name": "Petr"},
    ]
    save_subscribers(seed)


def _auth_headers():
    return {"X-Auth-User": "tester"}


def test_search_requires_auth():
    response = client.get("/search/users", params={"q": "iv"})
    assert response.status_code == 401


def test_query_validation_min_length():
    response = client.get("/search/users", params={"q": "i"}, headers=_auth_headers())
    assert response.status_code == 422


def test_query_validation_max_length():
    response = client.get(
        "/search/users",
        params={"q": "x" * 101},
        headers=_auth_headers(),
    )
    assert response.status_code == 422


def test_search_substring_case_insensitive_and_pagination():
    response = client.get(
        "/search/users",
        params={"q": "IVA", "page": 1, "page_size": 20},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total"] >= 2
    usernames = [item["username"] for item in body["items"]]
    # Both ivan and Ivana should match case-insensitively
    assert any(u.lower().startswith("ivan") for u in usernames)


def test_empty_results_are_ok():
    response = client.get(
        "/search/users",
        params={"q": "zzz"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_sensitive_fields_not_exposed():
    response = client.get(
        "/search/users",
        params={"q": "iv"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    for item in body["items"]:
        assert set(item.keys()) == {"id", "username", "display_name", "status"}
