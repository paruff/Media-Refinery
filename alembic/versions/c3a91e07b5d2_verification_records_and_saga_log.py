"""verification_records table; restore saga_file_move_log dropped by f27e40bf3f18

Revision ID: c3a91e07b5d2
Revises: f27e40bf3f18
Create Date: 2026-10-27

Databases built by create_all already have both tables, so each is created only if missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3a91e07b5d2"
down_revision: str | Sequence[str] | None = "f27e40bf3f18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "saga_file_move_log" not in existing:
        op.create_table(
            "saga_file_move_log",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("plan_id", sa.String(), nullable=False),
            sa.Column("src_path", sa.String(), nullable=False),
            sa.Column("tmp_path", sa.String(), nullable=False),
            sa.Column("dest_path", sa.String(), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "prepared", "committed", "cleaned", "failed", name="sagalogstatus"
                ),
                nullable=False,
            ),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    if "verification_records" not in existing:
        op.create_table(
            "verification_records",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "media_item_id",
                sa.String(),
                sa.ForeignKey("media_items.id"),
                nullable=False,
            ),
            sa.Column("passed", sa.Boolean(), nullable=False),
            sa.Column("checks", sa.JSON(), nullable=False),
            sa.Column("output_sha256", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_table("verification_records")
    op.drop_table("saga_file_move_log")  # f27e40bf3f18's downgrade recreates it
