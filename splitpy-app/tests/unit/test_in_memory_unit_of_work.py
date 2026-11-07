"""The in-memory unit of work: writes become visible only on commit, like a transaction."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain.errors import GroupNotFound
from splitpy_core.domain.events import GroupCreated
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.domain.money import Currency

EUR = Currency("EUR")
ALICE = UserId(UUID(int=1))
GROUP_ID = GroupId(UUID(int=10))
T0 = datetime(2026, 1, 1, tzinfo=UTC)
CREATED = GroupCreated(group_id=GROUP_ID, name="Flat", currency=EUR, founder=ALICE)


def create_group(uow: InMemoryUnitOfWork) -> None:
    group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
    uow.groups.save(group)
    uow.events.append(group.pull_events(), at=T0)


class TestUnitOfWork:
    def test_committed_writes_are_visible_to_the_next_unit(self):
        uow = InMemoryUnitOfWork()
        with uow:
            create_group(uow)
            uow.commit()
        with uow:
            assert uow.groups.get(GROUP_ID).name == "Flat"
            assert uow.events.list_for_group(GROUP_ID) == [RecordedEvent(CREATED, T0)]

    def test_writes_without_commit_are_discarded(self):
        uow = InMemoryUnitOfWork()
        with uow:
            create_group(uow)
        with uow:
            with pytest.raises(GroupNotFound):
                uow.groups.get(GROUP_ID)
            assert uow.events.list_for_group(GROUP_ID) == []

    def test_writes_are_discarded_when_the_unit_fails(self):
        uow = InMemoryUnitOfWork()
        with pytest.raises(RuntimeError), uow:
            create_group(uow)
            raise RuntimeError("use case failed")
        with uow, pytest.raises(GroupNotFound):
            uow.groups.get(GROUP_ID)

    def test_writes_after_a_commit_need_another_commit(self):
        uow = InMemoryUnitOfWork()
        with uow:
            uow.commit()
            create_group(uow)
        with uow, pytest.raises(GroupNotFound):
            uow.groups.get(GROUP_ID)
