"""Use cases that register, update and remove expenses and record payments."""

from uuid import UUID

import pytest
from support import (
    ALICE,
    BOB,
    CAROL,
    DAVE,
    DAY,
    FIRST_ID,
    GROUP_ID,
    NOW,
    FixedClock,
    SequentialIds,
    eur,
    load,
    stored_group,
)

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.application.ports import RecordedEvent
from splitpy_app.application.use_cases.expenses import (
    RecordPayment,
    RegisterExpense,
    RemoveExpense,
    UpdateExpense,
)
from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import GroupNotFound, NotAMember
from splitpy_core.domain.events import (
    ExpenseRegistered,
    ExpenseRemoved,
    ExpenseUpdated,
    PaymentRecorded,
)
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import ExpenseId, PaymentId, UserId
from splitpy_core.domain.split import EqualSplit

EXPENSE_ID = ExpenseId(UUID(int=100))
EVERYONE = EqualSplit(frozenset({ALICE, BOB, CAROL}))


def feed(uow: InMemoryUnitOfWork) -> list[RecordedEvent]:
    with uow:
        return uow.events.list_for_group(GROUP_ID)


def stored_dinner(uow: InMemoryUnitOfWork) -> None:
    """A dinner of 30.00 paid by Alice and split equally among Alice, Bob and Carol."""
    group = load(uow)
    group.register_expense(
        EXPENSE_ID, "Dinner", eur("30.00"), ALICE, EVERYONE, Category.FOOD, DAY, by=ALICE
    )
    group.pull_events()
    with uow:
        uow.groups.save(group)
        uow.commit()


def register_dinner(uow: InMemoryUnitOfWork, paid_by: UserId = ALICE) -> Expense:
    return RegisterExpense(uow, FixedClock(), SequentialIds()).execute(
        group_id=GROUP_ID,
        description="Dinner",
        amount=eur("30.00"),
        paid_by=paid_by,
        split=EVERYONE,
        category=Category.FOOD,
        occurred_on=DAY,
        by=ALICE,
    )


class TestRegisterExpense:
    def test_rf06_expense_is_stored_with_an_id_from_the_generator(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        expense = register_dinner(uow)
        assert expense.id == ExpenseId(FIRST_ID)
        assert list(load(uow).active_expenses()) == [expense]

    def test_rf10_balances_reflect_the_stored_expense(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        register_dinner(uow)
        assert load(uow).balances().by_member == {
            ALICE: eur("20.00"),
            BOB: eur("-10.00"),
            CAROL: eur("-10.00"),
        }

    def test_rf15_registration_is_recorded_at_the_clock_instant(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        expense = register_dinner(uow)
        registered = ExpenseRegistered(
            group_id=GROUP_ID,
            expense_id=expense.id,
            amount=eur("30.00"),
            paid_by=ALICE,
            category=Category.FOOD,
            by=ALICE,
        )
        assert feed(uow) == [RecordedEvent(registered, NOW)]

    def test_rf06_rejected_expense_stores_nothing(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        with pytest.raises(NotAMember):
            register_dinner(uow, paid_by=DAVE)
        assert list(load(uow).expenses()) == []
        assert feed(uow) == []

    def test_unknown_group_is_not_found(self):
        with pytest.raises(GroupNotFound):
            register_dinner(InMemoryUnitOfWork())


class TestUpdateExpense:
    def test_rf08_stored_expense_takes_the_changes(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        stored_dinner(uow)
        updated = UpdateExpense(uow, FixedClock()).execute(
            group_id=GROUP_ID, expense_id=EXPENSE_ID, by=BOB, amount=eur("60.00")
        )
        assert list(load(uow).active_expenses()) == [updated]
        assert updated.amount == eur("60.00")

    def test_rf08_update_is_recorded(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        stored_dinner(uow)
        UpdateExpense(uow, FixedClock()).execute(
            group_id=GROUP_ID, expense_id=EXPENSE_ID, by=BOB, category=Category.LEISURE
        )
        updated = ExpenseUpdated(
            group_id=GROUP_ID, expense_id=EXPENSE_ID, changed_fields=frozenset({"category"}), by=BOB
        )
        assert feed(uow) == [RecordedEvent(updated, NOW)]


class TestRemoveExpense:
    def test_rf09_expense_is_removed_logically_at_the_clock_instant(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        stored_dinner(uow)
        RemoveExpense(uow, FixedClock()).execute(group_id=GROUP_ID, expense_id=EXPENSE_ID, by=BOB)
        [removed] = load(uow).expenses()
        assert removed.deleted_at == NOW
        assert list(load(uow).active_expenses()) == []

    def test_rf09_removal_is_recorded(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        stored_dinner(uow)
        RemoveExpense(uow, FixedClock()).execute(group_id=GROUP_ID, expense_id=EXPENSE_ID, by=BOB)
        removed = ExpenseRemoved(group_id=GROUP_ID, expense_id=EXPENSE_ID, by=BOB)
        assert feed(uow) == [RecordedEvent(removed, NOW)]


class TestRecordPayment:
    def test_rf12_payment_is_stored_with_an_id_from_the_generator(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        stored_dinner(uow)
        payment = RecordPayment(uow, FixedClock(), SequentialIds()).execute(
            group_id=GROUP_ID,
            debtor=BOB,
            creditor=ALICE,
            amount=eur("10.00"),
            occurred_on=DAY,
            by=BOB,
        )
        assert payment.id == PaymentId(FIRST_ID)
        assert list(load(uow).payments()) == [payment]
        assert load(uow).balances().by_member[BOB] == eur("0.00")

    def test_rf12_payment_is_recorded(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        stored_dinner(uow)
        payment = RecordPayment(uow, FixedClock(), SequentialIds()).execute(
            group_id=GROUP_ID,
            debtor=BOB,
            creditor=ALICE,
            amount=eur("10.00"),
            occurred_on=DAY,
            by=BOB,
        )
        recorded = PaymentRecorded(
            group_id=GROUP_ID,
            payment_id=payment.id,
            debtor=BOB,
            creditor=ALICE,
            amount=eur("10.00"),
            by=BOB,
        )
        assert feed(uow) == [RecordedEvent(recorded, NOW)]
