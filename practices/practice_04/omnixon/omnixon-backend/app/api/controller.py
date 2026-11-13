"""Controllers: a class per resource whose methods are the HTTP endpoints.

    class Things(Controller):
        prefix = "/api/v1"

        def __init__(self, things: ThingService):
            self.things = things
            super().__init__()

        @endpoint.get("/things", summary="List the things")
        async def get_things(self, principal: Principal = Depends(current_principal)) -> list[Thing]: ...

A controller gets its services in the constructor (made by the container); only what belongs to the request comes through `Depends`.
The method's name is the operation's name, so renaming a method renames the operation in the OpenAPI schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, List, Optional

from fastapi import APIRouter, Depends, Request

from domain.access import AccessPolicy
from domain.roles import Role

_policy = AccessPolicy()


def require_role(role: str) -> Callable:
    """A dependency that lets only tokens of `role` or a higher one through; it carries `min_role`, which the OpenAPI schema reports."""
    needed = Role(role)

    async def check(request: Request) -> None:
        _policy.require(request.state.principal, needed)

    check.min_role = role  # type: ignore[attr-defined]
    return check


def current_principal(request: Request):
    """Who is asking (set by the authentication middleware)."""
    return request.state.principal


@dataclass
class _Marked:
    verb: str
    path: str
    min_role: Optional[str]
    options: Dict[str, Any] = field(default_factory=dict)


class _EndpointFactory:
    def _mark(self, verb: str):
        def make(path: str, *, min_role: Optional[str] = None, **options: Any):
            def decorate(method):
                method.__endpoint__ = _Marked(verb, path, min_role, options)
                return method

            return decorate

        return make

    def __getattr__(self, verb: str):
        if verb in ("get", "post", "patch", "put", "delete"):
            return self._mark(verb)
        raise AttributeError(verb)


endpoint = _EndpointFactory()


class Controller:
    """Collects the marked methods of the class (base classes first, in the order they are written) into `router`."""

    prefix: ClassVar[str] = ""
    tags: ClassVar[Optional[List[str]]] = None
    default_role: ClassVar[Optional[str]] = None  # the role every endpoint needs at least (an endpoint's own `min_role` may be higher)

    def __init__(self) -> None:
        self.router = APIRouter()
        seen = set()
        for cls in reversed(type(self).__mro__):
            for name, member in vars(cls).items():
                marked = getattr(member, "__endpoint__", None)
                if marked is None or name in seen:
                    continue
                seen.add(name)
                role = marked.min_role or self.default_role
                dependencies = [Depends(require_role(role))] if role else []
                self.router.add_api_route(
                    f"{self.prefix}{marked.path}",
                    getattr(self, name),
                    methods=[marked.verb.upper()],
                    dependencies=dependencies,
                    tags=self.tags,
                    **marked.options,
                )
