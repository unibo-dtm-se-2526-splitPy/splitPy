"""Use cases that change expenses and record payments (RF-06, RF-08, RF-09, RF-12)."""

from datetime import date

from splitpy_app.application.ports import UnitOfWork
from splitpy_core.domain.category import Category
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.money import Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.split import SplitStrategy
from splitpy_core.ports.clock import Clock
from splitpy_core.ports.id_generator import IdGenerator


class RegisterExpense:
    def __init__(self, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    def execute(
        self,
        *,
        group_id: GroupId,
        description: str,
        amount: Money,
        paid_by: UserId,
        split: SplitStrategy,
        category: Category,
        occurred_on: date,
        by: UserId,
    ) -> Expense:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            expense = group.register_expense(
                ExpenseId(self._ids.new_id()),
                description,
                amount,
                paid_by,
                split,
                category,
                occurred_on,
                by=by,
            )
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()
        return expense


class UpdateExpense:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(
        self, *, group_id: GroupId, expense_id: ExpenseId, by: UserId, **changes: object
    ) -> Expense:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            expense = group.update_expense(expense_id, by=by, **changes)
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()
        return expense


class RemoveExpense:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, *, group_id: GroupId, expense_id: ExpenseId, by: UserId) -> None:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            group.remove_expense(expense_id, by=by, at=at)
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()


class RecordPayment:
    def __init__(self, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    def execute(
        self,
        *,
        group_id: GroupId,
        debtor: UserId,
        creditor: UserId,
        amount: Money,
        occurred_on: date,
        note: str = "",
        by: UserId,
    ) -> Payment:
        at = self._clock.now()
        with self._uow:
            group = self._uow.groups.get(group_id)
            payment = group.record_payment(
                PaymentId(self._ids.new_id()),
                debtor,
                creditor,
                amount,
                occurred_on,
                note,
                by=by,
            )
            self._uow.groups.save(group)
            self._uow.events.append(group.pull_events(), at=at)
            self._uow.commit()
        return payment
