"""Schemas of the expense and payment endpoints (RF-06, RF-08, RF-12)."""

from datetime import date
from typing import Self
from uuid import UUID

from pydantic import StrictInt

from splitpy_app.adapters.rest.schemas.base import Schema
from splitpy_app.adapters.rest.schemas.money import MoneySchema
from splitpy_app.adapters.rest.schemas.splits import (
    SplitSchema,
    SplitStrategyFactory,
    split_schema_for,
)
from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency
from splitpy_core.domain.payment import Payment


class RegisterExpenseRequest(Schema):
    description: str
    amount: MoneySchema
    paid_by: UUID
    category: Category
    occurred_on: date
    split: SplitSchema

    def command(self) -> dict[str, object]:
        amount = self.amount.to_domain()
        return {
            "description": self.description,
            "amount": amount,
            "paid_by": UserId(self.paid_by),
            "split": SplitStrategyFactory.create(self.split, amount.currency),
            "category": self.category,
            "occurred_on": self.occurred_on,
        }


class UpdateExpenseRequest(Schema):
    """Only the fields sent are changed; the expense keeps the others."""

    description: str | None = None
    amount: MoneySchema | None = None
    paid_by: UUID | None = None
    category: Category | None = None
    occurred_on: date | None = None
    split: SplitSchema | None = None

    def changes(self, currency: Currency) -> dict[str, object]:
        """Exact amounts are read in the group currency when the amount is not sent."""
        changes: dict[str, object] = {}
        if self.description is not None:
            changes["description"] = self.description
        if self.amount is not None:
            changes["amount"] = self.amount.to_domain()
        if self.paid_by is not None:
            changes["paid_by"] = UserId(self.paid_by)
        if self.category is not None:
            changes["category"] = self.category
        if self.occurred_on is not None:
            changes["occurred_on"] = self.occurred_on
        if self.split is not None:
            changes["split"] = SplitStrategyFactory.create(self.split, currency)
        return changes


class ExpenseResponse(Schema):
    id: UUID
    description: str
    amount: MoneySchema
    paid_by: UUID
    category: Category
    occurred_on: date
    split: SplitSchema
    shares: dict[UUID, StrictInt]

    @classmethod
    def from_domain(cls, expense: Expense) -> Self:
        shares = expense.shares().by_member
        return cls(
            id=expense.id.value,
            description=expense.description,
            amount=MoneySchema.from_domain(expense.amount),
            paid_by=expense.paid_by.value,
            category=expense.category,
            occurred_on=expense.occurred_on,
            split=split_schema_for(expense.split),
            shares={user.value: shares[user].cents for user in sorted(shares)},
        )


class RecordPaymentRequest(Schema):
    debtor: UUID
    creditor: UUID
    amount: MoneySchema
    occurred_on: date
    note: str = ""

    def command(self) -> dict[str, object]:
        return {
            "debtor": UserId(self.debtor),
            "creditor": UserId(self.creditor),
            "amount": self.amount.to_domain(),
            "occurred_on": self.occurred_on,
            "note": self.note,
        }


class PaymentResponse(Schema):
    id: UUID
    debtor: UUID
    creditor: UUID
    amount: MoneySchema
    occurred_on: date
    note: str

    @classmethod
    def from_domain(cls, payment: Payment) -> Self:
        return cls(
            id=payment.id.value,
            debtor=payment.debtor.value,
            creditor=payment.creditor.value,
            amount=MoneySchema.from_domain(payment.amount),
            occurred_on=payment.occurred_on,
            note=payment.note,
        )
