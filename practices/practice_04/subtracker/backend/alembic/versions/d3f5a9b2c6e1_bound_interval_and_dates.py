"""bound custom interval and subscription dates

Revision ID: d3f5a9b2c6e1
Revises: a84836ba7e43
Create Date: 2026-10-16

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d3f5a9b2c6e1"
down_revision: str | Sequence[str] | None = "a84836ba7e43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_INTERVAL_RULE = (
    "(billing_cycle = 'custom_days' AND custom_interval_days IS NOT NULL "
    "AND custom_interval_days > 0) "
    "OR (billing_cycle <> 'custom_days' AND custom_interval_days IS NULL)"
)
NEW_INTERVAL_RULE = (
    "(billing_cycle = 'custom_days' AND custom_interval_days IS NOT NULL "
    "AND custom_interval_days BETWEEN 1 AND 3650) "
    "OR (billing_cycle <> 'custom_days' AND custom_interval_days IS NULL)"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_subscriptions_custom_interval", "subscriptions", type_="check"
    )
    op.create_check_constraint(
        "ck_subscriptions_custom_interval", "subscriptions", NEW_INTERVAL_RULE
    )
    op.create_check_constraint(
        "ck_subscriptions_dates_range",
        "subscriptions",
        "start_date BETWEEN '2000-01-01' AND '2100-12-31' "
        "AND next_billing_date BETWEEN '2000-01-01' AND '2100-12-31'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_subscriptions_dates_range", "subscriptions", type_="check")
    op.drop_constraint(
        "ck_subscriptions_custom_interval", "subscriptions", type_="check"
    )
    op.create_check_constraint(
        "ck_subscriptions_custom_interval", "subscriptions", OLD_INTERVAL_RULE
    )
