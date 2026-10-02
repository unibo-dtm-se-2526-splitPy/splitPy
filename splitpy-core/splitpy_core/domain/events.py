"""Domain events recorded by the Group aggregate.

The use case pulls them after saving the group and stores them in the same transaction;
their real consumer is the activity feed (RF-15).
"""

from dataclasses import dataclass

from splitpy_core.domain.category import Category
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Role
from splitpy_core.domain.money import Currency, Money


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    group_id: GroupId


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupCreated(DomainEvent):
    name: str
    currency: Currency
    founder: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class MemberAdded(DomainEvent):
    user_id: UserId
    role: Role
    by: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class MemberRemoved(DomainEvent):
    user_id: UserId
    by: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpenseRegistered(DomainEvent):
    expense_id: ExpenseId
    amount: Money
    paid_by: UserId
    category: Category
    by: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpenseUpdated(DomainEvent):
    expense_id: ExpenseId
    changed_fields: frozenset[str]
    by: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpenseRemoved(DomainEvent):
    expense_id: ExpenseId
    by: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentRecorded(DomainEvent):
    payment_id: PaymentId
    debtor: UserId
    creditor: UserId
    amount: Money
    by: UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupArchived(DomainEvent):
    by: UserId
