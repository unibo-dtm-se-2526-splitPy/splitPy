"""Domain events of the Group aggregate: the activity feed (RF-15) is built from them."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_core.domain import events
from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import NotAnAdministrator
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit

EUR = Currency("EUR")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))

GROUP_ID = GroupId(UUID(int=10))
EXPENSE_ID = ExpenseId(UUID(int=100))
PAYMENT_ID = PaymentId(UUID(int=200))

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
DAY = date(2026, 1, 2)


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def group_with_bob() -> Group:
    """Alice founds the group and adds Bob; the events of the setup are already pulled."""
    group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
    group.add_member(BOB, Role.MEMBER, by=ALICE, at=T1)
    group.pull_events()
    return group


def register_dinner(group: Group) -> None:
    group.register_expense(
        EXPENSE_ID,
        "Dinner",
        eur("30.00"),
        ALICE,
        EqualSplit(frozenset({ALICE, BOB})),
        Category.FOOD,
        DAY,
        by=ALICE,
    )


class TestPullEvents:
    def test_rf15_create_records_group_created(self):
        group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
        assert group.pull_events() == [
            events.GroupCreated(group_id=GROUP_ID, name="Flat", currency=EUR, founder=ALICE)
        ]

    def test_pull_events_empties_the_queue(self):
        group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
        group.pull_events()
        assert group.pull_events() == []

    def test_a_reconstituted_group_has_no_events(self):
        group = Group(GROUP_ID, "Flat", EUR, [Member(ALICE, Role.ADMIN, joined_at=T0)])
        assert group.pull_events() == []

    def test_events_are_returned_in_the_order_they_happened(self):
        group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
        group.add_member(BOB, Role.MEMBER, by=ALICE, at=T1)
        assert [type(event) for event in group.pull_events()] == [
            events.GroupCreated,
            events.MemberAdded,
        ]

    def test_a_rejected_command_records_no_event(self):
        group = group_with_bob()
        with pytest.raises(NotAnAdministrator):
            group.add_member(UserId(UUID(int=3)), Role.MEMBER, by=BOB, at=T1)
        assert group.pull_events() == []


class TestCommandEvents:
    def test_rf15_add_member_records_member_added(self):
        group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
        group.pull_events()
        group.add_member(BOB, Role.MEMBER, by=ALICE, at=T1)
        assert group.pull_events() == [
            events.MemberAdded(group_id=GROUP_ID, user_id=BOB, role=Role.MEMBER, by=ALICE)
        ]

    def test_rf15_remove_member_records_member_removed(self):
        group = group_with_bob()
        group.remove_member(BOB, by=ALICE, at=T1)
        assert group.pull_events() == [
            events.MemberRemoved(group_id=GROUP_ID, user_id=BOB, by=ALICE)
        ]

    def test_rf15_register_expense_records_expense_registered(self):
        group = group_with_bob()
        register_dinner(group)
        assert group.pull_events() == [
            events.ExpenseRegistered(
                group_id=GROUP_ID,
                expense_id=EXPENSE_ID,
                amount=eur("30.00"),
                paid_by=ALICE,
                category=Category.FOOD,
                by=ALICE,
            )
        ]

    def test_rf15_update_expense_records_the_changed_fields(self):
        group = group_with_bob()
        register_dinner(group)
        group.pull_events()
        group.update_expense(EXPENSE_ID, by=BOB, amount=eur("40.00"), description="Pizza")
        assert group.pull_events() == [
            events.ExpenseUpdated(
                group_id=GROUP_ID,
                expense_id=EXPENSE_ID,
                changed_fields=frozenset({"amount", "description"}),
                by=BOB,
            )
        ]

    def test_rf15_remove_expense_records_expense_removed(self):
        group = group_with_bob()
        register_dinner(group)
        group.pull_events()
        group.remove_expense(EXPENSE_ID, by=BOB, at=T1)
        assert group.pull_events() == [
            events.ExpenseRemoved(group_id=GROUP_ID, expense_id=EXPENSE_ID, by=BOB)
        ]

    def test_rf15_record_payment_records_payment_recorded(self):
        group = group_with_bob()
        group.record_payment(PAYMENT_ID, BOB, ALICE, eur("15.00"), DAY, by=BOB)
        assert group.pull_events() == [
            events.PaymentRecorded(
                group_id=GROUP_ID,
                payment_id=PAYMENT_ID,
                debtor=BOB,
                creditor=ALICE,
                amount=eur("15.00"),
                by=BOB,
            )
        ]

    def test_rf15_archive_records_group_archived(self):
        group = group_with_bob()
        group.archive(by=ALICE)
        assert group.pull_events() == [events.GroupArchived(group_id=GROUP_ID, by=ALICE)]
