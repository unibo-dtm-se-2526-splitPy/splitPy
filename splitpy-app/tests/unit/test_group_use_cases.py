"""Use cases that create a group, manage its members, archive it and list a user's groups."""

import pytest
from support import (
    ALICE,
    BOB,
    CAROL,
    EUR,
    FIRST_ID,
    GROUP_ID,
    NOW,
    FixedClock,
    SequentialIds,
    load,
    stored_group,
)

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.application.ports import RecordedEvent
from splitpy_app.application.use_cases.groups import (
    AddMember,
    ArchiveGroup,
    CreateGroup,
    ListMyGroups,
    RemoveMember,
)
from splitpy_core.domain.errors import GroupNotFound, NotAnAdministrator
from splitpy_core.domain.events import GroupArchived, GroupCreated, MemberAdded, MemberRemoved
from splitpy_core.domain.group import GroupStatus
from splitpy_core.domain.ids import GroupId
from splitpy_core.domain.member import Role
from splitpy_core.ports.group_repository import GroupSummary


def feed(uow: InMemoryUnitOfWork, group_id: GroupId = GROUP_ID) -> list[RecordedEvent]:
    with uow:
        return uow.events.list_for_group(group_id)


class TestCreateGroup:
    def test_rf04_group_is_stored_with_the_founder_as_admin(self):
        uow = InMemoryUnitOfWork()
        group = CreateGroup(uow, FixedClock(), SequentialIds()).execute(
            name="Flat", currency=EUR, founder=ALICE
        )
        stored = load(uow, group.id)
        [founder] = stored.active_members()
        assert (stored.name, stored.currency) == ("Flat", EUR)
        assert (founder.user_id, founder.role, founder.joined_at) == (ALICE, Role.ADMIN, NOW)

    def test_rf04_group_id_comes_from_the_id_generator(self):
        uow = InMemoryUnitOfWork()
        group = CreateGroup(uow, FixedClock(), SequentialIds()).execute(
            name="Flat", currency=EUR, founder=ALICE
        )
        assert group.id == GroupId(FIRST_ID)

    def test_rf15_creation_is_recorded_at_the_clock_instant(self):
        uow = InMemoryUnitOfWork()
        group = CreateGroup(uow, FixedClock(), SequentialIds()).execute(
            name="Flat", currency=EUR, founder=ALICE
        )
        created = GroupCreated(group_id=group.id, name="Flat", currency=EUR, founder=ALICE)
        assert feed(uow, group.id) == [RecordedEvent(created, NOW)]


class TestAddMember:
    def test_rf05_admin_adds_a_member_at_the_clock_instant(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow)
        AddMember(uow, FixedClock()).execute(
            group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE
        )
        added = next(m for m in load(uow).active_members() if m.user_id == BOB)
        assert (added.role, added.joined_at) == (Role.MEMBER, NOW)

    def test_rf15_addition_is_recorded(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow)
        AddMember(uow, FixedClock()).execute(
            group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE
        )
        added = MemberAdded(group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE)
        assert feed(uow) == [RecordedEvent(added, NOW)]

    def test_rf05_rejected_command_stores_nothing(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        with pytest.raises(NotAnAdministrator):
            AddMember(uow, FixedClock()).execute(
                group_id=GROUP_ID, user_id=CAROL, role=Role.MEMBER, by=BOB
            )
        assert load(uow).version == 1
        assert feed(uow) == []

    def test_unknown_group_is_not_found(self):
        with pytest.raises(GroupNotFound):
            AddMember(InMemoryUnitOfWork(), FixedClock()).execute(
                group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE
            )


class TestRemoveMember:
    def test_rf05_admin_removes_a_member_at_the_clock_instant(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        RemoveMember(uow, FixedClock()).execute(group_id=GROUP_ID, user_id=BOB, by=ALICE)
        removed = next(m for m in load(uow).members() if m.user_id == BOB)
        assert removed.left_at == NOW
        assert feed(uow) == [
            RecordedEvent(MemberRemoved(group_id=GROUP_ID, user_id=BOB, by=ALICE), NOW)
        ]

    def test_rf05_admin_leaving_hands_over_to_the_successor(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        RemoveMember(uow, FixedClock()).execute(
            group_id=GROUP_ID, user_id=ALICE, by=ALICE, successor=BOB
        )
        [successor] = load(uow).active_members()
        assert (successor.user_id, successor.role) == (BOB, Role.ADMIN)


class TestArchiveGroup:
    def test_rf16_admin_archives_the_group(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow)
        ArchiveGroup(uow, FixedClock()).execute(group_id=GROUP_ID, by=ALICE)
        assert load(uow).status == GroupStatus.ARCHIVED
        assert feed(uow) == [RecordedEvent(GroupArchived(group_id=GROUP_ID, by=ALICE), NOW)]


class TestListMyGroups:
    def test_lists_the_groups_the_user_belongs_to(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        assert ListMyGroups(uow).execute(user_id=BOB) == [
            GroupSummary(GROUP_ID, "Flat", EUR, GroupStatus.ACTIVE)
        ]

    def test_user_with_no_groups_gets_an_empty_list(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow)
        assert ListMyGroups(uow).execute(user_id=CAROL) == []
