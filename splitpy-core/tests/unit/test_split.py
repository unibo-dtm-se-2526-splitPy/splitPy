from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_core.domain.errors import (
    CurrencyMismatch,
    EmptyParticipantSet,
    NegativeShare,
    PercentagesDoNotSumTo100,
    SplitDoesNotMatchAmount,
)
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit, ExactSplit, PercentageSplit, Shares

EUR = Currency("EUR")
USD = Currency("USD")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


class TestShares:
    def test_total_sums_every_share(self):
        shares = Shares({ALICE: eur("1.50"), BOB: eur("2.25")})
        assert shares.total() == eur("3.75")

    def test_empty_shares_raises_empty_participant_set(self):
        with pytest.raises(EmptyParticipantSet):
            Shares({})


class TestEqualSplit:
    def test_rf05_equal_split_divides_evenly(self):
        shares = EqualSplit(frozenset({ALICE, BOB})).shares(eur("10.00"))
        assert shares.by_member == {ALICE: eur("5.00"), BOB: eur("5.00")}

    def test_rf05_extra_cent_goes_to_lowest_user_id(self):
        shares = EqualSplit(frozenset({CAROL, BOB, ALICE})).shares(eur("10.00"))
        assert shares.by_member == {ALICE: eur("3.34"), BOB: eur("3.33"), CAROL: eur("3.33")}

    def test_rf05_equal_split_never_loses_cents(self):
        amount = eur("10.00")
        assert EqualSplit(frozenset({ALICE, BOB, CAROL})).shares(amount).total() == amount

    def test_participants_are_exposed(self):
        assert EqualSplit(frozenset({ALICE, BOB})).participants == frozenset({ALICE, BOB})

    def test_empty_participants_raises_empty_participant_set(self):
        with pytest.raises(EmptyParticipantSet):
            EqualSplit(frozenset())


class TestExactSplit:
    def test_rf06_exact_split_returns_given_amounts(self):
        split = ExactSplit({ALICE: eur("7.00"), BOB: eur("3.00")})
        assert split.shares(eur("10.00")).by_member == {ALICE: eur("7.00"), BOB: eur("3.00")}

    def test_participants_are_the_keys(self):
        split = ExactSplit({ALICE: eur("7.00"), BOB: eur("3.00")})
        assert split.participants == frozenset({ALICE, BOB})

    def test_scenario3_amounts_not_matching_total_raise_split_does_not_match_amount(self):
        split = ExactSplit({ALICE: eur("7.00"), BOB: eur("2.99")})
        with pytest.raises(SplitDoesNotMatchAmount):
            split.shares(eur("10.00"))

    def test_amounts_in_other_currency_raise_currency_mismatch(self):
        split = ExactSplit({ALICE: Money.from_decimal(Decimal("10.00"), USD)})
        with pytest.raises(CurrencyMismatch):
            split.shares(eur("10.00"))

    def test_rf06_negative_exact_amount_raises_negative_share(self):
        with pytest.raises(NegativeShare):
            ExactSplit({ALICE: eur("12.00"), BOB: eur("-2.00")})

    def test_rf06_zero_exact_amount_is_allowed(self):
        split = ExactSplit({ALICE: eur("10.00"), BOB: eur("0.00")})
        assert split.shares(eur("10.00")).by_member[BOB] == eur("0.00")

    def test_empty_amounts_raises_empty_participant_set(self):
        with pytest.raises(EmptyParticipantSet):
            ExactSplit({})


class TestPercentageSplit:
    def test_rf07_percentage_split_follows_basis_points(self):
        split = PercentageSplit({ALICE: 7_000, BOB: 3_000})
        assert split.shares(eur("10.00")).by_member == {ALICE: eur("7.00"), BOB: eur("3.00")}

    def test_rf07_percentage_split_never_loses_cents(self):
        split = PercentageSplit({ALICE: 3_333, BOB: 3_333, CAROL: 3_334})
        amount = eur("0.01")
        assert split.shares(amount).total() == amount

    def test_rf07_remainder_tie_goes_to_lowest_user_id(self):
        split = PercentageSplit({CAROL: 5_000, ALICE: 5_000})
        assert split.shares(eur("0.01")).by_member == {ALICE: eur("0.01"), CAROL: eur("0.00")}

    def test_participants_are_the_keys(self):
        split = PercentageSplit({ALICE: 5_000, BOB: 5_000})
        assert split.participants == frozenset({ALICE, BOB})

    def test_scenario4_percentages_summing_to_9999_raise_percentages_do_not_sum_to_100(self):
        with pytest.raises(PercentagesDoNotSumTo100):
            PercentageSplit({ALICE: 5_000, BOB: 4_999})

    def test_rf07_negative_basis_points_raise_negative_share(self):
        with pytest.raises(NegativeShare):
            PercentageSplit({ALICE: 12_000, BOB: -2_000})

    def test_rf07_zero_basis_points_are_allowed(self):
        split = PercentageSplit({ALICE: 10_000, BOB: 0})
        assert split.shares(eur("10.00")).by_member[BOB] == eur("0.00")

    def test_empty_basis_points_raises_empty_participant_set(self):
        with pytest.raises(EmptyParticipantSet):
            PercentageSplit({})
