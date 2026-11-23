"""Database adapters on SQLAlchemy: same contract as the in-memory ones."""

from collections.abc import Iterable
from datetime import datetime
from typing import Self

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from splitpy_app.adapters.persistence.mappers import (
    event_from_row,
    event_to_row,
    group_from_row,
    group_to_row,
)
from splitpy_app.adapters.persistence.models import EventRow, GroupRow, MemberRow
from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain.errors import GroupNotFound
from splitpy_core.domain.events import DomainEvent
from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.domain.money import Currency
from splitpy_core.ports.group_repository import ConcurrencyConflict, GroupSummary


class SqlAlchemyGroupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, group_id: GroupId) -> Group:
        row = self._session.get(GroupRow, group_id.value)
        if row is None:
            raise GroupNotFound(f"group {group_id} not found")
        return group_from_row(row)

    def save(self, group: Group) -> None:
        fresh = group_to_row(group)
        fresh.version = group.version + 1
        if group.version == 0:
            if self._session.get(GroupRow, group.id.value) is not None:
                raise ConcurrencyConflict(f"group {group.id} already exists")
            self._session.add(fresh)
            try:
                self._session.flush()
            except IntegrityError as error:
                # Another unit created it after the check above.
                raise ConcurrencyConflict(f"group {group.id} already exists") from error
            return
        # Checking and bumping the version in one statement leaves no room for a concurrent save.
        updated = self._session.execute(
            update(GroupRow)
            .where(GroupRow.id == group.id.value, GroupRow.version == group.version)
            .values(name=fresh.name, status=fresh.status, version=fresh.version)
        )
        if updated.rowcount == 0:
            raise ConcurrencyConflict(f"group {group.id} changed since version {group.version}")
        row = self._session.get(GroupRow, group.id.value, populate_existing=True)
        assert row is not None
        row.members.clear()
        row.expenses.clear()
        row.payments.clear()
        # The old rows go first: the new ones reuse their primary keys.
        self._session.flush()
        row.members, row.expenses, row.payments = fresh.members, fresh.expenses, fresh.payments
        self._session.flush()

    def list_summaries_for_user(self, user_id: UserId) -> list[GroupSummary]:
        rows = self._session.execute(
            select(GroupRow.id, GroupRow.name, GroupRow.currency, GroupRow.status)
            .join(GroupRow.members)
            .where(MemberRow.user_id == user_id.value, MemberRow.left_at.is_(None))
        )
        return [
            GroupSummary(GroupId(id), name, Currency(currency), GroupStatus(status))
            for id, name, currency, status in rows
        ]


class SqlAlchemyEventStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, events: Iterable[DomainEvent], *, at: datetime) -> None:
        self._session.add_all(event_to_row(event, at=at) for event in events)
        self._session.flush()

    def list_for_group(self, group_id: GroupId) -> list[RecordedEvent]:
        rows = self._session.scalars(
            select(EventRow).where(EventRow.group_id == group_id.value)
            # Events appended together share the instant: the id keeps their order.
            .order_by(EventRow.occurred_at.desc(), EventRow.id.desc())
        )
        return [event_from_row(row) for row in rows]


class SqlAlchemyUnitOfWork:
    """One session per unit: commit commits it, leaving the unit discards the rest."""

    groups: SqlAlchemyGroupRepository
    events: SqlAlchemyEventStore

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def __enter__(self) -> Self:
        self._session = self._sessions()
        self.groups = SqlAlchemyGroupRepository(self._session)
        self.events = SqlAlchemyEventStore(self._session)
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._session.close()

    def commit(self) -> None:
        self._session.commit()
