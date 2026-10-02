from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_core.domain.errors import InvalidPayment
from splitpy_core.domain.ids import PaymentId, UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment

EUR = Currency("EUR")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))

PAYMENT_ID = PaymentId(UUID(int=200))
OCCURRED_ON = date(2026, 3, 20)


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


class TestPayment:
    def test_rf12_payment_records_debtor_creditor_and_amount(self):
        payment = Payment(PAYMENT_ID, ALICE, BOB, eur("12.50"), OCCURRED_ON, note="Pizza")
        assert (payment.debtor, payment.creditor, payment.amount) == (ALICE, BOB, eur("12.50"))

    def test_note_defaults_to_empty(self):
        assert Payment(PAYMENT_ID, ALICE, BOB, eur("12.50"), OCCURRED_ON).note == ""

    def test_i08_debtor_and_creditor_must_differ(self):
        with pytest.raises(InvalidPayment):
            Payment(PAYMENT_ID, ALICE, ALICE, eur("12.50"), OCCURRED_ON)

    def test_i08_zero_amount_is_rejected(self):
        with pytest.raises(InvalidPayment):
            Payment(PAYMENT_ID, ALICE, BOB, eur("0.00"), OCCURRED_ON)

    def test_i08_negative_amount_is_rejected(self):
        with pytest.raises(InvalidPayment):
            Payment(PAYMENT_ID, ALICE, BOB, eur("-1.00"), OCCURRED_ON)

    def test_payment_is_immutable(self):
        payment = Payment(PAYMENT_ID, ALICE, BOB, eur("12.50"), OCCURRED_ON)
        with pytest.raises(AttributeError):
            payment.amount = eur("1.00")
