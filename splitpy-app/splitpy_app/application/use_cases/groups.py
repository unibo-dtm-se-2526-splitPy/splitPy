"""Use cases that create a group, manage its members and archive it (RF-04, RF-05, RF-16)."""

from splitpy_app.application.ports import UnitOfWork
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.domain.member import Role
from splitpy_core.domain.money import Currency
from splitpy_core.ports.clock import Clock
from splitpy_core.ports.group_repository import GroupSummary
from splitpy_core.ports.id_generator import IdGenerator


class CreateGroup:
    def __init__(self, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    def execute(self, *, name: str, currency: Currency, founder: UserId) -> Group:
        at = self._clock.now()
        group = Group.create(GroupId(self._ids.new_id()), name, currency, founder=founder, at=at)
        with self._uow:
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()
        return group


class AddMember:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, *, group_id: GroupId, user_id: UserId, role: Role, by: UserId) -> None:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            group.add_member(user_id, role, by=by, at=at)
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()


class RemoveMember:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(
        self, *, group_id: GroupId, user_id: UserId, by: UserId, successor: UserId | None = None
    ) -> None:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            group.remove_member(user_id, by=by, at=at, successor=successor)
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()


class ArchiveGroup:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, *, group_id: GroupId, by: UserId) -> None:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            group.archive(by=by)
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()


class ListMyGroups:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, user_id: UserId) -> list[GroupSummary]:
        with self._uow:
            return self._uow.groups.list_summaries_for_user(user_id)
