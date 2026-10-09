"""add resumable curriculum book uploads and processing state

Revision ID: 03a1c99f4d21
Revises: 47bc7a210e91
Create Date: 2026-10-09 22:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "03a1c99f4d21"
down_revision: str | Sequence[str] | None = "47bc7a210e91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("official_book_sources") as batch_op:
        batch_op.alter_column(
            "file_size",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )
        batch_op.alter_column("pdf_data", existing_type=sa.LargeBinary(), nullable=True)
        batch_op.add_column(sa.Column("storage_key", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("checksum_sha256", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("author", sa.String(200), nullable=True))
        batch_op.add_column(
            sa.Column("language", sa.String(32), server_default="English", nullable=False)
        )
        batch_op.add_column(sa.Column("edition", sa.String(120), nullable=True))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("processing_status", sa.String(24), server_default="ready", nullable=False)
        )
        batch_op.add_column(
            sa.Column("processing_stage", sa.String(40), server_default="ready", nullable=False)
        )
        batch_op.add_column(
            sa.Column("processing_progress", sa.Integer(), server_default="100", nullable=False)
        )
        batch_op.add_column(
            sa.Column("processed_page_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("pipeline_version", sa.String(40), server_default="v1", nullable=False)
        )
        batch_op.add_column(
            sa.Column("processing_lease_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index("ix_official_book_sources_processing_status", ["processing_status"])
        batch_op.create_index("uq_official_book_sources_storage_key", ["storage_key"], unique=True)

    op.create_table(
        "book_upload_sessions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("storage_upload_id", sa.String(512), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), server_default="initiated", nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("uploaded_parts", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("book_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_book_upload_sessions_owner_id", "book_upload_sessions", ["owner_id"])
    op.create_index("ix_book_upload_sessions_status", "book_upload_sessions", ["status"])
    op.create_index("ix_book_upload_sessions_book_id", "book_upload_sessions", ["book_id"])
    op.create_index("ix_book_upload_sessions_expires_at", "book_upload_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_book_upload_sessions_expires_at", table_name="book_upload_sessions")
    op.drop_index("ix_book_upload_sessions_book_id", table_name="book_upload_sessions")
    op.drop_index("ix_book_upload_sessions_status", table_name="book_upload_sessions")
    op.drop_index("ix_book_upload_sessions_owner_id", table_name="book_upload_sessions")
    op.drop_table("book_upload_sessions")
    with op.batch_alter_table("official_book_sources") as batch_op:
        batch_op.drop_index("uq_official_book_sources_storage_key")
        batch_op.drop_index("ix_official_book_sources_processing_status")
        batch_op.drop_column("pipeline_version")
        batch_op.drop_column("processing_lease_until")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("last_error")
        batch_op.drop_column("processed_page_count")
        batch_op.drop_column("processing_progress")
        batch_op.drop_column("processing_stage")
        batch_op.drop_column("processing_status")
        batch_op.drop_column("description")
        batch_op.drop_column("edition")
        batch_op.drop_column("language")
        batch_op.drop_column("author")
        batch_op.drop_column("checksum_sha256")
        batch_op.drop_column("storage_key")
        batch_op.alter_column("pdf_data", existing_type=sa.LargeBinary(), nullable=False)
        batch_op.alter_column(
            "file_size",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
