"""Invariant I-01: whatever the amount and the participants, the shares sum to the amount."""

from hypothesis import given
from hypothesis import strategies as st
from strategies import user_ids
from support import EUR

from splitpy_core.domain.money import Money
from splitpy_core.domain.split import EqualSplit, PercentageSplit

amounts = st.integers(min_value=1, max_value=10**9).map(lambda cents: Money(cents, EUR))
participants = st.frozensets(user_ids, min_size=1, max_size=20)


@st.composite
def basis_points(draw):
    users = sorted(draw(participants))
    cuts = sorted(
        draw(
            st.lists(
                st.integers(min_value=0, max_value=10_000),
                min_size=len(users) - 1,
                max_size=len(users) - 1,
            )
        )
    )
    bounds = [0, *cuts, 10_000]
    return {user: bounds[i + 1] - bounds[i] for i, user in enumerate(users)}


@given(amount=amounts, users=participants)
def test_i01_equal_split_shares_sum_to_amount(amount, users):
    assert EqualSplit(users).shares(amount).total() == amount


@given(amount=amounts, points=basis_points())
def test_i01_percentage_split_shares_sum_to_amount(amount, points):
    assert PercentageSplit(points).shares(amount).total() == amount
