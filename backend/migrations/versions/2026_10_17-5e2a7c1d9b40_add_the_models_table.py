"""Add the models table.

Revision ID: 5e2a7c1d9b40
Revises: c9fdbf55cf32
Create Date: 2026-10-17 14:12:03.512274
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5e2a7c1d9b40"
down_revision: str | None = "c9fdbf55cf32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", sa.String(length=14), nullable=False),
        sa.Column("user_id", sa.String(length=14), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("framework", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(length=32), nullable=False),
        sa.Column("parameters", sa.BigInteger(), nullable=False),
        sa.Column("input_shape", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_shape", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("keras_version", sa.String(length=32), nullable=False),
        sa.Column("starred", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_models_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_models")),
    )
    op.create_index(op.f("ix_models_user_id"), "models", ["user_id"], unique=False)
    op.create_index(
        "uq_models_user_id_name",
        "models",
        ["user_id", sa.literal_column("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_models_user_id_name", table_name="models")
    op.drop_index(op.f("ix_models_user_id"), table_name="models")
    op.drop_table("models")
