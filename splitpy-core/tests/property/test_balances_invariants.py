"""Scenario 5 of the test plan: balances of a randomly generated group always sum to zero."""

from datetime import UTC, date, datetime
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import ExpenseId, PaymentId, UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import EqualSplit

EUR = Currency("EUR")
ON = date(2026, 3, 14)

cents = st.integers(min_value=1, max_value=10**7)


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
            occurred_on=ON,
            deleted_at=datetime(2026, 3, 15, tzinfo=UTC) if draw(st.booleans()) else None,
        )
        for i in range(draw(st.integers(0, 15)))
    ]
    payments = []
    for i in range(draw(st.integers(0, 10))):
        debtor, creditor = draw(
            st.lists(st.sampled_from(members), min_size=2, max_size=2, unique=True)
        )
        payments.append(
            Payment(PaymentId(UUID(int=i)), debtor, creditor, Money(draw(cents), EUR), ON)
        )
    return members, expenses, payments


@given(group=groups())
def test_rf10_balances_always_sum_to_zero(group):
    members, expenses, payments = group
    balances = Balances.compute(EUR, members, expenses, payments)
    assert sum(balances.by_member.values(), Money.zero(EUR)).is_zero()
