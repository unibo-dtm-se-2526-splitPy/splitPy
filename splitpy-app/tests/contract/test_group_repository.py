"""Contract every GroupRepository implementation must pass, in memory and on a database alike."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_app.adapters.persistence.in_memory import InMemoryGroupRepository
from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.errors import GroupNotFound
from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit
from splitpy_core.ports.group_repository import ConcurrencyConflict, GroupSummary

EUR = Currency("EUR")
ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
GROUP_ID = GroupId(UUID(int=10))
OTHER_GROUP_ID = GroupId(UUID(int=11))
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
JANUARY = DateRange(date(2026, 1, 1), date(2026, 1, 31))


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def register(group: Group, n: int, amount: str, occurred_on: date) -> None:
    group.register_expense(
        ExpenseId(UUID(int=100 + n)),
        "Dinner",
        eur(amount),
        ALICE,
        EqualSplit(frozenset({ALICE, BOB})),
        Category.FOOD,
        occurred_on,
        by=ALICE,
    )


def new_group(id: GroupId = GROUP_ID, name: str = "Flat") -> Group:
    """Alice (ADMIN) and Bob, with no expenses."""
    group = Group.create(id, name, EUR, founder=ALICE, at=T0)
    group.add_member(BOB, Role.MEMBER, by=ALICE, at=T0)
    return group


@pytest.fixture(params=[InMemoryGroupRepository], ids=["in_memory"])
def repository(request):
    return request.param()


class TestGet:
    def test_unknown_group_is_not_found(self, repository):
        with pytest.raises(GroupNotFound):
            repository.get(GROUP_ID)

    def test_saved_group_is_loaded_with_everything_it_recorded(self, repository):
        group = new_group()
        group.add_member(CAROL, Role.MEMBER, by=ALICE, at=T0)
        register(group, 1, "30.00", date(2026, 1, 5))
        register(group, 2, "10.00", date(2026, 1, 6))
        group.remove_expense(ExpenseId(UUID(int=102)), by=ALICE, at=T1)
        group.record_payment(PaymentId(UUID(int=200)), BOB, ALICE, eur("5.00"), T1.date(), by=BOB)
        group.remove_member(CAROL, by=ALICE, at=T1)
        repository.save(group)

        loaded = repository.get(GROUP_ID)

        assert (loaded.id, loaded.name, loaded.currency, loaded.status) == (
            GROUP_ID,
            "Flat",
            EUR,
            GroupStatus.ACTIVE,
        )
        assert list(loaded.members()) == list(group.members())
        assert list(loaded.expenses()) == list(group.expenses())
        assert list(loaded.payments()) == list(group.payments())
        assert loaded.balances() == group.balances()

    def test_loaded_group_has_no_pending_events(self, repository):
        repository.save(new_group())
        assert repository.get(GROUP_ID).pull_events() == []

    def test_changes_are_not_stored_until_saved(self, repository):
        repository.save(new_group())
        loaded = repository.get(GROUP_ID)
        register(loaded, 1, "30.00", date(2026, 1, 5))
        assert list(repository.get(GROUP_ID).expenses()) == []


class TestSave:
    def test_new_group_is_stored_at_version_one(self, repository):
        repository.save(new_group())
        assert repository.get(GROUP_ID).version == 1

    def test_each_save_bumps_the_version(self, repository):
        repository.save(new_group())
        loaded = repository.get(GROUP_ID)
        loaded.archive(by=ALICE)
        repository.save(loaded)
        assert repository.get(GROUP_ID).version == 2

    def test_save_of_a_stale_group_is_a_conflict(self, repository):
        repository.save(new_group())
        first = repository.get(GROUP_ID)
        second = repository.get(GROUP_ID)
        register(first, 1, "30.00", date(2026, 1, 5))
        repository.save(first)
        register(second, 2, "10.00", date(2026, 1, 6))
        with pytest.raises(ConcurrencyConflict):
            repository.save(second)

    def test_a_conflict_leaves_the_stored_group_untouched(self, repository):
        repository.save(new_group())
        stale = repository.get(GROUP_ID)
        repository.save(repository.get(GROUP_ID))
        stale.archive(by=ALICE)
        with pytest.raises(ConcurrencyConflict):
            repository.save(stale)
        stored = repository.get(GROUP_ID)
        assert (stored.status, stored.version) == (GroupStatus.ACTIVE, 2)

    def test_new_group_with_a_taken_id_is_a_conflict(self, repository):
        repository.save(new_group())
        with pytest.raises(ConcurrencyConflict):
            repository.save(new_group(name="Trip"))


class TestGetForPeriod:
    def test_rf13_only_expenses_in_the_period_are_loaded(self, repository):
        group = new_group()
        register(group, 1, "30.00", date(2025, 12, 31))
        register(group, 2, "10.00", date(2026, 1, 1))
        register(group, 3, "20.00", date(2026, 1, 31))
        register(group, 4, "40.00", date(2026, 2, 1))
        repository.save(group)

        loaded = repository.get_for_period(GROUP_ID, JANUARY)

        assert [expense.id for expense in loaded.expenses()] == [
            ExpenseId(UUID(int=102)),
            ExpenseId(UUID(int=103)),
        ]

    def test_unknown_group_is_not_found(self, repository):
        with pytest.raises(GroupNotFound):
            repository.get_for_period(GROUP_ID, JANUARY)


class TestListSummariesForUser:
    def test_lists_the_groups_the_user_is_an_active_member_of(self, repository):
        repository.save(new_group(GROUP_ID, "Flat"))
        repository.save(new_group(OTHER_GROUP_ID, "Trip"))
        assert set(repository.list_summaries_for_user(BOB)) == {
            GroupSummary(GROUP_ID, "Flat", EUR, GroupStatus.ACTIVE),
            GroupSummary(OTHER_GROUP_ID, "Trip", EUR, GroupStatus.ACTIVE),
        }

    def test_groups_the_user_left_are_not_listed(self, repository):
        group = new_group()
        group.remove_member(BOB, by=ALICE, at=T1)
        repository.save(group)
        assert repository.list_summaries_for_user(BOB) == []

    def test_user_with_no_groups_gets_an_empty_list(self, repository):
        repository.save(new_group())
        assert repository.list_summaries_for_user(CAROL) == []
