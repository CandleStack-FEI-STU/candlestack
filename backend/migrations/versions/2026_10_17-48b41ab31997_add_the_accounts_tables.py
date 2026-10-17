"""Add the accounts tables.

Revision ID: 48b41ab31997
Revises:
Create Date: 2026-10-17 01:01:07.188406
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "48b41ab31997"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=14), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "identities",
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=14), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("login", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_identities_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("provider", "subject", name=op.f("pk_identities")),
    )
    op.create_index(op.f("ix_identities_user_id"), "identities", ["user_id"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=14), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_identities_user_id"), table_name="identities")
    op.drop_table("identities")
    op.drop_table("users")
