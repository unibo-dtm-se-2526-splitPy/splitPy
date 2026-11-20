"""SQLAlchemy tables, kept apart from the domain entities: the mappers translate between them."""

from collections.abc import Iterable
from datetime import date, datetime
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from splitpy_core.domain.category import Category
from splitpy_core.domain.group import GroupStatus
from splitpy_core.domain.member import Role

# Named constraints, so that migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class SplitType(StrEnum):
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    PERCENTAGE = "PERCENTAGE"


def one_of(column: str, values: Iterable[str]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


class GroupRow(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("length(currency) = 3", name="currency_code"),
        CheckConstraint(one_of("status", GroupStatus), name="known_status"),
        CheckConstraint("version >= 0", name="non_negative_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str]
    version: Mapped[int]

    members: Mapped[list["MemberRow"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    expenses: Mapped[list["ExpenseRow"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list["PaymentRow"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class MemberRow(Base):
    __tablename__ = "group_members"
    __table_args__ = (CheckConstraint(one_of("role", Role), name="known_role"),)

    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    # For "my groups". No foreign key to users yet: they arrive with authentication.
    user_id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    role: Mapped[str]
    joined_at: Mapped[datetime]
    left_at: Mapped[datetime | None]


class ExpenseRow(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="positive_amount"),
        CheckConstraint("length(currency) = 3", name="currency_code"),
        CheckConstraint(one_of("category", Category), name="known_category"),
        CheckConstraint(one_of("split_type", SplitType), name="known_split_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    group_id: Mapped[UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    description: Mapped[str]
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    # Always the group currency: the domain enforces it, the column keeps amounts readable.
    currency: Mapped[str] = mapped_column(String(3))
    paid_by: Mapped[UUID]
    category: Mapped[str]
    occurred_on: Mapped[date]
    split_type: Mapped[str]
    deleted_at: Mapped[datetime | None]

    shares: Mapped[list["ShareRow"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ShareRow(Base):
    """The computed share, plus the weight that rebuilds the split strategy."""

    __tablename__ = "expense_shares"
    __table_args__ = (CheckConstraint("share_cents >= 0", name="non_negative_share"),)

    expense_id: Mapped[UUID] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    share_cents: Mapped[int] = mapped_column(BigInteger)
    # 1 for an equal split, cents for an exact one, basis points for a percentage one.
    weight: Mapped[int] = mapped_column(BigInteger, default=1)


class PaymentRow(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="positive_amount"),
        CheckConstraint("length(currency) = 3", name="currency_code"),
        # Already enforced by the domain (I-08): this guards writes that bypass it.
        CheckConstraint("debtor_id <> creditor_id", name="distinct_members"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    group_id: Mapped[UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    debtor_id: Mapped[UUID]
    creditor_id: Mapped[UUID]
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    occurred_on: Mapped[date]
    note: Mapped[str]


class EventRow(Base):
    __tablename__ = "domain_events"

    # SQLite only autoincrements an INTEGER primary key.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    group_id: Mapped[UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    type: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    actor_id: Mapped[UUID]
    occurred_at: Mapped[datetime]


# Listing and reporting skip removed expenses, so the index leaves them out.
Index(
    "ix_expenses_group_id_occurred_on",
    ExpenseRow.group_id,
    ExpenseRow.occurred_on.desc(),
    postgresql_where=ExpenseRow.deleted_at.is_(None),
)
Index("ix_expenses_group_id_paid_by", ExpenseRow.group_id, ExpenseRow.paid_by)
Index("ix_payments_group_id_occurred_on", PaymentRow.group_id, PaymentRow.occurred_on)
# The activity feed reads a group's events newest first (RF-15).
Index("ix_domain_events_group_id_occurred_at", EventRow.group_id, EventRow.occurred_at.desc())
