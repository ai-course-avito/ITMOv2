"""unit access policy tests: every rule, for every role"""

import pytest

from database.models import Agent, Token
from domain.access import AccessPolicy, Principal
from domain.chain import CallChain
from domain.errors import Forbidden
from domain.roles import Role
from shared import NOW

policy = AccessPolicy()


def principal(role, agent_id=1, chain=None, acting_as=None):
    token = Token(id=5, name="t", agent_id=agent_id, role=role, timestamp=NOW)
    agent = Agent(id=acting_as or agent_id, prompt="p", model_id=0, timestamp=NOW)
    return Principal(token, agent, chain)


@pytest.mark.parametrize("held", list(Role))
@pytest.mark.parametrize("needed", list(Role))
def test_a_role_passes_the_door_of_its_own_rank_and_below(held, needed):
    if held.at_least(needed):
        policy.require(principal(held.value), needed)
    else:
        with pytest.raises(Forbidden, match=f"^Forbidden: needs the {needed.value} role$"):
            policy.require(principal(held.value), needed)


def test_below_admin_a_token_keeps_to_its_own_agent():
    policy.ensure_agent(principal("user", agent_id=1), 1)
    with pytest.raises(Forbidden, match="may only use its own agent"):
        policy.ensure_agent(principal("user", agent_id=1), 2)
    policy.ensure_agent(principal("admin", agent_id=1), 2)
    assert policy.agent_scope(principal("user", agent_id=1), None) == 1
    assert policy.agent_scope(principal("owner", agent_id=1, acting_as=7), None) == 7
    assert policy.agent_scope(principal("admin"), 9) == 9


def test_acting_as_another_agent_is_for_admins_or_an_agent_with_a_connection():
    assert policy.may_act_as(principal("admin"), 9, has_connection=False)
    assert not policy.may_act_as(principal("user"), 9, has_connection=True)  # no chain: a client asking
    chain = CallChain(agents=(1,), human="alice")
    assert policy.may_act_as(principal("user", chain=chain), 9, has_connection=True)
    assert not policy.may_act_as(principal("user", chain=chain), 9, has_connection=False)


def test_handing_out_roles_and_managing_tokens():
    policy.ensure_may_hand_out(principal("user"), Role.USER)
    with pytest.raises(Forbidden, match="may not hand out the admin role"):
        policy.ensure_may_hand_out(principal("admin"), Role.ADMIN)
    policy.ensure_may_hand_out(principal("owner"), Role.OWNER)
    other = Token(id=9, name="o", agent_id=2, role="regular", timestamp=NOW)
    with pytest.raises(Forbidden, match="may not manage a token of that role or agent"):
        policy.ensure_may_manage(principal("user", agent_id=1), other)
    policy.ensure_may_manage(principal("admin", agent_id=1), other)


def test_mcp_servers_are_seen_when_attached_and_changed_when_nothing_else_uses_them():
    policy.ensure_mcp_use(principal("user", agent_id=1), [1], change=True)
    policy.ensure_mcp_use(principal("user", agent_id=1), [1, 2], change=False)
    with pytest.raises(Forbidden, match="not attached to the token's agent"):
        policy.ensure_mcp_use(principal("user", agent_id=1), [2], change=False)
    with pytest.raises(Forbidden, match="shared with another agent"):
        policy.ensure_mcp_use(principal("user", agent_id=1), [1, 2], change=True)
    policy.ensure_mcp_use(principal("admin", agent_id=1), [], change=True)
