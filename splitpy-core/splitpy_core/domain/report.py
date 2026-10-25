"""Spending report: how much each member consumed in a period, not who owes whom."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

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

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_category", MappingProxyType(dict(self.by_category)))
        object.__setattr__(self, "by_member", MappingProxyType(dict(self.by_member)))


class ReportService:
    @staticmethod
    def spending(group: Group, period: DateRange) -> SpendingReport:
        """Active expenses in the period, extremes included.

        A member's figure is the sum of their shares, so both breakdowns add up to the total.
        Payments are left out: a reimbursement settles debt, it is not consumption.
        """
        zero = Money.zero(group.currency)
        total = zero
        by_category: defaultdict[Category, Money] = defaultdict(lambda: zero)
        by_member: defaultdict[UserId, Money] = defaultdict(lambda: zero)
        for expense in group.active_expenses():
            if not period.contains(expense.occurred_on):
                continue
            total += expense.amount
            by_category[expense.category] += expense.amount
            for member, share in expense.shares().by_member.items():
                by_member[member] += share
        return SpendingReport(period, total, by_category, by_member)
