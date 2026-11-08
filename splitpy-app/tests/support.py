"""Constants, test doubles and builders shared by the tests of the use cases."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import GroupId, UserId
from splitpy_core.domain.member import Role
from splitpy_core.domain.money import Currency, Money

EUR = Currency("EUR")

# UUIDs by kind: users 1-4, the stored group 10, generated ids from 1000.
ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
DAVE = UserId(UUID(int=4))
GROUP_ID = GroupId(UUID(int=10))
FIRST_ID = UUID(int=1000)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
DAY = date(2026, 1, 15)


class FixedClock:
    def today(self) -> date:
        return NOW.date()

    def now(self) -> datetime:
        return NOW


class SequentialIds:
    """Hands out FIRST_ID, then the next UUID, and so on."""

    def __init__(self) -> None:
        self._next = FIRST_ID.int

    def new_id(self) -> UUID:
        id = UUID(int=self._next)
        self._next += 1
        return id


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def stored_group(uow: InMemoryUnitOfWork, *members: UserId) -> Group:
    """Stores a group founded by Alice at T0, with the given members, and returns it."""
    group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
    for member in members:
        group.add_member(member, Role.MEMBER, by=ALICE, at=T0)
    group.pull_events()
    with uow:
        uow.groups.save(group)
        uow.commit()
    return group


def load(uow: InMemoryUnitOfWork, group_id: GroupId = GROUP_ID) -> Group:
    with uow:
        return uow.groups.get(group_id)
