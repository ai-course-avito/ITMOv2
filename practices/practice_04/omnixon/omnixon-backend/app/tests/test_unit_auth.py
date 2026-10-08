"""unit auth tests: from a secret (and X-Act-As-Agent) to a Principal, or to the answer the service has always given"""

import pytest

from database.models import Agent, AgentConnection, Token
from domain.access import AccessPolicy
from domain.chain import CallChain
from services.auth import AuthError, AuthService
from shared import NOW


class Tokens:
    def __init__(self, *tokens):
        self.tokens = {t.token_sha256: t for t in tokens}

    async def by_secret(self, secret):
        from database.models import token_hash

        return self.tokens.get(token_hash(secret))


class Agents:
    async def get(self, agent_id):
        return Agent(id=agent_id, prompt="p", model_id=0, timestamp=NOW) if 0 < agent_id < 100 else None


class Connections:
    def __init__(self, *pairs):
        self.pairs = set(pairs)

    async def find(self, a, b):
        return AgentConnection(id=1, agent1_id=a, agent2_id=b, description="d", timestamp=NOW) if (a, b) in self.pairs else None


def service(role="user", agent_id=1):
    from database.models import token_hash

    token = Token(id=3, name="t", agent_id=agent_id, role=role, token_sha256=token_hash("secret"), timestamp=NOW)
    return AuthService(Tokens(token), Agents(), Connections(), AccessPolicy())


async def refused(auth, secret, act_as=None):
    with pytest.raises(AuthError) as caught:
        await auth.authenticate(secret, act_as)
    return caught.value


@pytest.mark.asyncio
async def test_the_three_refusals_are_the_texts_the_service_has_always_sent():
    auth = service("user")
    missing = await refused(auth, None)
    assert (missing.status, missing.body, missing.as_json) == (403, "Authentication failed: API token is missing", False)
    wrong = await refused(auth, "nope")
    assert (wrong.status, wrong.body, wrong.as_json) == (403, "Authentication failed: wrong token", False)
    forbidden = await refused(auth, "secret", "2")
    assert (forbidden.status, forbidden.body, forbidden.as_json) == (403, "Forbidden: X-Act-As-Agent needs the admin role", True)


@pytest.mark.asyncio
async def test_a_token_gets_its_own_agent_and_an_admin_the_agent_it_acts_as():
    principal = await service("user").authenticate("secret", None)
    assert (principal.token.id, principal.agent.id, principal.chain) == (3, 1, None)
    assert (await service("user").authenticate("secret", "  ")).agent.id == 1  # an empty header is no header
    admin = await service("admin").authenticate("secret", "7")
    assert (admin.agent.id, admin.token.agent_id) == (7, 1)


@pytest.mark.asyncio
async def test_an_unknown_agent_is_not_found_for_an_admin_and_forbidden_below():
    unknown = await refused(service("admin"), "secret", "500")
    assert (unknown.status, unknown.body, unknown.as_json) == (404, "Agent not found", True)
    below = await refused(service("user"), "secret", "500")
    assert below.status == 403


@pytest.mark.asyncio
async def test_a_non_numeric_act_as_is_refused_like_an_unknown_agent():
    # today: the id becomes -1, which is nobody's: an admin may "act as" it (admins may act as any) and finds no agent
    assert (await refused(service("admin"), "secret", "not a number")).status == 404
    assert (await refused(service("user"), "secret", "not a number")).status == 403
