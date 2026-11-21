"""What only a real database can show: concurrent units of work and the instants it stores."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from support import ALICE, BOB, EUR, GROUP_ID, T0

from splitpy_app.adapters.persistence.database import SqlAlchemyUnitOfWork
from splitpy_core.domain.group import Group
from splitpy_core.domain.member import Role
from splitpy_core.ports.group_repository import ConcurrencyConflict


def store_group(uow: SqlAlchemyUnitOfWork) -> None:
    with uow:
        uow.groups.save(Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0))
        uow.commit()


class TestConcurrentUnits:
    def test_rf16_the_second_of_two_concurrent_saves_is_a_conflict(self, sessions):
        store_group(SqlAlchemyUnitOfWork(sessions))
        first, second = SqlAlchemyUnitOfWork(sessions), SqlAlchemyUnitOfWork(sessions)
        with first, second:
            group_in_first = first.groups.get(GROUP_ID)
            group_in_second = second.groups.get(GROUP_ID)
            group_in_first.add_member(BOB, Role.MEMBER, by=ALICE, at=T0)
            first.groups.save(group_in_first)
            first.commit()
            group_in_second.archive(by=ALICE)
            with pytest.raises(ConcurrencyConflict):
                second.groups.save(group_in_second)
        with first:
            assert first.groups.get(GROUP_ID).version == 2

    def test_rf16_two_units_creating_the_same_group_conflict(self, sessions):
        first, second = SqlAlchemyUnitOfWork(sessions), SqlAlchemyUnitOfWork(sessions)
        with first, second:
            first.groups.save(Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0))
            # The first unit commits after the second looked for the group, before it inserts.
            event.listen(sessions, "before_flush", lambda *_: first.commit(), once=True)
            with pytest.raises(ConcurrencyConflict):
                second.groups.save(Group.create(GROUP_ID, "Trip", EUR, founder=BOB, at=T0))


class TestInstants:
    def test_instants_come_back_in_utc_whatever_offset_they_had(self, sessions):
        uow = SqlAlchemyUnitOfWork(sessions)
        rome = timezone(timedelta(hours=1))
        with uow:
            group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
            group.add_member(BOB, Role.MEMBER, by=ALICE, at=datetime(2026, 1, 1, 13, tzinfo=rome))
            uow.groups.save(group)
            uow.commit()
        with uow:
            members = {member.user_id: member for member in uow.groups.get(GROUP_ID).members()}
        assert members[BOB].joined_at == datetime(2026, 1, 1, 12, tzinfo=UTC)
        assert members[BOB].joined_at.tzinfo is UTC
