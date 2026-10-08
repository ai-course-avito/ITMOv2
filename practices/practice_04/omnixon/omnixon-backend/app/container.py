"""The composition root: the one place that knows which class is made from which (GRASP Creator).

Everything else is given what it needs. A test builds a container with `overrides` to put a fake where a real thing would be made."""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Type, TypeVar, Union

from config import Settings

T = TypeVar("T")
Closer = Callable[[], Union[None, Awaitable[None]]]


class Container:
    def __init__(
        self,
        settings: Settings,
        *,
        factories: Optional[Mapping[type, Callable[[], Any]]] = None,
        overrides: Optional[Mapping[type, Any]] = None,
    ) -> None:
        self.settings = settings
        self._factories: Dict[type, Callable[[], Any]] = dict(factories or {})
        self._overrides: Dict[type, Any] = dict(overrides or {})
        self._instances: Dict[type, Any] = {}
        self._closers: List[Closer] = []

    def register(self, cls: Type[T], factory: Callable[[], T]) -> None:
        self._factories[cls] = factory

    def get(self, cls: Type[T]) -> T:
        if cls in self._overrides:
            return self._overrides[cls]
        if cls not in self._instances:
            self._instances[cls] = self._factories[cls]()
        return self._instances[cls]

    def on_close(self, closer: Closer) -> None:
        """Something to undo at shutdown; closers run in the reverse order of their registration."""
        self._closers.append(closer)

    async def aclose(self) -> None:
        closers, self._closers = self._closers[::-1], []
        for closer in closers:
            result = closer()
            if inspect.isawaitable(result):
                await result
