"""Explicit translation between the domain and the database rows, in both directions."""

from datetime import datetime
from typing import Any
from uuid import UUID

from splitpy_app.adapters.persistence.models import (
    EventRow,
    ExpenseRow,
    GroupRow,
    MemberRow,
    PaymentRow,
    ShareRow,
    SplitType,
)
from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain import events
from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import EqualSplit, ExactSplit, PercentageSplit, SplitStrategy


def group_to_row(group: Group) -> GroupRow:
    return GroupRow(
        id=group.id.value,
        name=group.name,
        currency=group.currency.code,
        status=group.status.value,
        version=group.version,
        members=[_member_to_row(member) for member in group.members()],
        expenses=[_expense_to_row(expense) for expense in group.expenses()],
        payments=[_payment_to_row(payment) for payment in group.payments()],
    )


def group_from_row(row: GroupRow) -> Group:
    currency = Currency(row.currency)
    return Group(
        GroupId(row.id),
        row.name,
        currency,
        [_member_from_row(member) for member in row.members],
        [_expense_from_row(expense, currency) for expense in row.expenses],
        [_payment_from_row(payment, currency) for payment in row.payments],
        GroupStatus(row.status),
        version=row.version,
    )


def event_to_row(event: events.DomainEvent, *, at: datetime) -> EventRow:
    actor, payload = _actor_and_payload(event)
    return EventRow(
        group_id=event.group_id.value,
        type=type(event).__name__,
        payload=payload,
        actor_id=actor.value,
        occurred_at=at,
    )


def event_from_row(row: EventRow) -> RecordedEvent:
    return RecordedEvent(_event_from_row(row), row.occurred_at)


def _member_to_row(member: Member) -> MemberRow:
    return MemberRow(
        user_id=member.user_id.value,
        role=member.role.value,
        joined_at=member.joined_at,
        left_at=member.left_at,
    )


def _member_from_row(row: MemberRow) -> Member:
    return Member(UserId(row.user_id), Role(row.role), joined_at=row.joined_at, left_at=row.left_at)


def _expense_to_row(expense: Expense) -> ExpenseRow:
    split_type, weights = _split_to_weights(expense.split)
    shares = expense.shares().by_member
    return ExpenseRow(
        id=expense.id.value,
        description=expense.description,
        amount_cents=expense.amount.cents,
        currency=expense.amount.currency.code,
        paid_by=expense.paid_by.value,
        category=expense.category.value,
        occurred_on=expense.occurred_on,
        split_type=split_type.value,
        deleted_at=expense.deleted_at,
        shares=[
            ShareRow(user_id=user.value, share_cents=shares[user].cents, weight=weight)
            for user, weight in sorted(weights.items())
        ],
    )


def _expense_from_row(row: ExpenseRow, currency: Currency) -> Expense:
    # The shares are not read back: the split recomputes them, cent for cent (I-01).
    return Expense(
        ExpenseId(row.id),
        row.description,
        Money(row.amount_cents, currency),
        UserId(row.paid_by),
        _split_from_row(row, currency),
        Category(row.category),
        row.occurred_on,
        row.deleted_at,
    )


def _split_to_weights(split: SplitStrategy) -> tuple[SplitType, dict[UserId, int]]:
    if isinstance(split, EqualSplit):
        return SplitType.EQUAL, dict.fromkeys(split.participants, 1)
    if isinstance(split, ExactSplit):
        return SplitType.EXACT, {user: share.cents for user, share in split.amounts.items()}
    if isinstance(split, PercentageSplit):
        return SplitType.PERCENTAGE, dict(split.basis_points)
    raise TypeError(f"cannot store a {type(split).__name__}")


def _split_from_row(row: ExpenseRow, currency: Currency) -> SplitStrategy:
    weights = {UserId(share.user_id): share.weight for share in row.shares}
    split_type = SplitType(row.split_type)
    if split_type is SplitType.EQUAL:
        return EqualSplit(frozenset(weights))
    if split_type is SplitType.EXACT:
        return ExactSplit({user: Money(cents, currency) for user, cents in weights.items()})
    return PercentageSplit(weights)


def _payment_to_row(payment: Payment) -> PaymentRow:
    return PaymentRow(
        id=payment.id.value,
        debtor_id=payment.debtor.value,
        creditor_id=payment.creditor.value,
        amount_cents=payment.amount.cents,
        currency=payment.amount.currency.code,
        occurred_on=payment.occurred_on,
        note=payment.note,
    )


def _payment_from_row(row: PaymentRow, currency: Currency) -> Payment:
    return Payment(
        PaymentId(row.id),
        UserId(row.debtor_id),
        UserId(row.creditor_id),
        Money(row.amount_cents, currency),
        row.occurred_on,
        row.note,
    )


def _money_to_json(amount: Money) -> dict[str, Any]:
    return {"amount_cents": amount.cents, "currency": amount.currency.code}


def _money_from_json(payload: dict[str, Any]) -> Money:
    return Money(payload["amount_cents"], Currency(payload["currency"]))


def _user(value: str) -> UserId:
    return UserId(UUID(value))


def _actor_and_payload(event: events.DomainEvent) -> tuple[UserId, dict[str, Any]]:
    """The actor gets a column of its own, so the payload leaves it out."""
    match event:
        case events.GroupCreated():
            return event.founder, {"name": event.name, "currency": event.currency.code}
        case events.MemberAdded():
            return event.by, {"user_id": str(event.user_id), "role": event.role.value}
        case events.MemberRemoved():
            return event.by, {"user_id": str(event.user_id)}
        case events.ExpenseRegistered():
            return event.by, {
                "expense_id": str(event.expense_id),
                **_money_to_json(event.amount),
                "paid_by": str(event.paid_by),
                "category": event.category.value,
            }
        case events.ExpenseUpdated():
            return event.by, {
                "expense_id": str(event.expense_id),
                "changed_fields": sorted(event.changed_fields),
            }
        case events.ExpenseRemoved():
            return event.by, {"expense_id": str(event.expense_id)}
        case events.PaymentRecorded():
            return event.by, {
                "payment_id": str(event.payment_id),
                "debtor": str(event.debtor),
                "creditor": str(event.creditor),
                **_money_to_json(event.amount),
            }
        case events.GroupArchived():
            return event.by, {}
    raise TypeError(f"cannot store a {type(event).__name__}")


def _event_from_row(row: EventRow) -> events.DomainEvent:
    group_id = GroupId(row.group_id)
    actor = UserId(row.actor_id)
    payload = row.payload
    match row.type:
        case "GroupCreated":
            return events.GroupCreated(
                group_id=group_id,
                name=payload["name"],
                currency=Currency(payload["currency"]),
                founder=actor,
            )
        case "MemberAdded":
            return events.MemberAdded(
                group_id=group_id,
                user_id=_user(payload["user_id"]),
                role=Role(payload["role"]),
                by=actor,
            )
        case "MemberRemoved":
            return events.MemberRemoved(
                group_id=group_id, user_id=_user(payload["user_id"]), by=actor
            )
        case "ExpenseRegistered":
            return events.ExpenseRegistered(
                group_id=group_id,
                expense_id=ExpenseId(UUID(payload["expense_id"])),
                amount=_money_from_json(payload),
                paid_by=_user(payload["paid_by"]),
                category=Category(payload["category"]),
                by=actor,
            )
        case "ExpenseUpdated":
            return events.ExpenseUpdated(
                group_id=group_id,
                expense_id=ExpenseId(UUID(payload["expense_id"])),
                changed_fields=frozenset(payload["changed_fields"]),
                by=actor,
            )
        case "ExpenseRemoved":
            return events.ExpenseRemoved(
                group_id=group_id, expense_id=ExpenseId(UUID(payload["expense_id"])), by=actor
            )
        case "PaymentRecorded":
            return events.PaymentRecorded(
                group_id=group_id,
                payment_id=PaymentId(UUID(payload["payment_id"])),
                debtor=_user(payload["debtor"]),
                creditor=_user(payload["creditor"]),
                amount=_money_from_json(payload),
                by=actor,
            )
        case "GroupArchived":
            return events.GroupArchived(group_id=group_id, by=actor)
    raise ValueError(f"unknown event type {row.type}")
