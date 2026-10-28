"""subscription dates, note and constraints

Revision ID: a84836ba7e43
Revises: c42cf1c11196
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a84836ba7e43"
down_revision: str | Sequence[str] | None = "c42cf1c11196"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows are backfilled with the migration date, then the default is dropped.
    for column in ("start_date", "next_billing_date"):
        op.add_column(
            "subscriptions",
            sa.Column(
                column,
                sa.Date(),
                server_default=sa.text("CURRENT_DATE"),
                nullable=False,
            ),
        )
        op.alter_column("subscriptions", column, server_default=None)
    op.add_column(
        "subscriptions", sa.Column("note", sa.String(length=500), nullable=True)
    )
    op.create_index(
        op.f("ix_subscriptions_owner_id"), "subscriptions", ["owner_id"], unique=False
    )
    op.create_check_constraint(
        "ck_subscriptions_amount_positive", "subscriptions", "amount > 0"
    )
    op.create_check_constraint(
        "ck_subscriptions_billing_cycle",
        "subscriptions",
        "billing_cycle IN ('monthly', 'yearly', 'weekly', 'custom_days')",
    )
    op.create_check_constraint(
        "ck_subscriptions_custom_interval",
        "subscriptions",
        "(billing_cycle = 'custom_days' AND custom_interval_days IS NOT NULL "
        "AND custom_interval_days > 0) "
        "OR (billing_cycle <> 'custom_days' AND custom_interval_days IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_subscriptions_custom_interval", "subscriptions", type_="check"
    )
    op.drop_constraint("ck_subscriptions_billing_cycle", "subscriptions", type_="check")
    op.drop_constraint(
        "ck_subscriptions_amount_positive", "subscriptions", type_="check"
    )
    op.drop_index(op.f("ix_subscriptions_owner_id"), table_name="subscriptions")
    op.drop_column("subscriptions", "note")
    op.drop_column("subscriptions", "next_billing_date")
    op.drop_column("subscriptions", "start_date")
