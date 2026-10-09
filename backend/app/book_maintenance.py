import logging
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.book_storage import get_book_storage
from app.database import SessionLocal
from app.models import BookUploadSession

logger = logging.getLogger(__name__)


def cleanup_expired_uploads() -> tuple[int, int]:
    cleaned = 0
    failed = 0
    storage = get_book_storage()
    with SessionLocal() as db:
        sessions = db.scalars(
            select(BookUploadSession).where(
                BookUploadSession.status.in_(("initiated", "uploading", "expired")),
                BookUploadSession.expires_at <= datetime.now(UTC),
            )
        ).all()
        for session in sessions:
            try:
                storage.delete(session.storage_key, session.storage_upload_id)
                session.status = "expired"
                cleaned += 1
            except Exception:
                logger.exception("Could not clean expired book upload %s", session.id)
                failed += 1
        db.commit()
    return cleaned, failed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    deleted, errors = cleanup_expired_uploads()
    logger.info("Expired upload cleanup finished: %s removed, %s failed", deleted, errors)
    sys.exit(1 if errors else 0)
