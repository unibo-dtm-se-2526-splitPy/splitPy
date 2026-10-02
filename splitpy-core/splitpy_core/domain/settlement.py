"""Settlement plan: who pays whom to bring every balance back to zero."""

from dataclasses import dataclass

from splitpy_core.domain.balances import Balances
from splitpy_core.domain.errors import NonPositiveAmount
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Money


@dataclass(frozen=True, slots=True)
class Transfer:
    debtor: UserId
    creditor: UserId
    amount: Money

    def __post_init__(self) -> None:
        if self.amount.cents <= 0:
            raise NonPositiveAmount(f"a transfer amount must be positive, got {self.amount.cents}")


@dataclass(frozen=True, slots=True)
class SettlementPlan:
    transfers: tuple[Transfer, ...]


class SettlementService:
    @staticmethod
    def plan(balances: Balances) -> SettlementPlan:
        """Greedy heuristic: the largest debtor pays the largest creditor, ties broken by UserId.

        Every transfer zeroes at least one member, so the plan has at most N-1 transfers for
        N unsettled members (I-07). It is not guaranteed to be minimal: the exact minimum is
        NP-hard, and the greedy runs in O(N log N).
        """
        debtors = _by_amount_desc(
            {m: -net for m, net in balances.by_member.items() if net.cents < 0}
        )
        creditors = _by_amount_desc(
            {m: net for m, net in balances.by_member.items() if net.cents > 0}
        )
        transfers = []
        d = c = 0
        while d < len(debtors) and c < len(creditors):
            debtor, owed = debtors[d]
            creditor, due = creditors[c]
            amount = owed if owed.cents <= due.cents else due
            transfers.append(Transfer(debtor, creditor, amount))
            debtors[d] = (debtor, owed - amount)
            creditors[c] = (creditor, due - amount)
            if debtors[d][1].is_zero():
                d += 1
            if creditors[c][1].is_zero():
                c += 1
        return SettlementPlan(tuple(transfers))


def _by_amount_desc(amounts: dict[UserId, Money]) -> list[tuple[UserId, Money]]:
    return sorted(amounts.items(), key=lambda item: (-item[1].cents, item[0]))
