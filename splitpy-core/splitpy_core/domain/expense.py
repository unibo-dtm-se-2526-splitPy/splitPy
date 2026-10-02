"""An expense paid by one member and split among participants; removal is a soft delete."""

from dataclasses import dataclass
from datetime import date, datetime

from splitpy_core.domain.category import Category
from splitpy_core.domain.errors import NonPositiveAmount
from splitpy_core.domain.ids import ExpenseId, UserId
from splitpy_core.domain.money import Money
from splitpy_core.domain.split import Shares, SplitStrategy


@dataclass(slots=True)
class Expense:
    id: ExpenseId
    description: str
    amount: Money
    paid_by: UserId
    split: SplitStrategy
    category: Category
    occurred_on: date
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.amount.cents <= 0:
            raise NonPositiveAmount(f"an expense amount must be positive, got {self.amount.cents}")
        # Computing the shares up front rejects a split that cannot match the amount (I-01).
        self.shares()

    def shares(self) -> Shares:
        return self.split.shares(self.amount)

    def is_active(self) -> bool:
        return self.deleted_at is None
