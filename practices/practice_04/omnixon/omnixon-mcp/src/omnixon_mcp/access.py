"""Roles, who a token is, and which routes of the service need which role.

Mirrors omnixon-backend/app/access.py and the `require(...)` of its routes. The service stays the authority (it answers 403 to anything not
allowed); this only keeps a model from being offered tools it would be refused, and tells it the limits that apply to it. `ADMIN_ONLY` is
checked against the tools by tests (a tool needs the role of the highest route it uses), and the routes against the service's OpenAPI.
"""

from __future__ import annotations

from dataclasses import dataclass

ROLES = ("regular", "user", "admin", "owner")
RANK = {role: rank for rank, role in enumerate(ROLES)}

Route = tuple[str, str]  # ("GET", "/api/v1/admin/agents/{agent_id}")

# Routes of the admin API that need more than `user` (the rest of /api/v1/admin/ needs `user`,
# everything else under /api/v1/ is open to `regular`)
ADMIN_ONLY: set[Route] = {
    ("GET", "/api/v1/admin/agents"),
    ("POST", "/api/v1/admin/agents"),
    ("DELETE", "/api/v1/admin/agents/{agent_id}"),
    ("POST", "/api/v1/admin/agents/{agent_id}/mcp-servers/{mcp_server_id}"),
    ("GET", "/api/v1/admin/mcp-servers"),
    ("POST", "/api/v1/admin/models"),
    ("PATCH", "/api/v1/admin/models/{model_id}"),
    ("DELETE", "/api/v1/admin/models/{model_id}"),
    # connections between agents: a whole router with require("admin")
    ("GET", "/api/v1/admin/agent-connections"),
    ("POST", "/api/v1/admin/agent-connections"),
    ("GET", "/api/v1/admin/agent-connections/{connection_id}"),
    ("PATCH", "/api/v1/admin/agent-connections/{connection_id}"),
    ("DELETE", "/api/v1/admin/agent-connections/{connection_id}"),
}

# What a token of each role may hand out (GRANTS in the service)
HANDS_OUT = {
    "regular": "none",
    "user": "regular and user, for your own agent",
    "admin": "regular and user, for any agent",
    "owner": "any role (regular, user, admin, owner), for any agent",
}


def lowest_role(route: Route) -> str:
    """The lowest role the service lets through to this route."""
    if route in ADMIN_ONLY:
        return "admin"
    return "user" if route[1].startswith("/api/v1/admin/") else "regular"


@dataclass(frozen=True)
class Identity:
    """The token an MCP request came with, as the service describes it (GET /api/v1/tokens/self)."""

    token_id: int
    name: str
    role: str
    agent_id: int

    @property
    def rank(self) -> int:
        return RANK[self.role]

    @property
    def is_admin(self) -> bool:
        return self.rank >= RANK["admin"]

    @property
    def mcp_user(self) -> str:
        """The user every message of this token goes as: an agent never speaks for a person."""
        return f"agentmcp_{self.agent_id}"
