"""The Group aggregate root: the only way to change members, expenses and payments."""

from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import date, datetime
from enum import StrEnum
from typing import Self

from splitpy_core.domain import events
from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import (
    AdminSuccessorRequired,
    AlreadyAMember,
    CurrencyMismatch,
    ExpenseNotFound,
    GroupArchived,
    MemberHasNonZeroBalance,
    NotAMember,
    NotAnAdministrator,
)
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import SplitStrategy

EDITABLE_EXPENSE_FIELDS = frozenset(
    {"description", "amount", "paid_by", "split", "category", "occurred_on"}
)


class GroupStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Group:
    """Members and expenses are frozen: the group swaps them, nobody else can change them."""

    def __init__(
        self,
        id: GroupId,
        name: str,
        currency: Currency,
        members: Iterable[Member],
        expenses: Iterable[Expense] = (),
        payments: Iterable[Payment] = (),
        status: GroupStatus = GroupStatus.ACTIVE,
    ) -> None:
        self._id = id
        self._name = name
        self._currency = currency
        self._status = status
        self._members = {member.user_id: member for member in members}
        self._expenses = {expense.id: expense for expense in expenses}
        self._payments = {payment.id: payment for payment in payments}
        # Only commands record events: a group rebuilt from storage starts with none.
        self._events: list[events.DomainEvent] = []

    @classmethod
    def create(
        cls, id: GroupId, name: str, currency: Currency, *, founder: UserId, at: datetime
    ) -> Self:
        """The founder is an ADMIN from the start, so a group is never without members."""
        group = cls(id, name, currency, [Member(founder, Role.ADMIN, joined_at=at)])
        group._record(
            events.GroupCreated(group_id=id, name=name, currency=currency, founder=founder)
        )
        return group

    @property
    def id(self) -> GroupId:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def status(self) -> GroupStatus:
        return self._status

    def add_member(self, user_id: UserId, role: Role, *, by: UserId, at: datetime) -> None:
        self._check_writable()
        self._check_admin(by)
        if self._is_active_member(user_id):
            raise AlreadyAMember(f"{user_id} is already a member")
        # A former member who rejoins gets a fresh membership.
        self._members[user_id] = Member(user_id, role, joined_at=at)
        self._record(events.MemberAdded(group_id=self._id, user_id=user_id, role=role, by=by))

    def remove_member(
        self, user_id: UserId, *, by: UserId, at: datetime, successor: UserId | None = None
    ) -> None:
        """An admin who removes themselves must name a successor, who becomes ADMIN."""
        self._check_writable()
        self._check_admin(by)
        self._check_member(user_id)
        if not self.balances().by_member[user_id].is_zero():
            raise MemberHasNonZeroBalance(f"{user_id} has a non-zero balance")
        if user_id == by:
            if successor is None or successor == user_id:
                raise AdminSuccessorRequired(f"{user_id} must name another member as admin")
            self._check_member(successor)
            self._members[successor] = replace(self._members[successor], role=Role.ADMIN)
        self._members[user_id] = replace(self._members[user_id], left_at=at)
        self._record(events.MemberRemoved(group_id=self._id, user_id=user_id, by=by))

    def register_expense(
        self,
        id: ExpenseId,
        description: str,
        amount: Money,
        paid_by: UserId,
        split: SplitStrategy,
        category: Category,
        occurred_on: date,
        *,
        by: UserId,
    ) -> Expense:
        self._check_writable()
        self._check_member(by)
        expense = Expense(id, description, amount, paid_by, split, category, occurred_on)
        self._check_expense(expense)
        self._expenses[id] = expense
        self._record(
            events.ExpenseRegistered(
                group_id=self._id,
                expense_id=id,
                amount=amount,
                paid_by=paid_by,
                category=category,
                by=by,
            )
        )
        return expense

    def update_expense(self, id: ExpenseId, *, by: UserId, **changes) -> Expense:
        self._check_writable()
        self._check_member(by)
        unknown = changes.keys() - EDITABLE_EXPENSE_FIELDS
        if unknown:
            raise TypeError(f"cannot update {', '.join(sorted(unknown))}")
        # replace() builds a new Expense, so a failed check leaves the stored one untouched.
        expense = replace(self._active_expense(id), **changes)
        self._check_expense(expense)
        self._expenses[id] = expense
        self._record(
            events.ExpenseUpdated(
                group_id=self._id, expense_id=id, changed_fields=frozenset(changes), by=by
            )
        )
        return expense

    def remove_expense(self, id: ExpenseId, *, by: UserId, at: datetime) -> None:
        self._check_writable()
        self._check_member(by)
        self._expenses[id] = replace(self._active_expense(id), deleted_at=at)
        self._record(events.ExpenseRemoved(group_id=self._id, expense_id=id, by=by))

    def record_payment(
        self,
        id: PaymentId,
        debtor: UserId,
        creditor: UserId,
        amount: Money,
        occurred_on: date,
        note: str = "",
        *,
        by: UserId,
    ) -> Payment:
        self._check_writable()
        self._check_member(by)
        payment = Payment(id, debtor, creditor, amount, occurred_on, note)
        self._check_currency(amount)
        self._check_member(debtor)
        self._check_member(creditor)
        self._payments[id] = payment
        self._record(
            events.PaymentRecorded(
                group_id=self._id,
                payment_id=id,
                debtor=debtor,
                creditor=creditor,
                amount=amount,
                by=by,
            )
        )
        return payment

    def archive(self, *, by: UserId) -> None:
        self._check_writable()
        self._check_admin(by)
        self._status = GroupStatus.ARCHIVED
        self._record(events.GroupArchived(group_id=self._id, by=by))

    def balances(self) -> Balances:
        """One balance per active member.

        Former members still appear in past expenses, so they take part in the computation;
        they left with a zero balance (I-05), so dropping them keeps the sum at zero.
        """
        computed = Balances.compute(
            self._currency, self._members, self._expenses.values(), self._payments.values()
        )
        return Balances(
            {
                user_id: net
                for user_id, net in computed.by_member.items()
                if self._is_active_member(user_id)
            }
        )

    def active_members(self) -> Iterator[Member]:
        return (member for member in self._members.values() if member.is_active())

    def active_expenses(self) -> Iterator[Expense]:
        return (expense for expense in self._expenses.values() if expense.is_active())

    def pull_events(self) -> list[events.DomainEvent]:
        """Hand over the recorded events and forget them, so each is published once."""
        pulled, self._events = self._events, []
        return pulled

    def _record(self, event: events.DomainEvent) -> None:
        self._events.append(event)

    def _check_writable(self) -> None:
        if self._status is GroupStatus.ARCHIVED:
            raise GroupArchived(f"group {self._id} is archived")

    def _is_active_member(self, user_id: UserId) -> bool:
        member = self._members.get(user_id)
        return member is not None and member.is_active()

    def _check_member(self, user_id: UserId) -> None:
        if not self._is_active_member(user_id):
            raise NotAMember(f"{user_id} is not an active member")

    def _check_admin(self, user_id: UserId) -> None:
        self._check_member(user_id)
        if self._members[user_id].role is not Role.ADMIN:
            raise NotAnAdministrator(f"{user_id} is not an administrator")

    def _check_currency(self, amount: Money) -> None:
        if amount.currency != self._currency:
            raise CurrencyMismatch(f"{amount.currency.code} != {self._currency.code}")

    def _check_expense(self, expense: Expense) -> None:
        self._check_currency(expense.amount)
        self._check_member(expense.paid_by)
        for participant in expense.split.participants:
            self._check_member(participant)

    def _active_expense(self, id: ExpenseId) -> Expense:
        expense = self._expenses.get(id)
        if expense is None or not expense.is_active():
            raise ExpenseNotFound(f"expense {id} not found")
        return expense
