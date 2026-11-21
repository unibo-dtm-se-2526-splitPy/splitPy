"""Schemas of balances, settlement plan and report, computed on every request (RF-10, RF-11, RF-13)."""

from collections.abc import Mapping
from datetime import date
from typing import Self
from uuid import UUID

from splitpy_app.adapters.rest.schemas.base import Schema
from splitpy_app.adapters.rest.schemas.money import MoneySchema
from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Money
from splitpy_core.domain.report import SpendingReport
from splitpy_core.domain.settlement import SettlementPlan


def _by_user(amounts: Mapping[UserId, Money]) -> dict[UUID, MoneySchema]:
    return {user.value: MoneySchema.from_domain(amounts[user]) for user in sorted(amounts)}


class BalancesResponse(Schema):
    """Positive means the group owes the member, negative the opposite."""

    by_member: dict[UUID, MoneySchema]

    @classmethod
    def from_domain(cls, balances: Balances) -> Self:
        return cls(by_member=_by_user(balances.by_member))


class TransferResponse(Schema):
    debtor: UUID
    creditor: UUID
    amount: MoneySchema


class SettlementResponse(Schema):
    transfers: list[TransferResponse]

    @classmethod
    def from_domain(cls, plan: SettlementPlan) -> Self:
        return cls(
            transfers=[
                TransferResponse(
                    debtor=transfer.debtor.value,
                    creditor=transfer.creditor.value,
                    amount=MoneySchema.from_domain(transfer.amount),
                )
                for transfer in plan.transfers
            ]
        )


class ReportResponse(Schema):
    start: date
    end: date
    total: MoneySchema
    by_category: dict[Category, MoneySchema]
    by_member: dict[UUID, MoneySchema]

    @classmethod
    def from_domain(cls, report: SpendingReport) -> Self:
        return cls(
            start=report.period.start,
            end=report.period.end,
            total=MoneySchema.from_domain(report.total),
            by_category={
                category: MoneySchema.from_domain(amount)
                for category, amount in report.by_category.items()
            },
            by_member=_by_user(report.by_member),
        )
