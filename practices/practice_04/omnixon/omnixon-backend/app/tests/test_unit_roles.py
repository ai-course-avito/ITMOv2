"""unit role tests: who outranks whom, who may hand out what, which tokens a token may manage"""

import pytest

from domain.roles import Role
from shared import NOW
from domain.entities import Token

HANDS_OUT = {"regular": set(), "user": {"regular", "user"}, "admin": {"regular", "user"}, "owner": {"regular", "user", "admin", "owner"}}


def token(role, agent_id=1):
    return Token(id=1, name="t", agent_id=agent_id, role=role, timestamp=NOW)


def test_roles_are_ranked():
    assert [r.rank for r in Role] == [1, 2, 3, 4]
    assert Role.ADMIN.at_least(Role.USER) and not Role.USER.at_least(Role.ADMIN)


@pytest.mark.parametrize("giver", list(Role))
def test_which_roles_a_role_may_hand_out(giver):
    assert {r.value for r in Role if giver.may_hand_out(r)} == HANDS_OUT[giver.value]


def test_a_token_manages_tokens_up_to_what_it_hands_out_on_agents_it_may_use():
    assert token("user", 1).may_manage(token("regular", 1))
    assert not token("user", 1).may_manage(token("regular", 2))  # another agent
    assert not token("user", 1).may_manage(token("admin", 1))  # above what it hands out
    assert token("admin", 1).may_manage(token("user", 2))  # any agent
    assert not token("admin", 1).may_manage(token("admin", 2))
    assert token("owner", 1).may_manage(token("owner", 9))
    assert not token("regular", 1).may_manage(token("regular", 1))


def test_a_token_knows_its_role_object():
    assert token("admin").as_role is Role.ADMIN
