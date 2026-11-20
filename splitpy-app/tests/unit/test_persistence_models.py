"""Database constraints: the last line of defence for writes that bypass the domain."""

from uuid import UUID

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support import ALICE, BOB, DAY, GROUP_ID

from splitpy_app.adapters.persistence.models import (
    Base,
    ExpenseRow,
    GroupRow,
    PaymentRow,
    ShareRow,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def group_row(**changes) -> GroupRow:
    values = {
        "id": GROUP_ID.value,
        "name": "Flat",
        "currency": "EUR",
        "status": "ACTIVE",
        "version": 1,
    }
    return GroupRow(**(values | changes))


def expense_row(**changes) -> ExpenseRow:
    values = {
        "id": UUID(int=100),
        "description": "Groceries",
        "amount_cents": 1000,
        "currency": "EUR",
        "paid_by": ALICE.value,
        "category": "FOOD",
        "occurred_on": DAY,
        "split_type": "EQUAL",
    }
    return ExpenseRow(**(values | changes))


def payment_row(**changes) -> PaymentRow:
    values = {
        "id": UUID(int=200),
        "debtor_id": BOB.value,
        "creditor_id": ALICE.value,
        "amount_cents": 500,
        "currency": "EUR",
        "occurred_on": DAY,
        "note": "",
    }
    return PaymentRow(**(values | changes))


def store(session: Session, row: GroupRow) -> None:
    session.add(row)
    session.commit()


class TestColumns:
    @pytest.mark.parametrize(
        ("table", "column"),
        [
            ("expenses", "amount_cents"),
            ("expense_shares", "share_cents"),
            ("payments", "amount_cents"),
        ],
    )
    def test_rnf01_amounts_are_integer_cents(self, table, column):
        assert isinstance(Base.metadata.tables[table].c[column].type, BigInteger)

    def test_balances_and_reports_have_no_table(self):
        assert set(Base.metadata.tables) == {
            "groups",
            "group_members",
            "expenses",
            "expense_shares",
            "payments",
            "domain_events",
        }


class TestConstraints:
    def test_valid_group_is_stored(self, session):
        row = group_row()
        row.expenses = [expense_row(shares=[ShareRow(user_id=ALICE.value, share_cents=1000)])]
        row.payments = [payment_row()]
        store(session, row)
        assert session.get(GroupRow, GROUP_ID.value).expenses[0].shares[0].share_cents == 1000

    @pytest.mark.parametrize(
        "changes", [{"status": "CLOSED"}, {"version": -1}, {"currency": "EURO"}]
    )
    def test_group_with_an_invalid_value_is_rejected(self, session, changes):
        with pytest.raises(IntegrityError):
            store(session, group_row(**changes))

    @pytest.mark.parametrize(
        "changes", [{"amount_cents": 0}, {"category": "TRAVEL"}, {"split_type": "WEIGHTED"}]
    )
    def test_expense_with_an_invalid_value_is_rejected(self, session, changes):
        with pytest.raises(IntegrityError):
            store(session, group_row(expenses=[expense_row(**changes)]))

    def test_i01_negative_share_is_rejected(self, session):
        expense = expense_row(shares=[ShareRow(user_id=ALICE.value, share_cents=-1)])
        with pytest.raises(IntegrityError):
            store(session, group_row(expenses=[expense]))

    def test_i08_payment_between_the_same_member_is_rejected(self, session):
        payment = payment_row(debtor_id=ALICE.value, creditor_id=ALICE.value)
        with pytest.raises(IntegrityError):
            store(session, group_row(payments=[payment]))

    def test_i08_payment_amount_must_be_positive(self, session):
        with pytest.raises(IntegrityError):
            store(session, group_row(payments=[payment_row(amount_cents=0)]))
