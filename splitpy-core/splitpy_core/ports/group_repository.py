"""Storage port for the Group aggregate, the only repository of the core."""

from dataclasses import dataclass
from typing import ClassVar, Protocol

from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.domain.money import Currency


class ConcurrencyConflict(Exception):
    """The group changed since it was loaded. Not a domain error: the client reloads and retries."""

    code: ClassVar[str] = "CONCURRENCY_CONFLICT"


@dataclass(frozen=True, slots=True)
class GroupSummary:
    id: GroupId
    name: str
    currency: Currency
    status: GroupStatus


class GroupRepository(Protocol):
    def get(self, group_id: GroupId) -> Group:
        """Raises GroupNotFound."""
        ...

    def save(self, group: Group) -> None:
        """Raises ConcurrencyConflict if the stored version is not the one the group was loaded at."""
        ...

    def list_summaries_for_user(self, user_id: UserId) -> list[GroupSummary]:
        """The groups the user is an active member of."""
        ...
