"""Scenario 10 of the test plan: total by category = total by member = grand total."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import ExpenseId, GroupId, UserId
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.report import ReportService
from splitpy_core.domain.split import EqualSplit

EUR = Currency("EUR")
JOINED = datetime(2026, 1, 1, tzinfo=UTC)
FIRST_DAY = date(2026, 3, 1)

cents = st.integers(min_value=1, max_value=10**7)
days = st.integers(min_value=0, max_value=60).map(lambda n: FIRST_DAY + timedelta(days=n))


@st.composite
def groups(draw):
    members = sorted(
        draw(
            st.sets(
                st.integers(0, 1_000).map(lambda n: UserId(UUID(int=n))), min_size=2, max_size=8
            )
        )
    )
    expenses = [
        Expense(
            id=ExpenseId(UUID(int=i)),
            description="generated",
            amount=Money(draw(cents), EUR),
            paid_by=draw(st.sampled_from(members)),
            split=EqualSplit(
                frozenset(draw(st.lists(st.sampled_from(members), min_size=1, unique=True)))
            ),
            category=draw(st.sampled_from(Category)),
            occurred_on=draw(days),
            deleted_at=datetime(2026, 6, 1, tzinfo=UTC) if draw(st.booleans()) else None,
        )
        for i in range(draw(st.integers(0, 15)))
    ]
    return Group(
        GroupId(UUID(int=1)),
        "generated",
        EUR,
        [Member(user_id, Role.MEMBER, joined_at=JOINED) for user_id in members],
        expenses,
    )


@st.composite
def periods(draw):
    start, end = sorted([draw(days), draw(days)])
    return DateRange(start, end)


def total(amounts) -> Money:
    return sum(amounts, Money.zero(EUR))


@given(group=groups(), period=periods())
def test_rf13_category_and_member_totals_match_the_grand_total(group, period):
    spending = ReportService.spending(group, period)
    assert total(spending.by_category.values()) == spending.total
    assert total(spending.by_member.values()) == spending.total


@given(group=groups(), period=periods())
def test_rf13_grand_total_is_the_sum_of_active_expenses_in_the_period(group, period):
    spending = ReportService.spending(group, period)
    expected = total(
        expense.amount
        for expense in group.active_expenses()
        if period.contains(expense.occurred_on)
    )
    assert spending.total == expected
