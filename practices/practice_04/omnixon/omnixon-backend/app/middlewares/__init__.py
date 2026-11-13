from fastapi import FastAPI
from .postgres import DatabaseMiddleware


def setup_middleware(app: FastAPI):
    app.add_middleware(DatabaseMiddleware)


__all__ = [
    "setup_middleware",
]
