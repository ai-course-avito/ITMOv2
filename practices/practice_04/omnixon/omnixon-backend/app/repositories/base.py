from __future__ import annotations

from core import async_logfire_class_decorator

from .database import Database


class Repository:
    """The SQL of one aggregate. Methods take every id they need; none reads a request or applies a rule. Public coroutines are logged
    (at debug, arguments masked by name)."""

    def __init__(self, database: Database):
        self.db = database

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        async_logfire_class_decorator(cls)
