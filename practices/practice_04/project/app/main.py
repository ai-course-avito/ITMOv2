# version 3
from __future__ import annotations

import re
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:  # Prefer Pydantic v2-style validators when available
    from pydantic import field_validator  # type: ignore
except Exception:  # Fallback for Pydantic v1 environments
    from pydantic import validator as field_validator  # type: ignore


app = FastAPI()


# =====================
# Pydantic models
# =====================
TAG_RE = re.compile(r"^[A-Za-z0-9-]+$")


class TaskIn(BaseModel):
    title: str = Field(...)
    tags: List[str] = Field(...)

    # Title: strip, non-empty, <= 100
    @field_validator("title")
    def validate_title(cls, v: str):  # type: ignore[override]
        s = v.strip() if isinstance(v, str) else ""
        if not s:
            raise ValueError("title must be non-empty after strip")
        if len(s) > 100:
            raise ValueError("title must be at most 100 characters")
        return s

    # Tags: 1..5 items; each non-empty, alnum or hyphen only, <= 20; return stripped values
    @field_validator("tags")
    def validate_tags(cls, v: List[str]):  # type: ignore[override]
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        if not (1 <= len(v) <= 5):
            raise ValueError("tags must contain between 1 and 5 items")
        cleaned: List[str] = []
        for t in v:
            if not isinstance(t, str):
                raise ValueError("each tag must be a string")
            s = t.strip()
            if not s:
                raise ValueError("tag must be non-empty")
            if len(s) > 20:
                raise ValueError("tag must be at most 20 characters")
            if not TAG_RE.fullmatch(s):
                raise ValueError("tag must contain only letters, digits, or hyphen")
            cleaned.append(s)
        return cleaned


class Task(BaseModel):
    id: int
    title: str
    tags: List[str]


# =====================
# In-memory storage
# =====================
_tasks: List[Task] = []
_next_id: int = 1


def _create_task(data: TaskIn) -> Task:
    global _next_id
    task = Task(id=_next_id, title=data.title, tags=data.tags)
    _tasks.append(task)
    _next_id += 1
    return task


# =====================
# Routes
# =====================
@app.post("/tasks", response_model=Task, status_code=201)
def create_task(payload: TaskIn):
    # Pydantic validators will enforce 422 on invalid payload
    return _create_task(payload)


@app.get("/tasks", response_model=List[Task])
def list_tasks():
    return _tasks


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    for idx, t in enumerate(_tasks):
        if t.id == task_id:
            del _tasks[idx]
            return
    raise HTTPException(status_code=404, detail="Task not found")


# =====================
# Static files (mounted last to avoid intercepting API routes like /tasks)
# =====================
app.mount(
    "/",
    StaticFiles(directory="app/static", html=True),
    name="static",
)
