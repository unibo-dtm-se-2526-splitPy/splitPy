"""A reimbursement declared between two members. It settles debt, it is not an expense."""

from dataclasses import dataclass
from datetime import date

from splitpy_core.domain.errors import InvalidPayment
from splitpy_core.domain.ids import PaymentId, UserId
from splitpy_core.domain.money import Money


@dataclass(frozen=True, slots=True)
class Payment:
    id: PaymentId
    debtor: UserId
    creditor: UserId
    amount: Money
    occurred_on: date
    note: str = ""

    def __post_init__(self) -> None:
        if self.debtor == self.creditor:
            raise InvalidPayment("debtor and creditor must be different members")
        if self.amount.cents <= 0:
            raise InvalidPayment(f"a payment amount must be positive, got {self.amount.cents}")
