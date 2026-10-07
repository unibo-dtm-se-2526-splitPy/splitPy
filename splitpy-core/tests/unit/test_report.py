from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.expense import Expense
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment
from splitpy_core.domain.report import ReportService, SpendingReport
from splitpy_core.domain.split import EqualSplit, ExactSplit

EUR = Currency("EUR")

ALICE = UserId(UUID(int=1))
BOB = UserId(UUID(int=2))
CAROL = UserId(UUID(int=3))
MEMBERS = [ALICE, BOB, CAROL]

JOINED = datetime(2026, 1, 1, tzinfo=UTC)
MARCH = DateRange(date(2026, 3, 1), date(2026, 3, 31))


def eur(amount: str) -> Money:
    return Money.from_decimal(Decimal(amount), EUR)


def expense(
    n: int,
    amount: str,
    on: date = date(2026, 3, 14),
    category: Category = Category.FOOD,
    split=None,
    deleted: bool = False,
) -> Expense:
    return Expense(
        id=ExpenseId(UUID(int=100 + n)),
        description="generated",
        amount=eur(amount),
        paid_by=ALICE,
        split=split or EqualSplit(frozenset(MEMBERS)),
        category=category,
        occurred_on=on,
        deleted_at=datetime(2026, 3, 20, tzinfo=UTC) if deleted else None,
    )


def report(expenses=(), payments=(), period: DateRange = MARCH) -> SpendingReport:
    group = Group(
        GroupId(UUID(int=10)),
        "Flat",
        EUR,
        [Member(user_id, Role.MEMBER, joined_at=JOINED) for user_id in MEMBERS],
        expenses,
        payments,
    )
    return ReportService.spending(group, period)


class TestReportService:
    def test_rf13_without_expenses_the_report_is_empty(self):
        spending = report()
        assert spending.period == MARCH
        assert spending.total == eur("0")
        assert spending.by_category == {}
        assert spending.by_member == {}

    def test_rf13_totals_by_category(self):
        spending = report(
            [
                expense(1, "30.00", category=Category.FOOD),
                expense(2, "15.00", category=Category.FOOD),
                expense(3, "60.00", category=Category.HOUSING),
            ]
        )
        assert spending.total == eur("105.00")
        assert spending.by_category == {
            Category.FOOD: eur("45.00"),
            Category.HOUSING: eur("60.00"),
        }

    def test_rf13_by_member_is_what_each_one_consumed_not_what_they_paid(self):
        split = ExactSplit({ALICE: eur("10.00"), BOB: eur("30.00")})
        spending = report([expense(1, "40.00", split=split)])
        assert spending.by_member == {ALICE: eur("10.00"), BOB: eur("30.00")}

    def test_rf13_period_extremes_are_included(self):
        spending = report(
            [
                expense(1, "1.00", on=date(2026, 2, 28)),
                expense(2, "3.00", on=date(2026, 3, 1)),
                expense(3, "6.00", on=date(2026, 3, 31)),
                expense(4, "9.00", on=date(2026, 4, 1)),
            ]
        )
        assert spending.total == eur("9.00")

    def test_rf09_removed_expenses_are_excluded(self):
        spending = report([expense(1, "30.00"), expense(2, "99.00", deleted=True)])
        assert spending.total == eur("30.00")

    def test_rf13_payments_are_excluded_because_they_are_not_consumption(self):
        payment = Payment(PaymentId(UUID(int=200)), BOB, ALICE, eur("10.00"), date(2026, 3, 15))
        spending = report([expense(1, "30.00")], [payment])
        assert spending.total == eur("30.00")
        assert spending.by_member == {ALICE: eur("10.00"), BOB: eur("10.00"), CAROL: eur("10.00")}
