"""Add the backtests table.

Revision ID: a3f1c8e2b7d4
Revises: 5e2a7c1d9b40
Create Date: 2026-10-17 18:20:41.208113
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f1c8e2b7d4"
down_revision: str | None = "5e2a7c1d9b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtests",
        sa.Column("id", sa.String(length=14), nullable=False),
        sa.Column("user_id", sa.String(length=14), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("instruments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("representation", sa.String(length=16), nullable=False),
        sa.Column("model_id", sa.String(length=14), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_framework", sa.String(length=16), nullable=False),
        sa.Column("setup", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("buy_and_hold_return", sa.Float(), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("engine_version", sa.String(length=16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("starred", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("seeded", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'finished', 'failed')", name=op.f("ck_backtests_status")
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.id"],
            name=op.f("fk_backtests_model_id_models"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_backtests_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backtests")),
        sa.UniqueConstraint("user_id", "number", name=op.f("uq_backtests_user_id_number")),
    )
    op.create_index(op.f("ix_backtests_model_id"), "backtests", ["model_id"], unique=False)
    op.create_index(
        "ix_backtests_user_id_created_at", "backtests", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_backtests_user_id_created_at", table_name="backtests")
    op.drop_index(op.f("ix_backtests_model_id"), table_name="backtests")
    op.drop_table("backtests")
