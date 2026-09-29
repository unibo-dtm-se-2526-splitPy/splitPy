from decimal import Decimal

import pytest

from splitpy_core.domain.errors import CurrencyMismatch
from splitpy_core.domain.money import Currency, Money

EUR = Currency("EUR")
USD = Currency("USD")


class TestMoneyArithmetic:
    def test_from_decimal_converts_to_cents(self):
        assert Money.from_decimal(Decimal("12.34"), EUR).cents == 1234

    def test_zero_has_zero_cents(self):
        assert Money.zero(EUR).cents == 0

    def test_zero_is_zero(self):
        assert Money.zero(EUR).is_zero()

    def test_nonzero_is_not_zero(self):
        assert not Money.from_decimal(Decimal("0.01"), EUR).is_zero()

    def test_add_sums_cents_in_same_currency(self):
        total = Money.from_decimal(Decimal("1.50"), EUR) + Money.from_decimal(Decimal("2.25"), EUR)
        assert total == Money.from_decimal(Decimal("3.75"), EUR)

    def test_subtract_same_currency(self):
        result = Money.from_decimal(Decimal("5.00"), EUR) - Money.from_decimal(Decimal("1.50"), EUR)
        assert result == Money.from_decimal(Decimal("3.50"), EUR)

    def test_negate_flips_sign(self):
        assert (-Money.from_decimal(Decimal("4.20"), EUR)).cents == -420

    def test_add_different_currency_raises_currency_mismatch(self):
        with pytest.raises(CurrencyMismatch):
            Money.from_decimal(Decimal("1.00"), EUR) + Money.from_decimal(Decimal("1.00"), USD)

    def test_subtract_different_currency_raises_currency_mismatch(self):
        with pytest.raises(CurrencyMismatch):
            Money.from_decimal(Decimal("1.00"), EUR) - Money.from_decimal(Decimal("1.00"), USD)


class TestMoneyAllocate:
    """Scenari 1-2 del piano di test (13 · Piano di test, Notion)."""

    def test_scenario1_ten_euros_among_three_gives_334_333_333(self):
        shares = Money.from_decimal(Decimal("10.00"), EUR).allocate([1, 1, 1])
        assert [share.cents for share in shares] == [334, 333, 333]

    def test_scenario2_one_cent_among_three_gives_1_0_0(self):
        shares = Money.from_decimal(Decimal("0.01"), EUR).allocate([1, 1, 1])
        assert [share.cents for share in shares] == [1, 0, 0]

    def test_allocate_never_loses_cents(self):
        money = Money.from_decimal(Decimal("10.00"), EUR)
        shares = money.allocate([1, 1, 1])
        assert sum(shares, Money.zero(EUR)) == money

    def test_allocate_preserves_currency_of_each_share(self):
        shares = Money.from_decimal(Decimal("10.00"), EUR).allocate([1, 1, 1])
        assert all(share.currency == EUR for share in shares)
