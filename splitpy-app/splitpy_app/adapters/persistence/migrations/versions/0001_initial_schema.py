"""Initial schema: groups with their members, expenses, shares, payments and domain events.

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_groups_currency_code")),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name=op.f("ck_groups_known_status")),
        sa.CheckConstraint("version >= 0", name=op.f("ck_groups_non_negative_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_groups")),
    )

    op.create_table(
        "group_members",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('ADMIN', 'MEMBER')", name=op.f("ck_group_members_known_role")),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("fk_group_members_group_id_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "user_id", name=op.f("pk_group_members")),
    )
    op.create_index(op.f("ix_group_members_user_id"), "group_members", ["user_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("paid_by", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("split_type", sa.String(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_expenses_positive_amount")),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_expenses_currency_code")),
        sa.CheckConstraint(
            "category IN ('FOOD', 'HOUSING', 'TRANSPORT', 'LEISURE', 'UTILITIES', 'OTHER')",
            name=op.f("ck_expenses_known_category"),
        ),
        sa.CheckConstraint(
            "split_type IN ('EQUAL', 'EXACT', 'PERCENTAGE')",
            name=op.f("ck_expenses_known_split_type"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("fk_expenses_group_id_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
    )
    op.create_index(
        "ix_expenses_group_id_occurred_on",
        "expenses",
        ["group_id", sa.text("occurred_on DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_expenses_group_id_paid_by", "expenses", ["group_id", "paid_by"])

    op.create_table(
        "expense_shares",
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("share_cents", sa.BigInteger(), nullable=False),
        sa.Column("weight", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("share_cents >= 0", name=op.f("ck_expense_shares_non_negative_share")),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            name=op.f("fk_expense_shares_expense_id_expenses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("expense_id", "user_id", name=op.f("pk_expense_shares")),
    )
    op.create_index(op.f("ix_expense_shares_user_id"), "expense_shares", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("debtor_id", sa.Uuid(), nullable=False),
        sa.Column("creditor_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_payments_positive_amount")),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_payments_currency_code")),
        sa.CheckConstraint("debtor_id <> creditor_id", name=op.f("ck_payments_distinct_members")),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("fk_payments_group_id_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index("ix_payments_group_id_occurred_on", "payments", ["group_id", "occurred_on"])

    op.create_table(
        "domain_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("fk_domain_events_group_id_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domain_events")),
    )
    op.create_index(
        "ix_domain_events_group_id_occurred_at",
        "domain_events",
        ["group_id", sa.text("occurred_at DESC")],
    )


def downgrade() -> None:
    # Children first: the foreign keys point to the groups.
    op.drop_table("domain_events")
    op.drop_table("payments")
    op.drop_table("expense_shares")
    op.drop_table("expenses")
    op.drop_table("group_members")
    op.drop_table("groups")
