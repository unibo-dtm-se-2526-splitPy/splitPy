from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.errors import NonPositiveAmount
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.settlement import SettlementPlan, SettlementService, Transfer

EUR = Currency("EUR")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
DAVE = UserId(UUID(int=4))


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def plan(**nets: str) -> SettlementPlan:
    members = {"alice": ALICE, "bob": BOB, "carol": CAROL, "dave": DAVE}
    return SettlementService.plan(Balances({members[name]: eur(net) for name, net in nets.items()}))


class TestTransfer:
    @pytest.mark.parametrize("amount", ["0", "-5.00"])
    def test_amount_must_be_positive(self, amount):
        with pytest.raises(NonPositiveAmount):
            Transfer(debtor=BOB, creditor=ALICE, amount=eur(amount))


class TestSettlementService:
    def test_rf11_settled_balances_produce_an_empty_plan(self):
        assert plan(alice="0", bob="0", carol="0").transfers == ()

    def test_rf11_single_debtor_pays_single_creditor(self):
        assert plan(alice="12.50", bob="-12.50", carol="0").transfers == (
            Transfer(debtor=BOB, creditor=ALICE, amount=eur("12.50")),
        )

    def test_rf11_largest_debtor_pays_first(self):
        assert plan(alice="30.00", bob="-20.00", carol="-10.00").transfers == (
            Transfer(debtor=BOB, creditor=ALICE, amount=eur("20.00")),
            Transfer(debtor=CAROL, creditor=ALICE, amount=eur("10.00")),
        )

    def test_rf11_debtor_is_split_across_creditors_when_the_largest_is_paid_off(self):
        assert plan(alice="50.00", bob="10.00", carol="-40.00", dave="-20.00").transfers == (
            Transfer(debtor=CAROL, creditor=ALICE, amount=eur("40.00")),
            Transfer(debtor=DAVE, creditor=ALICE, amount=eur("10.00")),
            Transfer(debtor=DAVE, creditor=BOB, amount=eur("10.00")),
        )

    def test_rf11_equal_amounts_are_ordered_by_user_id(self):
        assert plan(bob="10.00", alice="10.00", carol="-20.00").transfers == (
            Transfer(debtor=CAROL, creditor=ALICE, amount=eur("10.00")),
            Transfer(debtor=CAROL, creditor=BOB, amount=eur("10.00")),
        )
