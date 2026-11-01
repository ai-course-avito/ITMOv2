from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import json
from pathlib import Path
import logging
import hashlib

APP_VERSION = "0.1.0"
# Persisted JSON storage lives alongside the service code
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "subscribers.json"


class Subscription(BaseModel):
    email: EmailStr
    name: Optional[str] = None


def load_subscribers() -> List[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_subscribers(items: List[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open('w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


app = FastAPI(title="Subscription Service", version=APP_VERSION)

# Basic logger for audit of unauthorized access and critical search errors
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": APP_VERSION}


@app.post("/subscribe", status_code=201)
def subscribe(sub: Subscription):
    items = load_subscribers()
    if any(i.get('email') == sub.email for i in items):
        raise HTTPException(status_code=409, detail="already subscribed")
    items.append(sub.dict())
    save_subscribers(items)
    return {"email": sub.email, "status": "subscribed"}


@app.get("/subscribers")
def subscribers():
    return load_subscribers()


@app.delete("/subscribers/{email}", status_code=204)
def unsubscribe(email: str):
    items = load_subscribers()
    before = len(items)
    items = [i for i in items if i.get('email') != email]
    if len(items) == before:
        raise HTTPException(status_code=404, detail="not found")
    save_subscribers(items)
    return


def _safe_username_from_record(record: dict) -> str:
    """Derive username from a subscriber record without exposing emails.

    Use provided name; fallback to local-part of email; ensure string.
    """
    name = (record.get('name') or '').strip()
    if name:
        return name
    email = (record.get('email') or '').strip()
    if '@' in email:
        return email.split('@', 1)[0]
    return email or ""


def _safe_display_name_from_record(record: dict) -> str:
    # Deprecated: display_name removed from API response. Kept for backward-compat if needed.
    return _safe_username_from_record(record)


def _safe_id_from_email(email: str) -> str:
    """Deterministic, stable id derived from email without exposing it.

    Use sha1 hex (first 12 chars) for brevity.
    """
    try:
        digest = hashlib.sha1((email or "").lower().encode('utf-8')).hexdigest()
    except Exception:
        digest = hashlib.sha1(b"").hexdigest()
    return digest[:12]


def _to_safe_user(record: dict) -> dict:
    """Map subscriber record to safe user DTO with allowed fields only."""
    email = record.get('email') or ''
    return {
        "id": _safe_id_from_email(email),
        "username": _safe_username_from_record(record),
        "status": "active",  # no blocked state in simple service yet
    }


def _normalize_query(q: Optional[str]) -> str:
    if q is None:
        raise HTTPException(status_code=422, detail="query parameter 'q' is required")
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(status_code=422, detail="query length must be at least 2 characters")
    if len(q) > 100:
        raise HTTPException(status_code=422, detail="query length must not exceed 100 characters")
    return q


def _paginate(items: List[dict], page: int, page_size: int) -> tuple[List[dict], int]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 50:
        page_size = 50
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


@app.get("/search/users")
@app.get("/api/subscribers/search")
def search_users(
    q: Optional[str] = None,
    query: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    x_auth_user: Optional[str] = Header(default=None, alias="X-Auth-User"),
):
    # Authentication gate: require X-Auth-User header
    if not x_auth_user:
        logger.warning("unauthorized search attempt")
        raise HTTPException(status_code=401, detail="authentication required")

    # Normalize and validate query (accept both 'q' and 'query')
    query_val = q if q is not None else query
    query = _normalize_query(query_val)

    # Load and transform to safe users
    try:
        records = load_subscribers()
    except Exception as exc:
        logger.error("failed to load subscribers: %s", exc)
        records = []
    users = [_to_safe_user(r) for r in records]

    # Case-insensitive substring match on username, Unicode-aware
    folded = query.casefold()
    matched = [u for u in users if folded in (u.get('username') or '').casefold()]

    # Sort by username asc then id asc
    matched.sort(key=lambda u: (u.get('username') or "", u.get('id') or ""))

    # Paginate
    page_items, total = _paginate(matched, page, page_size)

    return {
        "page": max(1, page),
        "page_size": min(max(page_size, 1), 50),
        "total": total,
        "items": page_items,
    }

# Serve UI static files from practices/practice_05/ui
# We compute the UI directory relative to this file to keep repo structure flexible.
UI_DIR = Path(__file__).resolve().parents[1] / "ui"
if UI_DIR.exists():
    # Mount at root so opening http://localhost:8000/ serves the UI
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
