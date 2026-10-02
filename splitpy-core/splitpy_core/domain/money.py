"""Money as integer cents: amounts are never floats, so no cent is ever created or lost."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from splitpy_core.domain.errors import CurrencyMismatch


@dataclass(frozen=True, slots=True)
class Currency:
    code: str


@dataclass(frozen=True, slots=True)
class Money:
    cents: int
    currency: Currency

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: Currency) -> Self:
        return cls(int(amount.scaleb(2)), currency)

    @classmethod
    def zero(cls, currency: Currency) -> Self:
        return cls(0, currency)

    def is_zero(self) -> bool:
        return self.cents == 0

    def __add__(self, other: Self) -> Self:
        self._check_same_currency(other)
        return type(self)(self.cents + other.cents, self.currency)

    def __sub__(self, other: Self) -> Self:
        self._check_same_currency(other)
        return type(self)(self.cents - other.cents, self.currency)

    def __neg__(self) -> Self:
        return type(self)(-self.cents, self.currency)

    def allocate(self, ratios: list[int]) -> list[Self]:
        """Split by ratios with the largest remainder method; ties go to the lowest index."""
        total = sum(ratios)
        cents = [self.cents * ratio // total for ratio in ratios]
        remainders = [self.cents * ratio % total for ratio in ratios]
        leftover = self.cents - sum(cents)
        by_remainder = sorted(range(len(ratios)), key=lambda i: (-remainders[i], i))
        for i in by_remainder[:leftover]:
            cents[i] += 1
        return [type(self)(c, self.currency) for c in cents]

    def _check_same_currency(self, other: Self) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(f"{self.currency.code} != {other.currency.code}")
