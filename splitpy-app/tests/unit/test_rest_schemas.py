"""Request and response schemas of the REST API and their conversion to and from the domain."""

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError
from support import (
    ALICE,
    BOB,
    CAROL,
    DAY,
    EUR,
    FIRST_ID,
    GROUP_ID,
    FixedClock,
    SequentialIds,
    eur,
    load,
    stored_group,
)

from splitpy_app.adapters.persistence.in_memory import InMemoryUnitOfWork
from splitpy_app.adapters.rest.schemas.expenses import (
    ExpenseResponse,
    PaymentResponse,
    RecordPaymentRequest,
    RegisterExpenseRequest,
    UpdateExpenseRequest,
)
from splitpy_app.adapters.rest.schemas.groups import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupResponse,
    GroupSummaryResponse,
    UpdateGroupRequest,
)
from splitpy_app.adapters.rest.schemas.insights import (
    BalancesResponse,
    ReportResponse,
    SettlementResponse,
)
from splitpy_app.adapters.rest.schemas.money import MoneySchema
from splitpy_app.adapters.rest.schemas.splits import SplitStrategyFactory, split_schema_for
from splitpy_app.application.use_cases.expenses import RecordPayment, RegisterExpense
from splitpy_core.domain.balances import Balances
from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.errors import UnsupportedCurrency
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.group import GroupStatus
from splitpy_core.domain.ids import ExpenseId, PaymentId
from splitpy_core.domain.member import Role
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.report import SpendingReport
from splitpy_core.domain.settlement import SettlementPlan, Transfer
from splitpy_core.domain.split import EqualSplit, ExactSplit, PercentageSplit
from splitpy_core.ports.group_repository import GroupSummary

EXPENSE_ID = ExpenseId(UUID(int=100))
PAYMENT_ID = PaymentId(UUID(int=200))

A, B, C = str(ALICE), str(BOB), str(CAROL)


def money(cents: int) -> dict[str, object]:
    return {"cents": cents, "currency": "EUR"}


def json_of(schema) -> dict[str, object]:
    return schema.model_dump(mode="json")


def dinner(**overrides: object) -> dict[str, object]:
    payload = {
        "description": "Dinner",
        "amount": money(3000),
        "paid_by": A,
        "category": "FOOD",
        "occurred_on": "2026-01-15",
        "split": {"type": "EQUAL", "participants": [A, B, C]},
    }
    return payload | overrides


class TestMoney:
    def test_rnf01_amount_is_read_as_cents_and_currency(self):
        assert MoneySchema.model_validate(money(1234)).to_domain() == eur("12.34")

    @pytest.mark.parametrize("cents", [12.5, 12.0, "1234", True])
    def test_rnf01_cents_must_be_an_integer(self, cents):
        with pytest.raises(ValidationError):
            MoneySchema.model_validate({"cents": cents, "currency": "EUR"})

    def test_rnf01_amount_is_written_as_integer_cents(self):
        assert json_of(MoneySchema.from_domain(eur("12.34"))) == money(1234)

    def test_rf04_unsupported_currency_raises_unsupported_currency(self):
        with pytest.raises(UnsupportedCurrency):
            MoneySchema.model_validate({"cents": 100, "currency": "JPY"}).to_domain()


class TestSplits:
    @pytest.mark.parametrize(
        ("payload", "strategy"),
        [
            ({"type": "EQUAL", "participants": [A, B]}, EqualSplit(frozenset({ALICE, BOB}))),
            (
                {"type": "EXACT", "amounts": {A: 1000, B: 500}},
                ExactSplit({ALICE: eur("10.00"), BOB: eur("5.00")}),
            ),
            (
                {"type": "PERCENTAGE", "basis_points": {A: 7000, B: 3000}},
                PercentageSplit({ALICE: 7000, BOB: 3000}),
            ),
        ],
    )
    def test_rf07_each_split_type_builds_its_strategy(self, payload, strategy):
        split = RegisterExpenseRequest.model_validate(dinner(split=payload)).split

        assert SplitStrategyFactory.create(split, EUR) == strategy

    @pytest.mark.parametrize(
        "split",
        [
            {"type": "SHARES", "participants": [A]},
            {"type": "PERCENTAGE", "basis_points": {A: 5000.0, B: 5000}},
            {"type": "EXACT", "amounts": {A: 10.5}},
        ],
    )
    def test_rf07_unknown_types_and_non_integer_values_are_rejected(self, split):
        with pytest.raises(ValidationError):
            RegisterExpenseRequest.model_validate(dinner(split=split))

    @pytest.mark.parametrize(
        "payload",
        [
            {"type": "EQUAL", "participants": [A, B]},
            {"type": "EXACT", "amounts": {A: 1000, B: 500}},
            {"type": "PERCENTAGE", "basis_points": {A: 7000, B: 3000}},
        ],
    )
    def test_rf07_split_is_written_in_the_shape_it_is_read(self, payload):
        split = RegisterExpenseRequest.model_validate(dinner(split=payload)).split

        assert json_of(split_schema_for(SplitStrategyFactory.create(split, EUR))) == payload

    def test_rf07_a_strategy_the_api_does_not_know_cannot_be_written(self):
        class Unknown:
            participants = frozenset({ALICE})

        with pytest.raises(TypeError):
            split_schema_for(Unknown())


class TestGroups:
    def test_rf04_create_request_converts_to_the_create_command(self):
        request = CreateGroupRequest.model_validate({"name": "Flat", "currency": "EUR"})

        assert request.command() == {"name": "Flat", "currency": EUR}

    def test_rf04_unknown_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            CreateGroupRequest.model_validate({"name": "Flat", "currency": "EUR", "admin": A})

    def test_rf05_added_member_is_a_plain_member_unless_told_otherwise(self):
        request = AddMemberRequest.model_validate({"user_id": B})

        assert request.command() == {"user_id": BOB, "role": Role.MEMBER}

    def test_rf16_update_request_can_only_archive(self):
        assert UpdateGroupRequest.model_validate({"status": "ARCHIVED"}).status is (
            GroupStatus.ARCHIVED
        )
        with pytest.raises(ValidationError):
            UpdateGroupRequest.model_validate({"status": "ACTIVE"})

    def test_rf04_group_is_written_with_its_members(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)

        assert json_of(GroupResponse.from_domain(load(uow))) == {
            "id": str(GROUP_ID),
            "name": "Flat",
            "currency": "EUR",
            "status": "ACTIVE",
            "members": [
                {
                    "user_id": A,
                    "role": "ADMIN",
                    "joined_at": "2026-01-01T00:00:00Z",
                    "left_at": None,
                },
                {
                    "user_id": B,
                    "role": "MEMBER",
                    "joined_at": "2026-01-01T00:00:00Z",
                    "left_at": None,
                },
            ],
        }

    def test_rf04_summary_is_written_with_name_currency_and_status(self):
        summary = GroupSummary(GROUP_ID, "Flat", EUR, GroupStatus.ARCHIVED)

        assert json_of(GroupSummaryResponse.from_domain(summary)) == {
            "id": str(GROUP_ID),
            "name": "Flat",
            "currency": "EUR",
            "status": "ARCHIVED",
        }


class TestExpenses:
    def test_rf06_register_request_feeds_the_register_use_case(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB, CAROL)
        request = RegisterExpenseRequest.model_validate(dinner())

        expense = RegisterExpense(uow, FixedClock(), SequentialIds()).execute(
            group_id=GROUP_ID, by=ALICE, **request.command()
        )

        assert expense == Expense(
            ExpenseId(FIRST_ID),
            "Dinner",
            eur("30.00"),
            ALICE,
            EqualSplit(frozenset({ALICE, BOB, CAROL})),
            Category.FOOD,
            DAY,
        )

    def test_rf06_expense_is_written_with_its_shares_in_cents(self):
        expense = Expense(
            EXPENSE_ID,
            "Dinner",
            eur("10.00"),
            ALICE,
            EqualSplit(frozenset({ALICE, BOB, CAROL})),
            Category.FOOD,
            DAY,
        )

        assert json_of(ExpenseResponse.from_domain(expense)) == {
            "id": str(EXPENSE_ID),
            "description": "Dinner",
            "amount": money(1000),
            "paid_by": A,
            "category": "FOOD",
            "occurred_on": "2026-01-15",
            "split": {"type": "EQUAL", "participants": [A, B, C]},
            "shares": {A: 334, B: 333, C: 333},
        }

    def test_rf08_update_request_carries_only_the_fields_sent(self):
        request = UpdateExpenseRequest.model_validate(
            {"amount": money(4500), "category": "LEISURE"}
        )

        assert request.changes(EUR) == {"amount": eur("45.00"), "category": Category.LEISURE}

    def test_rf08_every_editable_field_can_be_sent(self):
        request = UpdateExpenseRequest.model_validate(dinner(paid_by=B, occurred_on="2026-01-20"))

        assert request.changes(EUR) == {
            "description": "Dinner",
            "amount": eur("30.00"),
            "paid_by": BOB,
            "category": Category.FOOD,
            "occurred_on": date(2026, 1, 20),
            "split": EqualSplit(frozenset({ALICE, BOB, CAROL})),
        }

    def test_rf08_exact_split_without_amount_is_read_in_the_group_currency(self):
        request = UpdateExpenseRequest.model_validate(
            {"split": {"type": "EXACT", "amounts": {A: 2000, B: 1000}}}
        )

        assert request.changes(EUR) == {
            "split": ExactSplit({ALICE: eur("20.00"), BOB: eur("10.00")})
        }

    def test_rf08_unknown_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            UpdateExpenseRequest.model_validate({"deleted_at": "2026-01-15T00:00:00Z"})

    def test_rf12_payment_request_feeds_the_record_payment_use_case(self):
        uow = InMemoryUnitOfWork()
        stored_group(uow, BOB)
        request = RecordPaymentRequest.model_validate(
            {"debtor": B, "creditor": A, "amount": money(1500), "occurred_on": "2026-01-15"}
        )

        payment = RecordPayment(uow, FixedClock(), SequentialIds()).execute(
            group_id=GROUP_ID, by=BOB, **request.command()
        )

        assert payment == Payment(PaymentId(FIRST_ID), BOB, ALICE, eur("15.00"), DAY)

    def test_rf12_payment_is_written_with_its_amount_in_cents(self):
        payment = Payment(PAYMENT_ID, BOB, ALICE, eur("15.00"), DAY, "rent")

        assert json_of(PaymentResponse.from_domain(payment)) == {
            "id": str(PAYMENT_ID),
            "debtor": B,
            "creditor": A,
            "amount": money(1500),
            "occurred_on": "2026-01-15",
            "note": "rent",
        }


class TestInsights:
    def test_rf10_balances_are_written_per_member(self):
        balances = Balances({BOB: eur("-5.00"), ALICE: eur("5.00")})

        assert json_of(BalancesResponse.from_domain(balances)) == {
            "by_member": {A: money(500), B: money(-500)}
        }

    def test_rf11_settlement_is_written_as_transfers(self):
        plan = SettlementPlan((Transfer(BOB, ALICE, eur("5.00")),))

        assert json_of(SettlementResponse.from_domain(plan)) == {
            "transfers": [{"debtor": B, "creditor": A, "amount": money(500)}]
        }

    def test_rf13_report_is_written_with_its_period_and_totals(self):
        report = SpendingReport(
            period=DateRange(date(2026, 1, 1), date(2026, 1, 31)),
            total=eur("30.00"),
            by_category={Category.FOOD: eur("30.00")},
            by_member={BOB: eur("15.00"), ALICE: eur("15.00")},
        )

        assert json_of(ReportResponse.from_domain(report)) == {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "total": money(3000),
            "by_category": {"FOOD": money(3000)},
            "by_member": {A: money(1500), B: money(1500)},
        }
