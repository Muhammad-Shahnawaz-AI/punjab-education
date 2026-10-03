"""add user settings and AI generation logs

Revision ID: ab81cd4f00a2
Revises: 9328bf80ad71
Create Date: 2026-10-03 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab81cd4f00a2"
down_revision: str | Sequence[str] | None = "9328bf80ad71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "settings",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_table(
        "ai_generation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("curriculum", sa.String(length=120), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("book", sa.String(length=160), nullable=False),
        sa.Column("chapter", sa.String(length=160), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("question_type", sa.String(length=24), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_generation_logs_created_by_id"),
        "ai_generation_logs",
        ["created_by_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ai_generation_logs_created_by_id"),
        table_name="ai_generation_logs",
    )
    op.drop_table("ai_generation_logs")
    op.drop_column("users", "settings")
