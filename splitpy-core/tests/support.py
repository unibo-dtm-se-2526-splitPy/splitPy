"""Constants and builders shared by the tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import EqualSplit, SplitStrategy

EUR = Currency("EUR")
USD = Currency("USD")

# UUIDs by kind: users 1-4, group 10, expenses from 100, payments from 200.
ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
DAVE = UserId(UUID(int=4))
MEMBERS = [ALICE, BOB, CAROL]

GROUP_ID = GroupId(UUID(int=10))
EXPENSE_ID = ExpenseId(UUID(int=100))
PAYMENT_ID = PaymentId(UUID(int=200))

# Instants in the order they happen, and the day expenses and payments occur on.
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
T2 = datetime(2026, 1, 3, tzinfo=UTC)
DAY = date(2026, 1, 2)


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def usd(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), USD)


def expense_id(n: int) -> ExpenseId:
    return ExpenseId(UUID(int=100 + n))


def payment_id(n: int) -> PaymentId:
    return PaymentId(UUID(int=200 + n))


def expense(
    amount: str = "30.00",
    *,
    id: ExpenseId = EXPENSE_ID,
    paid_by: UserId = ALICE,
    split: SplitStrategy | None = None,
    category: Category = Category.FOOD,
    occurred_on: date = DAY,
    deleted_at: datetime | None = None,
) -> Expense:
    """A dinner paid by Alice and split equally among Alice, Bob and Carol, unless overridden."""
    return Expense(
        id=id,
        description="Dinner",
        amount=eur(amount),
        paid_by=paid_by,
        split=split or EqualSplit(frozenset(MEMBERS)),
        category=category,
        occurred_on=occurred_on,
        deleted_at=deleted_at,
    )


def payment(debtor: UserId, creditor: UserId, amount: str, *, n: int = 0) -> Payment:
    return Payment(payment_id(n), debtor, creditor, eur(amount), DAY)


def register_dinner(
    group: Group,
    amount: str = "30.00",
    *,
    paid_by: UserId = ALICE,
    split: SplitStrategy | None = None,
) -> Expense:
    """Registers a dinner split equally among all the active members, unless overridden."""
    participants = frozenset(member.user_id for member in group.active_members())
    return group.register_expense(
        EXPENSE_ID,
        "Dinner",
        eur(amount),
        paid_by,
        split or EqualSplit(participants),
        Category.FOOD,
        DAY,
        by=paid_by,
    )
