"""A payment is a reimbursement between two different members, for a positive amount."""

from dataclasses import FrozenInstanceError

import pytest
from support import ALICE, BOB, DAY, PAYMENT_ID, eur

from splitpy_core.domain.errors import InvalidPayment
from splitpy_core.domain.payment import Payment


class TestPayment:
    def test_rf12_payment_records_debtor_creditor_and_amount(self):
        payment = Payment(PAYMENT_ID, ALICE, BOB, eur("12.50"), DAY, note="Pizza")
        assert (payment.debtor, payment.creditor, payment.amount) == (ALICE, BOB, eur("12.50"))

    def test_note_defaults_to_empty(self):
        assert Payment(PAYMENT_ID, ALICE, BOB, eur("12.50"), DAY).note == ""

    def test_i08_debtor_and_creditor_must_differ(self):
        with pytest.raises(InvalidPayment):
            Payment(PAYMENT_ID, ALICE, ALICE, eur("12.50"), DAY)

    def test_i08_zero_amount_is_rejected(self):
        with pytest.raises(InvalidPayment):
            Payment(PAYMENT_ID, ALICE, BOB, eur("0.00"), DAY)

    def test_i08_negative_amount_is_rejected(self):
        with pytest.raises(InvalidPayment):
            Payment(PAYMENT_ID, ALICE, BOB, eur("-1.00"), DAY)

    def test_payment_is_immutable(self):
        payment = Payment(PAYMENT_ID, ALICE, BOB, eur("12.50"), DAY)
        with pytest.raises(FrozenInstanceError):
            payment.amount = eur("1.00")
