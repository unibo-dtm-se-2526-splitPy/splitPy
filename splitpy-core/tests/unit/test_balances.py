"""Net balances: what each member paid minus what they owe, adjusted by reimbursements."""

from collections.abc import Iterable

import pytest
from support import ALICE, BOB, CAROL, EUR, MEMBERS, T2, eur, expense, payment

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.payment import Payment


def compute(expenses: Iterable[Expense] = (), payments: Iterable[Payment] = ()) -> Balances:
    return Balances.compute(EUR, MEMBERS, expenses, payments)


class TestBalancesCompute:
    def test_without_movements_every_member_is_at_zero(self):
        assert compute().by_member == {ALICE: eur("0.00"), BOB: eur("0.00"), CAROL: eur("0.00")}

    def test_rf10_payer_is_credited_and_participants_are_debited(self):
        balances = compute(expenses=[expense("30.00")])
        assert balances.by_member == {ALICE: eur("20.00"), BOB: eur("-10.00"), CAROL: eur("-10.00")}

    def test_rf10_deleted_expenses_are_ignored(self):
        balances = compute(expenses=[expense("30.00", deleted_at=T2)])
        assert balances.is_settled()

    def test_rf10_payment_moves_debt_from_debtor_to_creditor(self):
        balances = compute(expenses=[expense("30.00")], payments=[payment(BOB, ALICE, "10.00")])
        assert balances.by_member == {
            ALICE: eur("10.00"),
            BOB: eur("0.00"),
            CAROL: eur("-10.00"),
        }


class TestBalancesQueries:
    def test_debtors_are_members_with_negative_balance(self):
        assert compute(expenses=[expense("30.00")]).debtors() == [BOB, CAROL]

    def test_creditors_are_members_with_positive_balance(self):
        assert compute(expenses=[expense("30.00")]).creditors() == [ALICE]

    def test_is_settled_when_every_balance_is_zero(self):
        balances = compute(
            expenses=[expense("30.00")],
            payments=[payment(BOB, ALICE, "10.00"), payment(CAROL, ALICE, "10.00", n=1)],
        )
        assert balances.is_settled()

    def test_is_not_settled_while_someone_owes(self):
        assert not compute(expenses=[expense("30.00")]).is_settled()

    def test_i02_changing_the_source_dict_does_not_change_the_balances(self):
        source = {ALICE: eur("10.00"), BOB: eur("-10.00")}
        balances = Balances(source)
        source[BOB] = eur("0.00")
        assert balances.debtors() == [BOB]

    def test_i02_balances_cannot_be_changed_in_place(self):
        balances = compute(expenses=[expense("30.00")])
        with pytest.raises(TypeError):
            balances.by_member[ALICE] = eur("0.00")
