"""Schemas of balances, settlement plan and report, computed on every request (RF-10, RF-11, RF-13)."""

from collections.abc import Mapping
from dataclasses import fields
from datetime import date, datetime
from enum import Enum
from typing import Any, Self
from uuid import UUID

from splitpy_app.adapters.rest.schemas.base import Schema
from splitpy_app.adapters.rest.schemas.money import MoneySchema
from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.events import DomainEvent
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency, Money
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


class ActivityEntryResponse(Schema):
    """type is the name of the domain event; data holds its fields, the group id left out."""

    type: str
    at: datetime
    data: dict[str, Any]

    @classmethod
    def from_domain(cls, recorded: RecordedEvent) -> Self:
        return cls(
            type=type(recorded.event).__name__, at=recorded.at, data=_event_data(recorded.event)
        )


class ActivityPageResponse(Schema):
    items: list[ActivityEntryResponse]
    page: int
    size: int


def _event_data(event: DomainEvent) -> dict[str, Any]:
    return {
        field.name: _plain(getattr(event, field.name))
        for field in fields(event)
        if field.name != "group_id"
    }


def _plain(value: object) -> object:
    match value:
        case Money():
            return MoneySchema.from_domain(value).model_dump()
        case Currency():
            return value.code
        case Enum():
            return value.value
        case frozenset():
            return sorted(value)
        case str():
            return value
        case _:
            # The typed ids print as their UUID.
            return str(value)
