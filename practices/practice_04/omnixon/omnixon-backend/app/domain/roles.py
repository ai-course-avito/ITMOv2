from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """What a token may do: regular < user < admin < owner."""

    REGULAR = "regular"
    USER = "user"
    ADMIN = "admin"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return _ORDER.index(self) + 1

    @property
    def grants(self) -> int:
        """The highest rank of a token this role may hand out (and so manage): regular none, user and admin up to `user`, owner any."""
        return _GRANTS[self]

    def at_least(self, other: "Role") -> bool:
        return self.rank >= other.rank

    def may_hand_out(self, other: "Role") -> bool:
        return other.rank <= self.grants


_ORDER = [Role.REGULAR, Role.USER, Role.ADMIN, Role.OWNER]
_GRANTS = {Role.REGULAR: 0, Role.USER: 2, Role.ADMIN: 2, Role.OWNER: 4}
