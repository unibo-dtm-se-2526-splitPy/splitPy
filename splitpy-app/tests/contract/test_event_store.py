"""Contract every EventStore implementation must pass: the activity feed reads from it."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from support import EUR

from splitpy_app.adapters.persistence.database import (
    SqlAlchemyEventStore,
    SqlAlchemyGroupRepository,
)
from splitpy_app.adapters.persistence.in_memory import InMemoryEventStore
from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain.events import GroupArchived, MemberAdded, MemberRemoved
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.domain.member import Role

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
GROUP_ID = GroupId(UUID(int=10))
OTHER_GROUP_ID = GroupId(UUID(int=11))
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)

ADDED = MemberAdded(group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE)
REMOVED = MemberRemoved(group_id=GROUP_ID, user_id=BOB, by=ALICE)
ARCHIVED = GroupArchived(group_id=GROUP_ID, by=ALICE)


@pytest.fixture(params=["in_memory", "sqlite", "postgres"])
def event_store(request):
    if request.param == "in_memory":
        yield InMemoryEventStore()
        return
    with request.getfixturevalue("database")(request.param)() as session:
        # Events reference their group, so the groups are stored first.
        groups = SqlAlchemyGroupRepository(session)
        for group_id in (GROUP_ID, OTHER_GROUP_ID):
            groups.save(Group.create(group_id, "Flat", EUR, founder=ALICE, at=T0))
        yield SqlAlchemyEventStore(session)


class TestEventStore:
    def test_rf15_events_are_listed_newest_first_with_their_instant(self, event_store):
        event_store.append([ADDED], at=T0)
        event_store.append([REMOVED, ARCHIVED], at=T1)
        assert event_store.list_for_group(GROUP_ID) == [
            RecordedEvent(ARCHIVED, T1),
            RecordedEvent(REMOVED, T1),
            RecordedEvent(ADDED, T0),
        ]

    def test_rf15_the_instant_orders_the_feed_not_the_order_of_appending(self, event_store):
        # Two use cases can commit in the opposite order of the instants they read.
        event_store.append([ARCHIVED], at=T1)
        event_store.append([ADDED], at=T0)
        assert event_store.list_for_group(GROUP_ID) == [
            RecordedEvent(ARCHIVED, T1),
            RecordedEvent(ADDED, T0),
        ]

    def test_rf15_only_the_events_of_the_group_are_listed(self, event_store):
        other = GroupArchived(group_id=OTHER_GROUP_ID, by=ALICE)
        event_store.append([ADDED, other], at=T0)
        assert event_store.list_for_group(GROUP_ID) == [RecordedEvent(ADDED, T0)]

    def test_group_with_no_events_has_an_empty_feed(self, event_store):
        assert event_store.list_for_group(GROUP_ID) == []
