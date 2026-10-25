"""An expense applies its split to its amount and is removed by a soft delete."""

from dataclasses import FrozenInstanceError

import pytest
from support import ALICE, BOB, CAROL, DAY, EXPENSE_ID, T2, eur, expense

from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import NonPositiveAmount, SplitDoesNotMatchAmount
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.split import EqualSplit, ExactSplit


class TestExpense:
    def test_rf06_shares_apply_the_split_to_the_amount(self):
        shares = expense("10.00").shares()
        assert shares.by_member == {ALICE: eur("3.34"), BOB: eur("3.33"), CAROL: eur("3.33")}

    def test_i01_shares_sum_to_the_amount(self):
        assert expense("10.00").shares().total() == eur("10.00")

    def test_i01_split_that_does_not_match_the_amount_is_rejected(self):
        split = ExactSplit({ALICE: eur("4.00"), BOB: eur("5.00")})
        with pytest.raises(SplitDoesNotMatchAmount):
            expense("10.00", split=split)

    def test_i10_zero_amount_is_rejected(self):
        with pytest.raises(NonPositiveAmount):
            expense("0.00")

    def test_i10_negative_amount_is_rejected(self):
        with pytest.raises(NonPositiveAmount):
            expense("-5.00")


class TestExpenseSoftDelete:
    def test_rf09_expense_without_deleted_at_is_active(self):
        assert expense().is_active()

    def test_rf09_expense_with_deleted_at_is_not_active(self):
        assert not expense(deleted_at=T2).is_active()

    def test_deleted_at_defaults_to_none(self):
        created = Expense(
            EXPENSE_ID,
            "Dinner",
            eur("10.00"),
            ALICE,
            EqualSplit(frozenset({ALICE})),
            Category.FOOD,
            DAY,
        )
        assert created.deleted_at is None

    def test_expense_is_immutable(self):
        with pytest.raises(FrozenInstanceError):
            expense().deleted_at = T2
