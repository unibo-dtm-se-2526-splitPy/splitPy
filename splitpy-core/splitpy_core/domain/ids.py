"""Typed identifiers: an id of one kind is never equal or comparable to an id of another."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True, order=True)
class UserId:
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True, order=True)
class GroupId:
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True, order=True)
class ExpenseId:
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True, order=True)
class PaymentId:
    value: UUID

    def __str__(self) -> str:
        return str(self.value)
