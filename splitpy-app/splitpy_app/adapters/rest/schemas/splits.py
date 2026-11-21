"""Split strategies on the wire, told apart by their type field (RF-07)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictInt

from splitpy_app.adapters.rest.schemas.base import Schema
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.money import Currency, Money
from splitpy_core.domain.split import EqualSplit, ExactSplit, PercentageSplit, SplitStrategy


class EqualSplitSchema(Schema):
    type: Literal["EQUAL"] = "EQUAL"
    participants: list[UUID]


class ExactSplitSchema(Schema):
    """Cents per participant, in the currency of the expense."""

    type: Literal["EXACT"] = "EXACT"
    amounts: dict[UUID, StrictInt]


class PercentageSplitSchema(Schema):
    type: Literal["PERCENTAGE"] = "PERCENTAGE"
    basis_points: dict[UUID, StrictInt]


SplitSchema = Annotated[
    EqualSplitSchema | ExactSplitSchema | PercentageSplitSchema, Field(discriminator="type")
]


class SplitStrategyFactory:
    """The core does not know the API format, so the strategy is built here."""

    @staticmethod
    def create(split: SplitSchema, currency: Currency) -> SplitStrategy:
        match split:
            case EqualSplitSchema():
                return EqualSplit(frozenset(UserId(user) for user in split.participants))
            case ExactSplitSchema():
                return ExactSplit(
                    {UserId(user): Money(cents, currency) for user, cents in split.amounts.items()}
                )
            case PercentageSplitSchema():
                return PercentageSplit(
                    {UserId(user): points for user, points in split.basis_points.items()}
                )


def split_schema_for(strategy: SplitStrategy) -> SplitSchema:
    """Participants are written ordered by UserId, so the same split always reads the same."""
    match strategy:
        case EqualSplit():
            return EqualSplitSchema(
                participants=[user.value for user in sorted(strategy.participants)]
            )
        case ExactSplit():
            return ExactSplitSchema(
                amounts={
                    user.value: strategy.amounts[user].cents for user in sorted(strategy.amounts)
                }
            )
        case PercentageSplit():
            return PercentageSplitSchema(
                basis_points={
                    user.value: strategy.basis_points[user]
                    for user in sorted(strategy.basis_points)
                }
            )
    raise TypeError(f"unknown split strategy {type(strategy).__name__}")
