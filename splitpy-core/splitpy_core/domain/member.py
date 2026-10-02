"""Group membership: a member leaves by getting a left_at, never by being deleted."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from splitpy_core.domain.ids import UserId


class Role(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


@dataclass(frozen=True, slots=True)
class Member:
    user_id: UserId
    role: Role
    joined_at: datetime
    left_at: datetime | None = None

    def is_active(self) -> bool:
        return self.left_at is None
