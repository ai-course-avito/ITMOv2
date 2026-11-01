from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import json
from pathlib import Path

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

# Serve UI static files from practices/practice_05/ui
# We compute the UI directory relative to this file to keep repo structure flexible.
UI_DIR = Path(__file__).resolve().parents[1] / "ui"
if UI_DIR.exists():
    # Mount at root so opening http://localhost:8000/ serves the UI
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
