"""Amounts on the wire: integer cents and a currency code, never a decimal number (RNF-01)."""

from typing import Self

from pydantic import StrictInt

from splitpy_app.adapters.rest.schemas.base import Schema
from splitpy_core.domain.money import Currency, Money


class MoneySchema(Schema):
    # Strict: 12.0 or "12" would otherwise be coerced to 12 cents.
    cents: StrictInt
    currency: str

    @classmethod
    def from_domain(cls, money: Money) -> Self:
        return cls(cents=money.cents, currency=money.currency.code)

    def to_domain(self) -> Money:
        return Money(self.cents, Currency(self.currency))
