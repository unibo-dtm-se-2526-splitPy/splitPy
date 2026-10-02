"""Net balance of each member: positive means the group owes the member, negative the opposite."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Self

from splitpy_core.domain.expense import Expense
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.payment import Payment


@dataclass(frozen=True, slots=True)
class Balances:
    by_member: Mapping[UserId, Money]

    @classmethod
    def compute(
        cls,
        currency: Currency,
        members: Iterable[UserId],
        expenses: Iterable[Expense],
        payments: Iterable[Payment],
    ) -> Self:
        """net = paid - owed + paid back - received back, over active expenses.

        The sum is zero by construction (I-02): each expense's shares add up to its amount,
        and each payment adds the same amount with opposite signs to its two members.
        """
        net = dict.fromkeys(members, Money.zero(currency))
        for expense in expenses:
            if not expense.is_active():
                continue
            net[expense.paid_by] += expense.amount
            for member, share in expense.shares().by_member.items():
                net[member] -= share
        for payment in payments:
            net[payment.debtor] += payment.amount
            net[payment.creditor] -= payment.amount
        return cls(net)

    def debtors(self) -> list[UserId]:
        return sorted(member for member, net in self.by_member.items() if net.cents < 0)

    def creditors(self) -> list[UserId]:
        return sorted(member for member, net in self.by_member.items() if net.cents > 0)

    def is_settled(self) -> bool:
        return all(net.is_zero() for net in self.by_member.values())
