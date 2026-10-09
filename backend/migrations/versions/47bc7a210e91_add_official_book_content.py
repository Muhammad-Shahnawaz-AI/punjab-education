"""add approved official book sources and searchable content

Revision ID: 47bc7a210e91
Revises: c47a32ef310b
Create Date: 2026-10-09 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "47bc7a210e91"
down_revision: str | Sequence[str] | None = "c47a32ef310b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "official_book_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("rights_basis", sa.Text(), nullable=False),
        sa.Column("rights_verified_by_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=False),
        sa.Column("ocr_used", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rights_verified_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id"),
    )
    op.create_index(
        op.f("ix_official_book_sources_book_id"),
        "official_book_sources",
        ["book_id"],
        unique=True,
    )
    op.create_table(
        "official_book_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("chapter_id", sa.Integer(), nullable=True),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["official_book_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "position", name="uq_official_book_chunk_position"),
    )
    op.create_index(
        op.f("ix_official_book_chunks_source_id"),
        "official_book_chunks",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_book_chunks_chapter_id"),
        "official_book_chunks",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_book_chunks_topic_id"),
        "official_book_chunks",
        ["topic_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_official_book_chunks_topic_id"), table_name="official_book_chunks")
    op.drop_index(op.f("ix_official_book_chunks_chapter_id"), table_name="official_book_chunks")
    op.drop_index(op.f("ix_official_book_chunks_source_id"), table_name="official_book_chunks")
    op.drop_table("official_book_chunks")
    op.drop_index(op.f("ix_official_book_sources_book_id"), table_name="official_book_sources")
    op.drop_table("official_book_sources")
