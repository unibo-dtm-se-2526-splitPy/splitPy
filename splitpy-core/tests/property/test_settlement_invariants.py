"""Scenarios 6 and 7 of the test plan (I-07): the plan settles everything in at most N-1 transfers."""

from hypothesis import given
from hypothesis import strategies as st
from strategies import members
from support import EUR

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.money import Money
from splitpy_core.domain.settlement import SettlementService


@st.composite
def balances(draw):
    users = draw(members)
    nets = draw(
        st.lists(
            st.integers(min_value=-(10**7), max_value=10**7),
            min_size=len(users) - 1,
            max_size=len(users) - 1,
        )
    )
    nets.append(-sum(nets))
    return Balances({user: Money(net, EUR) for user, net in zip(users, nets, strict=True)})


@given(balances=balances())
def test_rf11_executing_the_plan_settles_every_balance(balances):
    net = dict(balances.by_member)
    for transfer in SettlementService.plan(balances).transfers:
        net[transfer.debtor] += transfer.amount
        net[transfer.creditor] -= transfer.amount
    assert Balances(net).is_settled()


@given(balances=balances())
def test_rf11_plan_has_at_most_n_minus_one_transfers(balances):
    unsettled = [net for net in balances.by_member.values() if not net.is_zero()]
    transfers = SettlementService.plan(balances).transfers
    assert len(transfers) <= max(len(unsettled) - 1, 0)
