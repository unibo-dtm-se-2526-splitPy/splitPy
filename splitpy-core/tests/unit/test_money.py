"""Money as integer cents: exact arithmetic in one currency and allocation without losing cents."""

from decimal import Decimal

import pytest
from support import EUR, eur, usd

from splitpy_core.domain.errors import CurrencyMismatch, SubCentAmount, UnsupportedCurrency
from splitpy_core.domain.money import Currency, Money


class TestCurrency:
    @pytest.mark.parametrize("code", ["EUR", "USD", "GBP"])
    def test_supported_codes_are_accepted(self, code):
        assert Currency(code).code == code

    @pytest.mark.parametrize("code", ["XYZ", "eur", ""])
    def test_unsupported_code_raises_unsupported_currency(self, code):
        with pytest.raises(UnsupportedCurrency):
            Currency(code)


class TestFromDecimal:
    def test_from_decimal_converts_to_cents(self):
        assert Money.from_decimal(Decimal("12.34"), EUR).cents == 1234

    def test_from_decimal_accepts_trailing_zeros_beyond_cents(self):
        assert Money.from_decimal(Decimal("1.500"), EUR).cents == 150

    @pytest.mark.parametrize("amount", ["1.999", "0.001", "-2.005"])
    def test_from_decimal_rejects_fractions_of_a_cent(self, amount):
        with pytest.raises(SubCentAmount):
            Money.from_decimal(Decimal(amount), EUR)


class TestMoneyArithmetic:
    def test_zero_has_zero_cents(self):
        assert Money.zero(EUR).cents == 0

    def test_add_sums_cents_in_same_currency(self):
        assert eur("1.50") + eur("2.25") == eur("3.75")

    def test_subtract_same_currency(self):
        assert eur("5.00") - eur("1.50") == eur("3.50")

    def test_negate_flips_sign(self):
        assert (-eur("4.20")).cents == -420

    def test_add_different_currency_raises_currency_mismatch(self):
        with pytest.raises(CurrencyMismatch):
            eur("1.00") + usd("1.00")

    def test_subtract_different_currency_raises_currency_mismatch(self):
        with pytest.raises(CurrencyMismatch):
            eur("1.00") - usd("1.00")


class TestMoneySign:
    @pytest.mark.parametrize(
        ("amount", "expected"),
        [
            ("0.00", (True, False, False)),
            ("0.01", (False, True, False)),
            ("-0.01", (False, False, True)),
        ],
    )
    def test_zero_positive_and_negative_are_exclusive(self, amount, expected):
        money = eur(amount)
        assert (money.is_zero(), money.is_positive(), money.is_negative()) == expected


class TestMoneyAllocate:
    def test_rf07_ten_euros_among_three_gives_334_333_333(self):
        # Scenario 1 of the test plan.
        shares = eur("10.00").allocate([1, 1, 1])
        assert [share.cents for share in shares] == [334, 333, 333]

    def test_rf07_one_cent_among_three_gives_1_0_0(self):
        # Scenario 2 of the test plan.
        shares = eur("0.01").allocate([1, 1, 1])
        assert [share.cents for share in shares] == [1, 0, 0]

    def test_rf07_allocate_never_loses_cents(self):
        money = eur("10.00")
        assert sum(money.allocate([1, 1, 1]), Money.zero(EUR)) == money

    def test_rf07_allocate_preserves_currency_of_each_share(self):
        shares = eur("10.00").allocate([1, 1, 1])
        assert all(share.currency == EUR for share in shares)
