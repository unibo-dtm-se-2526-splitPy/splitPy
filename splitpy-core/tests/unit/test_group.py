from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import (
    AdminSuccessorRequired,
    AlreadyAMember,
    CurrencyMismatch,
    ExpenseNotFound,
    GroupArchived,
    InvalidPayment,
    MemberHasNonZeroBalance,
    NonPositiveAmount,
    NotAMember,
    NotAnAdministrator,
    SplitDoesNotMatchAmount,
)
from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit, ExactSplit

EUR = Currency("EUR")
USD = Currency("USD")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
DAVE = UserId(UUID(int=4))

GROUP_ID = GroupId(UUID(int=10))
EXPENSE_ID = ExpenseId(UUID(int=100))
OTHER_EXPENSE_ID = ExpenseId(UUID(int=101))
PAYMENT_ID = PaymentId(UUID(int=200))

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)
T2 = datetime(2026, 1, 3, tzinfo=UTC)
DAY = date(2026, 1, 2)


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def new_group() -> Group:
    """Alice (ADMIN) founds the group; Bob and Carol join as members."""
    group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
    group.add_member(BOB, Role.MEMBER, by=ALICE, at=T1)
    group.add_member(CAROL, Role.MEMBER, by=ALICE, at=T1)
    return group


def register_dinner(group: Group, amount: str = "30.00", paid_by: UserId = ALICE, split=None):
    return group.register_expense(
        EXPENSE_ID,
        "Dinner",
        eur(amount),
        paid_by,
        split or EqualSplit(frozenset({ALICE, BOB, CAROL})),
        Category.FOOD,
        DAY,
        by=paid_by,
    )


def active_ids(group: Group) -> set[UserId]:
    return {member.user_id for member in group.active_members()}


class TestCreate:
    def test_rf04_founder_is_the_only_member_and_is_admin(self):
        group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
        [founder] = group.active_members()
        assert (founder.user_id, founder.role, founder.joined_at) == (ALICE, Role.ADMIN, T0)

    def test_rf04_new_group_is_active_with_its_currency(self):
        group = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0)
        assert (group.id, group.name, group.currency, group.status) == (
            GROUP_ID,
            "Flat",
            EUR,
            GroupStatus.ACTIVE,
        )


class TestMembership:
    def test_rf05_admin_adds_a_member(self):
        assert active_ids(new_group()) == {ALICE, BOB, CAROL}

    def test_rf05_non_admin_cannot_add_members(self):
        group = new_group()
        with pytest.raises(NotAnAdministrator):
            group.add_member(DAVE, Role.MEMBER, by=BOB, at=T2)

    def test_rf05_non_member_cannot_add_members(self):
        group = new_group()
        with pytest.raises(NotAMember):
            group.add_member(DAVE, Role.MEMBER, by=DAVE, at=T2)

    def test_rf05_adding_an_active_member_twice_raises_already_a_member(self):
        group = new_group()
        with pytest.raises(AlreadyAMember):
            group.add_member(BOB, Role.MEMBER, by=ALICE, at=T2)

    def test_rf05_removed_member_is_kept_with_left_at(self):
        group = new_group()
        group.remove_member(BOB, by=ALICE, at=T2)
        assert active_ids(group) == {ALICE, CAROL}

    def test_rf05_removed_member_can_rejoin(self):
        group = new_group()
        group.remove_member(BOB, by=ALICE, at=T2)
        group.add_member(BOB, Role.MEMBER, by=ALICE, at=T2)
        assert BOB in active_ids(group)

    def test_rf05_non_admin_cannot_remove_members(self):
        group = new_group()
        with pytest.raises(NotAnAdministrator):
            group.remove_member(CAROL, by=BOB, at=T2)

    def test_rf05_removing_a_non_member_raises_not_a_member(self):
        group = new_group()
        with pytest.raises(NotAMember):
            group.remove_member(DAVE, by=ALICE, at=T2)

    def test_rf05_cannot_remove_member_with_non_zero_balance(self):
        # Scenario 8: Bob owes 10.00 to Alice.
        group = new_group()
        register_dinner(group)
        with pytest.raises(MemberHasNonZeroBalance):
            group.remove_member(BOB, by=ALICE, at=T2)
        assert BOB in active_ids(group)

    def test_rf05_member_can_be_removed_once_settled(self):
        group = new_group()
        register_dinner(group)
        group.record_payment(PAYMENT_ID, BOB, ALICE, eur("10.00"), DAY, by=BOB)
        group.remove_member(BOB, by=ALICE, at=T2)
        assert BOB not in active_ids(group)


class TestAdminLeaving:
    def test_rf05_admin_leaving_without_a_successor_raises(self):
        group = new_group()
        with pytest.raises(AdminSuccessorRequired):
            group.remove_member(ALICE, by=ALICE, at=T2)
        assert ALICE in active_ids(group)

    def test_rf05_admin_leaving_hands_the_role_to_the_successor(self):
        group = new_group()
        group.remove_member(ALICE, by=ALICE, at=T2, successor=BOB)
        roles = {member.user_id: member.role for member in group.active_members()}
        assert roles == {BOB: Role.ADMIN, CAROL: Role.MEMBER}

    def test_rf05_admin_cannot_name_themselves_as_successor(self):
        group = new_group()
        with pytest.raises(AdminSuccessorRequired):
            group.remove_member(ALICE, by=ALICE, at=T2, successor=ALICE)

    def test_rf05_successor_must_be_an_active_member(self):
        group = new_group()
        with pytest.raises(NotAMember):
            group.remove_member(ALICE, by=ALICE, at=T2, successor=DAVE)
        assert ALICE in active_ids(group)

    def test_rf05_admin_with_non_zero_balance_cannot_leave_and_successor_is_not_promoted(self):
        group = new_group()
        register_dinner(group)
        with pytest.raises(MemberHasNonZeroBalance):
            group.remove_member(ALICE, by=ALICE, at=T2, successor=BOB)
        roles = {member.user_id: member.role for member in group.active_members()}
        assert roles[BOB] == Role.MEMBER


class TestEncapsulation:
    @pytest.mark.parametrize("attribute", ["id", "name", "currency", "status"])
    def test_group_attributes_are_read_only(self, attribute):
        group = new_group()
        with pytest.raises(AttributeError):
            setattr(group, attribute, getattr(group, attribute))

    def test_returned_expense_cannot_be_changed_from_outside(self):
        group = new_group()
        expense = register_dinner(group)
        with pytest.raises(AttributeError):
            expense.deleted_at = T2
        assert list(group.active_expenses()) == [expense]

    def test_returned_member_cannot_be_changed_from_outside(self):
        [founder] = Group.create(GROUP_ID, "Flat", EUR, founder=ALICE, at=T0).active_members()
        with pytest.raises(AttributeError):
            founder.role = Role.MEMBER


class TestRegisterExpense:
    def test_rf06_registered_expense_is_listed_as_active(self):
        group = new_group()
        expense = register_dinner(group)
        assert list(group.active_expenses()) == [expense]

    def test_rf06_registered_expense_carries_its_data(self):
        expense = register_dinner(new_group())
        assert (expense.id, expense.amount, expense.paid_by, expense.category) == (
            EXPENSE_ID,
            eur("30.00"),
            ALICE,
            Category.FOOD,
        )

    def test_rf06_payer_not_a_member_raises_not_a_member(self):
        # Scenario 9.
        group = new_group()
        with pytest.raises(NotAMember):
            group.register_expense(
                EXPENSE_ID,
                "Dinner",
                eur("30.00"),
                DAVE,
                EqualSplit(frozenset({ALICE, BOB})),
                Category.FOOD,
                DAY,
                by=ALICE,
            )

    def test_i03_participant_not_a_member_raises_not_a_member(self):
        group = new_group()
        with pytest.raises(NotAMember):
            register_dinner(group, split=EqualSplit(frozenset({ALICE, DAVE})))

    def test_i03_former_member_cannot_take_part_in_new_expenses(self):
        group = new_group()
        group.remove_member(CAROL, by=ALICE, at=T2)
        with pytest.raises(NotAMember):
            register_dinner(group)

    def test_i03_non_member_cannot_register_expenses(self):
        group = new_group()
        with pytest.raises(NotAMember):
            group.register_expense(
                EXPENSE_ID,
                "Dinner",
                eur("30.00"),
                ALICE,
                EqualSplit(frozenset({ALICE, BOB})),
                Category.FOOD,
                DAY,
                by=DAVE,
            )

    def test_i04_amount_in_another_currency_raises_currency_mismatch(self):
        group = new_group()
        with pytest.raises(CurrencyMismatch):
            group.register_expense(
                EXPENSE_ID,
                "Dinner",
                Money(3000, USD),
                ALICE,
                EqualSplit(frozenset({ALICE, BOB})),
                Category.FOOD,
                DAY,
                by=ALICE,
            )

    def test_i10_non_positive_amount_is_rejected(self):
        group = new_group()
        with pytest.raises(NonPositiveAmount):
            register_dinner(group, amount="0.00")


class TestUpdateExpense:
    def test_rf08_update_changes_the_expense_and_the_balances(self):
        group = new_group()
        register_dinner(group)
        updated = group.update_expense(EXPENSE_ID, by=BOB, amount=eur("60.00"))
        assert updated.amount == eur("60.00")
        assert group.balances().by_member[BOB] == eur("-20.00")

    def test_rf08_update_keeps_the_fields_not_changed(self):
        group = new_group()
        register_dinner(group)
        updated = group.update_expense(EXPENSE_ID, by=ALICE, category=Category.LEISURE)
        assert (updated.amount, updated.category) == (eur("30.00"), Category.LEISURE)

    def test_rf08_invalid_update_leaves_the_expense_unchanged(self):
        group = new_group()
        register_dinner(group)
        with pytest.raises(SplitDoesNotMatchAmount):
            group.update_expense(EXPENSE_ID, by=ALICE, split=ExactSplit({ALICE: eur("1.00")}))
        [expense] = group.active_expenses()
        assert expense.split == EqualSplit(frozenset({ALICE, BOB, CAROL}))

    def test_i03_update_with_non_member_payer_raises_not_a_member(self):
        group = new_group()
        register_dinner(group)
        with pytest.raises(NotAMember):
            group.update_expense(EXPENSE_ID, by=ALICE, paid_by=DAVE)

    def test_i04_update_with_another_currency_raises_currency_mismatch(self):
        group = new_group()
        register_dinner(group)
        with pytest.raises(CurrencyMismatch):
            group.update_expense(EXPENSE_ID, by=ALICE, amount=Money(100, USD))

    def test_unknown_field_cannot_be_updated(self):
        group = new_group()
        register_dinner(group)
        with pytest.raises(TypeError):
            group.update_expense(EXPENSE_ID, by=ALICE, deleted_at=T2)

    def test_updating_a_missing_expense_raises_expense_not_found(self):
        group = new_group()
        with pytest.raises(ExpenseNotFound):
            group.update_expense(OTHER_EXPENSE_ID, by=ALICE, amount=eur("1.00"))


class TestRemoveExpense:
    def test_rf09_removed_expense_leaves_list_and_balances(self):
        group = new_group()
        register_dinner(group)
        group.remove_expense(EXPENSE_ID, by=BOB, at=T2)
        assert list(group.active_expenses()) == []
        assert group.balances().is_settled()

    def test_rf09_removing_twice_raises_expense_not_found(self):
        group = new_group()
        register_dinner(group)
        group.remove_expense(EXPENSE_ID, by=ALICE, at=T2)
        with pytest.raises(ExpenseNotFound):
            group.remove_expense(EXPENSE_ID, by=ALICE, at=T2)

    def test_rf09_non_member_cannot_remove_expenses(self):
        group = new_group()
        register_dinner(group)
        with pytest.raises(NotAMember):
            group.remove_expense(EXPENSE_ID, by=DAVE, at=T2)


class TestRecordPayment:
    def test_rf12_payment_updates_both_balances(self):
        group = new_group()
        register_dinner(group)
        group.record_payment(PAYMENT_ID, BOB, ALICE, eur("10.00"), DAY, by=BOB)
        balances = group.balances().by_member
        assert (balances[ALICE], balances[BOB]) == (eur("10.00"), eur("0.00"))

    def test_i03_payment_with_non_member_raises_not_a_member(self):
        group = new_group()
        with pytest.raises(NotAMember):
            group.record_payment(PAYMENT_ID, DAVE, ALICE, eur("10.00"), DAY, by=ALICE)

    def test_i04_payment_in_another_currency_raises_currency_mismatch(self):
        group = new_group()
        with pytest.raises(CurrencyMismatch):
            group.record_payment(PAYMENT_ID, BOB, ALICE, Money(1000, USD), DAY, by=BOB)

    def test_i08_payment_to_oneself_raises_invalid_payment(self):
        group = new_group()
        with pytest.raises(InvalidPayment):
            group.record_payment(PAYMENT_ID, BOB, BOB, eur("10.00"), DAY, by=BOB)


class TestBalances:
    def test_rf10_one_balance_per_active_member(self):
        group = new_group()
        register_dinner(group)
        assert group.balances().by_member == {
            ALICE: eur("20.00"),
            BOB: eur("-10.00"),
            CAROL: eur("-10.00"),
        }

    def test_rf10_former_member_with_past_expenses_is_not_listed(self):
        group = new_group()
        register_dinner(group, paid_by=CAROL)
        group.record_payment(PAYMENT_ID, ALICE, CAROL, eur("10.00"), DAY, by=ALICE)
        group.record_payment(PaymentId(UUID(int=201)), BOB, CAROL, eur("10.00"), DAY, by=BOB)
        group.remove_member(CAROL, by=ALICE, at=T2)
        assert group.balances().by_member == {ALICE: eur("0.00"), BOB: eur("0.00")}


class TestArchive:
    def test_rf16_admin_archives_the_group(self):
        group = new_group()
        group.archive(by=ALICE)
        assert group.status == GroupStatus.ARCHIVED

    def test_rf16_non_admin_cannot_archive(self):
        group = new_group()
        with pytest.raises(NotAnAdministrator):
            group.archive(by=BOB)

    @pytest.mark.parametrize(
        "command",
        [
            lambda g: g.add_member(DAVE, Role.MEMBER, by=ALICE, at=T2),
            lambda g: g.remove_member(CAROL, by=ALICE, at=T2),
            lambda g: register_dinner(g),
            lambda g: g.update_expense(EXPENSE_ID, by=ALICE, amount=eur("1.00")),
            lambda g: g.remove_expense(EXPENSE_ID, by=ALICE, at=T2),
            lambda g: g.record_payment(PAYMENT_ID, BOB, ALICE, eur("1.00"), DAY, by=BOB),
            lambda g: g.archive(by=ALICE),
        ],
        ids=[
            "add_member",
            "remove_member",
            "register_expense",
            "update_expense",
            "remove_expense",
            "record_payment",
            "archive",
        ],
    )
    def test_i09_archived_group_rejects_every_write(self, command):
        group = new_group()
        group.archive(by=ALICE)
        with pytest.raises(GroupArchived):
            command(group)

    def test_i09_archived_group_can_still_be_read(self):
        group = new_group()
        register_dinner(group)
        group.archive(by=ALICE)
        assert group.balances().by_member[ALICE] == eur("20.00")
