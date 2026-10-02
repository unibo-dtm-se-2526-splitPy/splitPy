from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import NonPositiveAmount, SplitDoesNotMatchAmount
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import ExpenseId, UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit, ExactSplit

EUR = Currency("EUR")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))

EXPENSE_ID = ExpenseId(UUID(int=100))
OCCURRED_ON = date(2026, 3, 14)
DELETED_AT = datetime(2026, 3, 15, tzinfo=UTC)


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def expense(amount: Money, split=None, deleted_at=None) -> Expense:
    return Expense(
        id=EXPENSE_ID,
        description="Dinner",
        amount=amount,
        paid_by=ALICE,
        split=split or EqualSplit(frozenset({ALICE, BOB, CAROL})),
        category=Category.FOOD,
        occurred_on=OCCURRED_ON,
        deleted_at=deleted_at,
    )


class TestExpense:
    def test_rf06_shares_apply_the_split_to_the_amount(self):
        shares = expense(eur("10.00")).shares()
        assert shares.by_member == {ALICE: eur("3.34"), BOB: eur("3.33"), CAROL: eur("3.33")}

    def test_i01_shares_sum_to_the_amount(self):
        assert expense(eur("10.00")).shares().total() == eur("10.00")

    def test_i01_split_that_does_not_match_the_amount_is_rejected(self):
        split = ExactSplit({ALICE: eur("4.00"), BOB: eur("5.00")})
        with pytest.raises(SplitDoesNotMatchAmount):
            expense(eur("10.00"), split=split)

    def test_i10_zero_amount_is_rejected(self):
        with pytest.raises(NonPositiveAmount):
            expense(eur("0.00"))

    def test_i10_negative_amount_is_rejected(self):
        with pytest.raises(NonPositiveAmount):
            expense(eur("-5.00"))


class TestExpenseSoftDelete:
    def test_rf09_expense_without_deleted_at_is_active(self):
        assert expense(eur("10.00")).is_active()

    def test_rf09_expense_with_deleted_at_is_not_active(self):
        assert not expense(eur("10.00"), deleted_at=DELETED_AT).is_active()

    def test_deleted_at_defaults_to_none(self):
        created = Expense(
            EXPENSE_ID,
            "Dinner",
            eur("10.00"),
            ALICE,
            EqualSplit(frozenset({ALICE})),
            Category.FOOD,
            OCCURRED_ON,
        )
        assert created.deleted_at is None

    def test_expense_is_immutable(self):
        with pytest.raises(AttributeError):
            expense(eur("10.00")).deleted_at = DELETED_AT
