"""Scenario 5 of the test plan: balances of a randomly generated group always sum to zero."""

from hypothesis import given
from hypothesis import strategies as st
from strategies import cents, members
from support import DAY, EUR, T2, expense_id, payment_id

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.money import Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import EqualSplit


@st.composite
def groups(draw):
    users = draw(members)
    expenses = [
        Expense(
            id=expense_id(i),
            description="generated",
            amount=Money(draw(cents), EUR),
            paid_by=draw(st.sampled_from(users)),
            split=EqualSplit(
                frozenset(draw(st.lists(st.sampled_from(users), min_size=1, unique=True)))
            ),
            category=draw(st.sampled_from(Category)),
            occurred_on=DAY,
            deleted_at=T2 if draw(st.booleans()) else None,
        )
        for i in range(draw(st.integers(min_value=0, max_value=15)))
    ]
    payments = []
    for i in range(draw(st.integers(min_value=0, max_value=10))):
        debtor, creditor = draw(
            st.lists(st.sampled_from(users), min_size=2, max_size=2, unique=True)
        )
        payments.append(Payment(payment_id(i), debtor, creditor, Money(draw(cents), EUR), DAY))
    return users, expenses, payments


@given(group=groups())
def test_rf10_balances_always_sum_to_zero(group):
    users, expenses, payments = group
    balances = Balances.compute(EUR, users, expenses, payments)
    assert sum(balances.by_member.values(), Money.zero(EUR)).is_zero()
