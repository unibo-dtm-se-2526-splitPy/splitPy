"""Split strategies: how an expense amount is divided among participants, cent-exact."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from splitpy_core.domain.errors import (
    CurrencyMismatch,
    EmptyParticipantSet,
    NegativeShare,
    PercentagesDoNotSumTo100,
    SplitDoesNotMatchAmount,
)
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Money

FULL_BASIS_POINTS = 10_000


@dataclass(frozen=True, slots=True)
class Shares:
    by_member: Mapping[UserId, Money]

    def __post_init__(self) -> None:
        if not self.by_member:
            raise EmptyParticipantSet("shares need at least one participant")

    def total(self) -> Money:
        shares = iter(self.by_member.values())
        return sum(shares, next(shares))


class SplitStrategy(Protocol):
    @property
    def participants(self) -> frozenset[UserId]: ...

    def shares(self, amount: Money) -> Shares: ...


def _allocate(amount: Money, weights: Mapping[UserId, int]) -> Shares:
    """Participants are ordered by UserId, so the largest-remainder tie-break is deterministic."""
    members = sorted(weights)
    allocated = amount.allocate([weights[member] for member in members])
    return Shares(dict(zip(members, allocated)))


@dataclass(frozen=True, slots=True)
class EqualSplit:
    participants: frozenset[UserId]

    def __post_init__(self) -> None:
        if not self.participants:
            raise EmptyParticipantSet("an equal split needs at least one participant")

    def shares(self, amount: Money) -> Shares:
        return _allocate(amount, dict.fromkeys(self.participants, 1))


@dataclass(frozen=True, slots=True)
class ExactSplit:
    amounts: Mapping[UserId, Money]

    def __post_init__(self) -> None:
        if not self.amounts:
            raise EmptyParticipantSet("an exact split needs at least one participant")
        if any(share.cents < 0 for share in self.amounts.values()):
            raise NegativeShare("an exact share cannot be negative")

    @property
    def participants(self) -> frozenset[UserId]:
        return frozenset(self.amounts)

    def shares(self, amount: Money) -> Shares:
        if any(share.currency != amount.currency for share in self.amounts.values()):
            raise CurrencyMismatch(f"exact amounts must be in {amount.currency.code}")
        shares = Shares(dict(self.amounts))
        if shares.total() != amount:
            raise SplitDoesNotMatchAmount(
                f"shares sum to {shares.total().cents}, not {amount.cents}"
            )
        return shares


@dataclass(frozen=True, slots=True)
class PercentageSplit:
    basis_points: Mapping[UserId, int]

    def __post_init__(self) -> None:
        if not self.basis_points:
            raise EmptyParticipantSet("a percentage split needs at least one participant")
        if any(points < 0 for points in self.basis_points.values()):
            raise NegativeShare("basis points cannot be negative")
        total = sum(self.basis_points.values())
        if total != FULL_BASIS_POINTS:
            raise PercentagesDoNotSumTo100(f"basis points sum to {total}, not {FULL_BASIS_POINTS}")

    @property
    def participants(self) -> frozenset[UserId]:
        return frozenset(self.basis_points)

    def shares(self, amount: Money) -> Shares:
        return _allocate(amount, self.basis_points)
