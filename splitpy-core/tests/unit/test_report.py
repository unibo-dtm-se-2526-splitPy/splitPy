"""Spending report: what each member consumed in a period, by category and by member."""

from collections.abc import Iterable
from datetime import date, datetime

import pytest
from support import (
    ALICE,
    BOB,
    CAROL,
    EUR,
    GROUP_ID,
    MEMBERS,
    T0,
    T2,
    eur,
    expense,
    expense_id,
    payment,
)

from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.group import Group
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.report import ReportService, SpendingReport
from splitpy_core.domain.split import ExactSplit, SplitStrategy

MARCH = DateRange(date(2026, 3, 1), date(2026, 3, 31))
MID_MARCH = date(2026, 3, 14)


def report(
    expenses: Iterable[Expense] = (), payments: Iterable[Payment] = (), period: DateRange = MARCH
) -> SpendingReport:
    members = [Member(user_id, Role.MEMBER, joined_at=T0) for user_id in MEMBERS]
    group = Group(GROUP_ID, "Flat", EUR, members, expenses, payments)
    return ReportService.spending(group, period)


def march_expense(
    n: int,
    amount: str,
    *,
    occurred_on: date = MID_MARCH,
    category: Category = Category.FOOD,
    split: SplitStrategy | None = None,
    deleted_at: datetime | None = None,
) -> Expense:
    return expense(
        amount,
        id=expense_id(n),
        occurred_on=occurred_on,
        category=category,
        split=split,
        deleted_at=deleted_at,
    )


class TestReportService:
    def test_rf13_without_expenses_the_report_is_empty(self):
        spending = report()
        assert spending.period == MARCH
        assert spending.total == eur("0.00")
        assert spending.by_category == {}
        assert spending.by_member == {}

    def test_rf13_totals_by_category(self):
        spending = report(
            [
                march_expense(1, "30.00", category=Category.FOOD),
                march_expense(2, "15.00", category=Category.FOOD),
                march_expense(3, "60.00", category=Category.HOUSING),
            ]
        )
        assert spending.total == eur("105.00")
        assert spending.by_category == {
            Category.FOOD: eur("45.00"),
            Category.HOUSING: eur("60.00"),
        }

    def test_rf13_by_member_is_what_each_one_consumed_not_what_they_paid(self):
        split = ExactSplit({ALICE: eur("10.00"), BOB: eur("30.00")})
        spending = report([march_expense(1, "40.00", split=split)])
        assert spending.by_member == {ALICE: eur("10.00"), BOB: eur("30.00")}

    def test_rf13_period_extremes_are_included(self):
        spending = report(
            [
                march_expense(1, "1.00", occurred_on=date(2026, 2, 28)),
                march_expense(2, "3.00", occurred_on=date(2026, 3, 1)),
                march_expense(3, "6.00", occurred_on=date(2026, 3, 31)),
                march_expense(4, "9.00", occurred_on=date(2026, 4, 1)),
            ]
        )
        assert spending.total == eur("9.00")

    def test_rf09_removed_expenses_are_excluded(self):
        spending = report([march_expense(1, "30.00"), march_expense(2, "99.00", deleted_at=T2)])
        assert spending.total == eur("30.00")

    def test_rf13_payments_are_excluded_because_they_are_not_consumption(self):
        spending = report([march_expense(1, "30.00")], [payment(BOB, ALICE, "10.00")])
        assert spending.total == eur("30.00")
        assert spending.by_member == {ALICE: eur("10.00"), BOB: eur("10.00"), CAROL: eur("10.00")}

    @pytest.mark.parametrize("breakdown", ["by_category", "by_member"])
    def test_rf13_breakdowns_cannot_be_changed_in_place(self, breakdown):
        spending = report([march_expense(1, "30.00")])
        with pytest.raises(TypeError):
            getattr(spending, breakdown)[ALICE] = eur("0.00")
