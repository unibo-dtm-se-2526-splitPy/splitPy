from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import ExpenseId, PaymentId, UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import EqualSplit

EUR = Currency("EUR")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
MEMBERS = [ALICE, BOB, CAROL]

ON = date(2026, 3, 14)


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def expense(amount: str, paid_by: UserId, deleted: bool = False) -> Expense:
    return Expense(
        id=ExpenseId(UUID(int=100)),
        description="Dinner",
        amount=eur(amount),
        paid_by=paid_by,
        split=EqualSplit(frozenset(MEMBERS)),
        category=Category.FOOD,
        occurred_on=ON,
        deleted_at=datetime(2026, 3, 15, tzinfo=UTC) if deleted else None,
    )


def payment(debtor: UserId, creditor: UserId, amount: str) -> Payment:
    return Payment(PaymentId(UUID(int=200)), debtor, creditor, eur(amount), ON)


def compute(expenses=(), payments=()) -> Balances:
    return Balances.compute(EUR, MEMBERS, expenses, payments)


class TestBalancesCompute:
    def test_without_movements_every_member_is_at_zero(self):
        assert compute().by_member == {ALICE: eur("0"), BOB: eur("0"), CAROL: eur("0")}

    def test_rf10_payer_is_credited_and_participants_are_debited(self):
        balances = compute(expenses=[expense("30.00", paid_by=ALICE)])
        assert balances.by_member == {ALICE: eur("20.00"), BOB: eur("-10.00"), CAROL: eur("-10.00")}

    def test_rf10_deleted_expenses_are_ignored(self):
        balances = compute(expenses=[expense("30.00", paid_by=ALICE, deleted=True)])
        assert balances.is_settled()

    def test_rf10_payment_moves_debt_from_debtor_to_creditor(self):
        balances = compute(
            expenses=[expense("30.00", paid_by=ALICE)],
            payments=[payment(BOB, ALICE, "10.00")],
        )
        assert balances.by_member == {ALICE: eur("10.00"), BOB: eur("0"), CAROL: eur("-10.00")}


class TestBalancesQueries:
    def test_debtors_are_members_with_negative_balance(self):
        assert compute(expenses=[expense("30.00", paid_by=ALICE)]).debtors() == [BOB, CAROL]

    def test_creditors_are_members_with_positive_balance(self):
        assert compute(expenses=[expense("30.00", paid_by=ALICE)]).creditors() == [ALICE]

    def test_is_settled_when_every_balance_is_zero(self):
        balances = compute(
            expenses=[expense("30.00", paid_by=ALICE)],
            payments=[payment(BOB, ALICE, "10.00"), payment(CAROL, ALICE, "10.00")],
        )
        assert balances.is_settled()

    def test_is_not_settled_while_someone_owes(self):
        assert not compute(expenses=[expense("30.00", paid_by=ALICE)]).is_settled()
