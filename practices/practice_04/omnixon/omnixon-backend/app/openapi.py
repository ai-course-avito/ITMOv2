"""The roles in the OpenAPI schema.

A route's role is the one thing the schema could not say: it comes from `Depends(require(role))` (see access.py), on the route or on its router.
This reads it from there, so it can never drift from what the route enforces, and writes it into every operation:

- `x-min-role`: the lowest role that gets through (`regular`, `user` or `admin`; `none` for the routes that need no token). Handler-level rules
  (which agent a token may touch, which tokens it may hand out) depend on what the route is about and stay in the description of the route;
- `security`: the Bearer token, and a line in the description saying the role.

Clients and tools read `x-min-role` instead of keeping their own list of routes (omnixon-mcp checks its offer to a role against it).
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from domain.entities import RANK
from middlewares.postgres import PUBLIC_PATHS

SCHEME = "BearerToken"
NO_TOKEN = "none"


def required_role(dependant: Dependant) -> Optional[str]:
    """The highest role among the `require(...)` dependencies of a route, or None if it has none."""
    found = [getattr(dependant.call, "min_role", None)]
    found += [required_role(child) for child in dependant.dependencies]
    roles = [role for role in found if role]
    return max(roles, key=RANK.__getitem__) if roles else None


def role_of(route: APIRoute) -> str:
    if route.path in PUBLIC_PATHS:
        return NO_TOKEN
    return required_role(route.dependant) or "regular"  # a route with no requirement still needs a token


def add_roles(app: FastAPI) -> None:
    """Make `app.openapi()` say the role of every operation."""
    generate = app.openapi

    def openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = generate()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})[SCHEME] = {
            "type": "http",
            "scheme": "bearer",
            "description": "A token of the service (`Authorization: Bearer <token>`). Its role decides which routes it may call.",
        }
        for route in app.routes:
            if not isinstance(route, APIRoute) or not route.include_in_schema:
                continue
            role = role_of(route)
            for method in route.methods:
                operation = schema["paths"].get(route.path_format, {}).get(method.lower())
                if operation is None:
                    continue
                operation["x-min-role"] = role
                if role == NO_TOKEN:
                    operation["security"] = []
                    continue
                operation["security"] = [{SCHEME: []}]
                needs = "any token" if role == "regular" else f"a token with the **{role}** role or higher"
                operation["description"] = f"{operation.get('description', '').rstrip()}\n\nNeeds {needs}.".lstrip()
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
