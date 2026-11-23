"""Read-only use cases: the settlement plan and the spending report of a stored group."""

from datetime import date
from uuid import UUID

import pytest
from support import ALICE, BOB, CAROL, DAY, GROUP_ID, NOW, T0, eur, load, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.application.ports import RecordedEvent
from splitpy_app.application.use_cases.insights import (
    ComputeBalances,
    ComputeSettlement,
    GenerateReport,
    ListActivity,
)
from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.errors import GroupNotFound
from splitpy_core.domain.events import GroupArchived, MemberAdded
from splitpy_core.domain.ids import ExpenseId, GroupId
from splitpy_core.domain.member import Role
from splitpy_core.domain.settlement import Transfer
from splitpy_core.domain.split import EqualSplit

JANUARY = DateRange(date(2026, 1, 1), date(2026, 1, 31))


def store_dinners(uow: InMemoryUnitOfWork, *dinners: tuple[str, date]) -> None:
    """Dinners paid by Alice and split equally among Alice, Bob and Carol."""
    group = load(uow)
    for n, (amount, occurred_on) in enumerate(dinners):
        group.register_expense(
            ExpenseId(UUID(int=100 + n)),
            "Dinner",
            eur(amount),
            ALICE,
            EqualSplit(frozenset({ALICE, BOB, CAROL})),
            Category.FOOD,
            occurred_on,
            by=ALICE,
        )
    with uow:
        uow.groups.save(group)
        uow.commit()


class TestComputeSettlement:
    def test_rf11_plan_settles_the_stored_balances(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        store_dinners(uow, ("30.00", DAY))
        plan = ComputeSettlement(uow).execute(group_id=GROUP_ID)
        assert set(plan.transfers) == {
            Transfer(BOB, ALICE, eur("10.00")),
            Transfer(CAROL, ALICE, eur("10.00")),
        }

    def test_rf11_computing_the_plan_stores_nothing(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        store_dinners(uow, ("30.00", DAY))
        ComputeSettlement(uow).execute(group_id=GROUP_ID)
        assert load(uow).version == 2

    def test_unknown_group_is_not_found(self):
        with pytest.raises(GroupNotFound):
            ComputeSettlement(InMemoryUnitOfWork()).execute(group_id=GROUP_ID)


class TestGenerateReport:
    def test_rf13_report_covers_only_the_period(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        store_dinners(uow, ("30.00", DAY), ("60.00", date(2026, 2, 10)))
        report = GenerateReport(uow).execute(group_id=GROUP_ID, period=JANUARY)
        assert (report.period, report.total) == (JANUARY, eur("30.00"))
        assert report.by_category == {Category.FOOD: eur("30.00")}

    def test_unknown_group_is_not_found(self):
        with pytest.raises(GroupNotFound):
            GenerateReport(InMemoryUnitOfWork()).execute(group_id=GROUP_ID, period=JANUARY)


class TestComputeBalances:
    def test_rf10_balances_come_from_the_stored_expenses(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        store_dinners(uow, ("30.00", DAY))

        balances = ComputeBalances(uow).execute(group_id=GROUP_ID)

        assert balances.by_member == {
            ALICE: eur("20.00"),
            BOB: eur("-10.00"),
            CAROL: eur("-10.00"),
        }

    def test_rf10_unknown_group_raises_group_not_found(self):
        with pytest.raises(GroupNotFound):
            ComputeBalances(InMemoryUnitOfWork()).execute(group_id=GROUP_ID)


class TestListActivity:
    def test_rf15_events_of_the_group_are_listed_newest_first(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow)
        added = MemberAdded(group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE)
        archived = GroupArchived(group_id=GROUP_ID, by=ALICE)
        other = GroupArchived(group_id=GroupId(UUID(int=11)), by=ALICE)
        with uow:
            uow.events.append([added], at=T0)
            uow.events.append([archived, other], at=NOW)
            uow.commit()

        assert ListActivity(uow).execute(group_id=GROUP_ID) == [
            RecordedEvent(archived, NOW),
            RecordedEvent(added, T0),
        ]

    def test_rf15_unknown_group_raises_group_not_found(self):
        with pytest.raises(GroupNotFound):
            ListActivity(InMemoryUnitOfWork()).execute(group_id=GROUP_ID)
