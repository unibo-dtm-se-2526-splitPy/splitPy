"""Ports of the application layer: the transaction boundary and the store of domain events."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self

from splitpy_core.domain.events import DomainEvent
from splitpy_core.domain.ids import GroupId
from splitpy_core.ports.group_repository import GroupRepository


@dataclass(frozen=True, slots=True)
class RecordedEvent:
    event: DomainEvent
    at: datetime


class EventStore(Protocol):
    def append(self, events: Iterable[DomainEvent], *, at: datetime) -> None:
        """Events carry no instant: the use case reads the Clock and passes it here."""
        ...

    def list_for_group(self, group_id: GroupId) -> list[RecordedEvent]:
        """Newest first, as the activity feed shows them (RF-15)."""
        ...


class UnitOfWork(Protocol):
    """One per use case: writes to groups and events become visible together, on commit."""

    groups: GroupRepository
    events: EventStore

    def __enter__(self) -> Self: ...

    def __exit__(self, *exc_info: object) -> None:
        """Discards whatever was not committed."""
        ...

    def commit(self) -> None: ...
