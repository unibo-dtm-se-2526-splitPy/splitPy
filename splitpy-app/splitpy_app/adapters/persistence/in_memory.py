"""In-memory adapters for tests and local runs: same contract as the database ones."""

from collections.abc import Iterable
from datetime import datetime
from typing import Self

from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain.errors import GroupNotFound
from splitpy_core.domain.events import DomainEvent
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.ports.group_repository import ConcurrencyConflict, GroupSummary


def _rebuild(group: Group, version: int) -> Group:
    """A separate Group, so changes to the one handed out never reach the stored one."""
    return Group(
        group.id,
        group.name,
        group.currency,
        group.members(),
        group.expenses(),
        group.payments(),
        group.status,
        version=version,
    )


class InMemoryGroupRepository:
    def __init__(self, groups: dict[GroupId, Group] | None = None) -> None:
        self._groups = dict(groups or {})

    def get(self, group_id: GroupId) -> Group:
        group = self._stored(group_id)
        return _rebuild(group, group.version)

    def save(self, group: Group) -> None:
        stored = self._groups.get(group.id)
        stored_version = 0 if stored is None else stored.version
        if group.version != stored_version:
            raise ConcurrencyConflict(
                f"group {group.id} is at version {stored_version}, not {group.version}"
            )
        self._groups[group.id] = _rebuild(group, group.version + 1)

    def list_summaries_for_user(self, user_id: UserId) -> list[GroupSummary]:
        return [
            GroupSummary(group.id, group.name, group.currency, group.status)
            for group in self._groups.values()
            if any(member.user_id == user_id for member in group.active_members())
        ]

    def copy(self) -> "InMemoryGroupRepository":
        return InMemoryGroupRepository(self._groups)

    def _stored(self, group_id: GroupId) -> Group:
        group = self._groups.get(group_id)
        if group is None:
            raise GroupNotFound(f"group {group_id} not found")
        return group


class InMemoryEventStore:
    def __init__(self, recorded: list[RecordedEvent] | None = None) -> None:
        self._recorded = list(recorded or [])

    def append(self, events: Iterable[DomainEvent], *, at: datetime) -> None:
        self._recorded.extend(RecordedEvent(event, at) for event in events)

    def list_for_group(self, group_id: GroupId) -> list[RecordedEvent]:
        return [r for r in reversed(self._recorded) if r.event.group_id == group_id]

    def copy(self) -> "InMemoryEventStore":
        return InMemoryEventStore(self._recorded)


class InMemoryUnitOfWork:
    """Each unit works on copies; commit makes them the stored state."""

    def __init__(self) -> None:
        self._committed_groups = InMemoryGroupRepository()
        self._committed_events = InMemoryEventStore()
        self.groups = self._committed_groups
        self.events = self._committed_events

    def __enter__(self) -> Self:
        self.groups = self._committed_groups.copy()
        self.events = self._committed_events.copy()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.groups = self._committed_groups
        self.events = self._committed_events

    def commit(self) -> None:
        self._committed_groups = self.groups
        self._committed_events = self.events
        # Later writes in the same unit need a commit of their own.
        self.groups = self._committed_groups.copy()
        self.events = self._committed_events.copy()
