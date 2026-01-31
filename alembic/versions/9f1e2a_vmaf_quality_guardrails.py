"""add quality_metrics and failed_quality_check to NormalizationPlan

Revision ID: 9f1e2a
Revises: 8f469dd7ba3c
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa

revision = "9f1e2a"
down_revision = "8f469dd7ba3c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "normalization_plans", sa.Column("quality_metrics", sa.JSON(), nullable=True)
    )
    op.add_column(
        "normalization_plans",
        sa.Column(
            "failed_quality_check",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("normalization_plans", "failed_quality_check")
    op.drop_column("normalization_plans", "quality_metrics")
