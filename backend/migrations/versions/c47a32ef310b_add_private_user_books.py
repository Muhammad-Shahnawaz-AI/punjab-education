"""add private user books and extracted chunks

Revision ID: c47a32ef310b
Revises: ab81cd4f00a2
Create Date: 2026-10-03 01:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c47a32ef310b"
down_revision: str | Sequence[str] | None = "ab81cd4f00a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_books",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_books_owner_id"), "user_books", ["owner_id"], unique=False)

    op.create_table(
        "user_book_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["user_books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "position", name="uq_user_book_chunk_position"),
    )
    op.create_index(
        op.f("ix_user_book_chunks_book_id"),
        "user_book_chunks",
        ["book_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_book_chunks_book_id"), table_name="user_book_chunks")
    op.drop_table("user_book_chunks")
    op.drop_index(op.f("ix_user_books_owner_id"), table_name="user_books")
    op.drop_table("user_books")
