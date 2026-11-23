"""Use cases that change expenses and record payments (RF-06, RF-08, RF-09, RF-12)."""

from datetime import date

from splitpy_app.application.ports import UnitOfWork
from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import ExpenseNotFound
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


class ListPayments:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, group_id: GroupId) -> list[Payment]:
        with self._uow:
            return list(self._uow.groups.get(group_id).payments())


class GetExpense:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, group_id: GroupId, expense_id: ExpenseId) -> Expense:
        with self._uow:
            group = self._uow.groups.get(group_id)
        for expense in group.active_expenses():
            if expense.id == expense_id:
                return expense
        raise ExpenseNotFound(f"expense {expense_id} not found")


class ListExpenses:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self,
        *,
        group_id: GroupId,
        start: date | None = None,
        end: date | None = None,
        category: Category | None = None,
        paid_by: UserId | None = None,
    ) -> list[Expense]:
        """Newest first (RF-14); within a day by id, the same order on every adapter."""
        with self._uow:
            group = self._uow.groups.get(group_id)
        listed = [
            expense
            for expense in group.active_expenses()
            if (start is None or expense.occurred_on >= start)
            and (end is None or expense.occurred_on <= end)
            and (category is None or expense.category == category)
            and (paid_by is None or expense.paid_by == paid_by)
        ]
        return sorted(listed, key=lambda expense: (expense.occurred_on, expense.id), reverse=True)
