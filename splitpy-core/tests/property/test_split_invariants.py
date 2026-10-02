from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit, PercentageSplit

EUR = Currency("EUR")

amounts = st.integers(min_value=1, max_value=10**9).map(lambda cents: Money(cents, EUR))
participants = st.frozensets(
    st.integers(min_value=0, max_value=1_000).map(lambda n: UserId(UUID(int=n))),
    min_size=1,
    max_size=20,
)


@st.composite
def basis_points(draw):
    members = sorted(draw(participants))
    cuts = sorted(
        draw(st.lists(st.integers(0, 10_000), min_size=len(members) - 1, max_size=len(members) - 1))
    )
    bounds = [0, *cuts, 10_000]
    return {member: bounds[i + 1] - bounds[i] for i, member in enumerate(members)}


@given(amount=amounts, members=participants)
def test_i01_equal_split_shares_sum_to_amount(amount, members):
    assert EqualSplit(members).shares(amount).total() == amount


@given(amount=amounts, points=basis_points())
def test_i01_percentage_split_shares_sum_to_amount(amount, points):
    assert PercentageSplit(points).shares(amount).total() == amount
