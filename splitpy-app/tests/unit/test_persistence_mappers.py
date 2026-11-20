"""Explicit mapping between the Group aggregate, its events and the database rows."""

import json
from dataclasses import dataclass
from uuid import UUID

import pytest
from support import ALICE, BOB, CAROL, DAY, EUR, GROUP_ID, NOW, T0, eur

from splitpy_app.adapters.persistence.mappers import (
    event_from_row,
    event_to_row,
    group_from_row,
    group_to_row,
)
from splitpy_app.adapters.persistence.models import EventRow
from splitpy_app.application.ports import RecordedEvent
from splitpy_core.domain import events
from splitpy_core.domain.category import Category
from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import ExpenseId, PaymentId, UserId
from splitpy_core.domain.member import Role
from splitpy_core.domain.money import Money
from splitpy_core.domain.split import EqualSplit, ExactSplit, PercentageSplit, Shares

EXPENSE_ID = ExpenseId(UUID(int=100))
PAYMENT_ID = PaymentId(UUID(int=200))

EQUAL = EqualSplit(frozenset({ALICE, BOB, CAROL}))
EXACT = ExactSplit({ALICE: eur("7.00"), BOB: eur("3.00")})
PERCENTAGE = PercentageSplit({ALICE: 6_000, BOB: 4_000})


@dataclass(frozen=True, slots=True)
class UnknownSplit:
    """A split strategy the mappers have never heard of."""

    participants: frozenset[UserId]

    def shares(self, amount: Money) -> Shares:
        return EqualSplit(self.participants).shares(amount)


def new_group(*members) -> Group:
    group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
    for member in members:
        group.add_member(member, Role.MEMBER, by=ALICE, at=T0)
    group.pull_events()
    return group


def group_with_expense(split, amount: str = "10.00") -> Group:
    group = new_group(BOB, CAROL)
    group.register_expense(
        EXPENSE_ID, "Groceries", eur(amount), ALICE, split, Category.FOOD, DAY, by=ALICE
    )
    return group


def round_trip(group: Group) -> Group:
    return group_from_row(group_to_row(group))


class TestGroupMapping:
    def test_group_comes_back_with_everything_it_recorded(self):
        group = new_group(BOB, CAROL)
        group.register_expense(
            EXPENSE_ID, "Groceries", eur("30.00"), ALICE, EQUAL, Category.FOOD, DAY, by=ALICE
        )
        group.record_payment(PAYMENT_ID, BOB, ALICE, eur("5.00"), DAY, "cash", by=BOB)

        loaded = round_trip(group)

        assert (loaded.id, loaded.name, loaded.currency, loaded.status) == (
            GROUP_ID,
            "Flat",
            EUR,
            GroupStatus.ACTIVE,
        )
        assert list(loaded.members()) == list(group.members())
        assert list(loaded.expenses()) == list(group.expenses())
        assert list(loaded.payments()) == list(group.payments())
        assert loaded.balances() == group.balances()

    def test_version_is_carried_over(self):
        group = Group(GROUP_ID, "Flat", EUR, new_group().members(), version=7)
        assert round_trip(group).version == 7

    def test_rf16_archived_group_stays_archived(self):
        group = new_group()
        group.archive(by=ALICE)
        assert round_trip(group).status is GroupStatus.ARCHIVED

    def test_rf05_former_member_is_kept_with_their_left_at(self):
        group = new_group(BOB)
        group.remove_member(BOB, by=ALICE, at=NOW)
        loaded = round_trip(group)
        assert [member.user_id for member in loaded.active_members()] == [ALICE]
        assert list(loaded.members()) == list(group.members())

    def test_rf09_removed_expense_is_kept_with_its_deleted_at(self):
        group = group_with_expense(EQUAL)
        group.remove_expense(EXPENSE_ID, by=ALICE, at=NOW)
        loaded = round_trip(group)
        assert list(loaded.active_expenses()) == []
        assert list(loaded.expenses()) == list(group.expenses())

    @pytest.mark.parametrize("split", [EQUAL, EXACT, PERCENTAGE], ids=lambda s: type(s).__name__)
    def test_rf07_split_strategy_comes_back_unchanged(self, split):
        loaded = round_trip(group_with_expense(split))
        assert next(loaded.expenses()).split == split

    @pytest.mark.parametrize(
        ("split", "split_type", "weights"),
        [
            (EQUAL, "EQUAL", {ALICE: 1, BOB: 1, CAROL: 1}),
            (EXACT, "EXACT", {ALICE: 700, BOB: 300}),
            (PERCENTAGE, "PERCENTAGE", {ALICE: 6_000, BOB: 4_000}),
        ],
        ids=["equal", "exact", "percentage"],
    )
    def test_rf07_weight_keeps_the_parameter_of_the_split(self, split, split_type, weights):
        row = group_to_row(group_with_expense(split)).expenses[0]
        assert row.split_type == split_type
        assert {share.user_id: share.weight for share in row.shares} == {
            user.value: weight for user, weight in weights.items()
        }

    def test_i01_stored_shares_are_the_computed_ones(self):
        row = group_to_row(group_with_expense(EQUAL)).expenses[0]
        assert {share.user_id: share.share_cents for share in row.shares} == {
            ALICE.value: 334,
            BOB.value: 333,
            CAROL.value: 333,
        }
        assert sum(share.share_cents for share in row.shares) == row.amount_cents

    def test_rnf01_amounts_are_stored_as_integer_cents(self):
        group = group_with_expense(EQUAL, "12.34")
        group.record_payment(PAYMENT_ID, BOB, ALICE, eur("0.05"), DAY, by=BOB)
        row = group_to_row(group)
        assert (row.expenses[0].amount_cents, row.payments[0].amount_cents) == (1234, 5)

    def test_loaded_group_has_no_pending_events(self):
        group = new_group(BOB)
        group.archive(by=ALICE)
        assert group_from_row(group_to_row(group)).pull_events() == []

    def test_split_the_mapper_does_not_know_cannot_be_stored(self):
        group = group_with_expense(UnknownSplit(frozenset({ALICE, BOB})))
        with pytest.raises(TypeError):
            group_to_row(group)


EVENTS = [
    events.GroupCreated(group_id=GROUP_ID, name="Flat", currency=EUR, founder=ALICE),
    events.MemberAdded(group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE),
    events.MemberRemoved(group_id=GROUP_ID, user_id=BOB, by=ALICE),
    events.ExpenseRegistered(
        group_id=GROUP_ID,
        expense_id=EXPENSE_ID,
        amount=eur("12.34"),
        paid_by=BOB,
        category=Category.FOOD,
        by=ALICE,
    ),
    events.ExpenseUpdated(
        group_id=GROUP_ID,
        expense_id=EXPENSE_ID,
        changed_fields=frozenset({"amount", "description"}),
        by=ALICE,
    ),
    events.ExpenseRemoved(group_id=GROUP_ID, expense_id=EXPENSE_ID, by=ALICE),
    events.PaymentRecorded(
        group_id=GROUP_ID,
        payment_id=PAYMENT_ID,
        debtor=BOB,
        creditor=ALICE,
        amount=eur("5.00"),
        by=BOB,
    ),
    events.GroupArchived(group_id=GROUP_ID, by=ALICE),
]


class TestEventMapping:
    @pytest.mark.parametrize("event", EVENTS, ids=lambda e: type(e).__name__)
    def test_rf15_event_comes_back_with_its_instant(self, event):
        assert event_from_row(event_to_row(event, at=NOW)) == RecordedEvent(event, NOW)

    @pytest.mark.parametrize("event", EVENTS, ids=lambda e: type(e).__name__)
    def test_rf15_payload_is_plain_json(self, event):
        payload = event_to_row(event, at=NOW).payload
        assert json.loads(json.dumps(payload)) == payload

    def test_rf15_row_names_the_event_and_who_acted(self):
        row = event_to_row(EVENTS[1], at=NOW)
        assert (row.group_id, row.type, row.actor_id, row.occurred_at) == (
            GROUP_ID.value,
            "MemberAdded",
            ALICE.value,
            NOW,
        )

    def test_rf15_founder_is_who_acted_on_creation(self):
        assert event_to_row(EVENTS[0], at=NOW).actor_id == ALICE.value

    def test_rnf01_amount_in_the_payload_is_in_cents(self):
        assert event_to_row(EVENTS[3], at=NOW).payload["amount_cents"] == 1234

    def test_event_the_mapper_does_not_know_cannot_be_stored(self):
        with pytest.raises(TypeError):
            event_to_row(events.DomainEvent(group_id=GROUP_ID), at=NOW)

    def test_row_of_an_unknown_event_type_cannot_be_read(self):
        row = EventRow(
            group_id=GROUP_ID.value, type="GroupRenamed", payload={}, actor_id=ALICE.value
        )
        with pytest.raises(ValueError):
            event_from_row(row)
