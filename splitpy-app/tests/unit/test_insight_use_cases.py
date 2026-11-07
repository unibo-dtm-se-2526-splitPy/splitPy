"""Read-only use cases: the settlement plan and the spending report of a stored group."""

from datetime import date
from uuid import UUID

import pytest
from support import ALICE, BOB, CAROL, DAY, GROUP_ID, eur, load, stored_group

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.application.use_cases.insights import ComputeSettlement, GenerateReport
from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.errors import GroupNotFound
from splitpy_core.domain.ids import ExpenseId
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
