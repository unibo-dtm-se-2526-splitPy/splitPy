"""Spending report: how much each member consumed in a period, not who owes whom."""

from collections.abc import Mapping
from dataclasses import dataclass

from splitpy_core.domain.category import Category
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.group import Group
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Money


@dataclass(frozen=True, slots=True)
class SpendingReport:
    period: DateRange
    total: Money
    by_category: Mapping[Category, Money]
    by_member: Mapping[UserId, Money]


class ReportService:
    @staticmethod
    def spending(group: Group, period: DateRange) -> SpendingReport:
        """Active expenses in the period, extremes included.

        A member's figure is the sum of their shares, so both breakdowns add up to the total.
        Payments are left out: a reimbursement settles debt, it is not consumption.
        """
        total = Money.zero(group.currency)
        by_category: dict[Category, Money] = {}
        by_member: dict[UserId, Money] = {}
        for expense in group.active_expenses():
            if not period.contains(expense.occurred_on):
                continue
            total += expense.amount
            by_category[expense.category] = (
                by_category.get(expense.category, Money.zero(group.currency)) + expense.amount
            )
            for member, share in expense.shares().by_member.items():
                by_member[member] = by_member.get(member, Money.zero(group.currency)) + share
        return SpendingReport(period, total, by_category, by_member)
