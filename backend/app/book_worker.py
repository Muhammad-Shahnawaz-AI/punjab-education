import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.book_storage import get_book_storage
from app.database import SessionLocal
from app.models import BookUploadSession, Chapter, OfficialBookChunk, OfficialBookSource, Topic
from app.official_content import CHAPTER_HEADING, TOPIC_HEADING

logger = logging.getLogger(__name__)
CHUNK_SIZE = 1600
CHUNK_OVERLAP = 200
MAX_PAGES = int(os.getenv("MAX_PDF_PAGES", "5000"))
MAX_EXTRACTED_CHARACTERS = int(os.getenv("MAX_EXTRACTED_CHARACTERS", "20000000"))
MAX_PROCESSING_SECONDS = int(os.getenv("MAX_PROCESSING_SECONDS", "21600"))
LEASE_SECONDS = int(os.getenv("PROCESSING_LEASE_SECONDS", "3600"))
MAX_OCR_PIXELS = int(os.getenv("MAX_OCR_PIXELS", "18000000"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_PROCESSING_JOBS", "1"))


class ProcessingFailure(Exception):
    pass


def _chunks(text: str) -> list[str]:
    normalized = " ".join(text.split())
    return [
        normalized[start : start + CHUNK_SIZE].strip()
        for start in range(0, len(normalized), CHUNK_SIZE - CHUNK_OVERLAP)
        if normalized[start : start + CHUNK_SIZE].strip()
    ]


def _ocr_page(document: object, page_index: int, language: str) -> str:
    if os.getenv("OCR_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return ""
    try:
        import pytesseract
    except ImportError as error:
        raise ProcessingFailure("OCR dependencies are not installed on the worker.") from error
    try:
        page = document[page_index]  # type: ignore[index]
        width, height = page.get_size()
        scale = min(1.5, (MAX_OCR_PIXELS / max(width * height, 1)) ** 0.5)
        bitmap = page.render(scale=scale)
        try:
            return pytesseract.image_to_string(bitmap.to_pil(), lang=language)
        finally:
            bitmap.close()
            page.close()
    except Exception as error:
        raise ProcessingFailure(
            "OCR failed on a page. Check the installed Tesseract executable and language data."
        ) from error


def _claim_next_job(db: Session) -> int | None:
    now = datetime.now(UTC)
    candidate = db.scalar(
        select(OfficialBookSource.id)
        .where(
            OfficialBookSource.storage_key.is_not(None),
            or_(
                OfficialBookSource.processing_status == "queued",
                (OfficialBookSource.processing_status == "processing")
                & (
                    OfficialBookSource.processing_lease_until.is_(None)
                    | (OfficialBookSource.processing_lease_until < now)
                ),
            ),
        )
        .order_by(OfficialBookSource.created_at)
        .limit(1)
    )
    if candidate is None:
        return None
    claimed = db.execute(
        update(OfficialBookSource)
        .where(
            OfficialBookSource.id == candidate,
            or_(
                OfficialBookSource.processing_status == "queued",
                (OfficialBookSource.processing_status == "processing")
                & (
                    OfficialBookSource.processing_lease_until.is_(None)
                    | (OfficialBookSource.processing_lease_until < now)
                ),
            ),
        )
        .values(
            processing_status="processing",
            processing_stage="integrity_verification",
            processing_lease_until=now + timedelta(seconds=LEASE_SECONDS),
            last_error=None,
        )
    )
    db.commit()
    return candidate if claimed.rowcount == 1 else None


def _set_failure(source_id: int, message: str) -> None:
    with SessionLocal.begin() as db:
        source = db.get(OfficialBookSource, source_id)
        if source is not None:
            source.processing_status = "failed"
            source.processing_stage = "failed"
            source.processing_lease_until = None
            source.last_error = message[:1000]


def _process_book(source_id: int) -> None:
    started = time.monotonic()
    path: Path | None = None
    remove_path = False
    try:
        with SessionLocal() as db:
            source = db.get(OfficialBookSource, source_id)
            if source is None or not source.storage_key:
                return
            storage_key = source.storage_key
            source_id_book = source.book_id
            source_file_size = source.file_size
            source.processing_stage = "pdf_validation"
            source.processing_lease_until = datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)
            db.commit()
            upload_session = db.scalar(
                select(BookUploadSession)
                .where(BookUploadSession.book_id == source_id_book)
                .order_by(BookUploadSession.created_at.desc())
            )
            metadata = upload_session.metadata_json if upload_session else {}
            ocr_requested = bool(metadata.get("use_ocr", False))
            ocr_language = str(metadata.get("ocr_language", "eng"))
        if ocr_requested and os.getenv("OCR_ENABLED", "false").lower() not in (
            "1",
            "true",
            "yes",
        ):
            raise ProcessingFailure("OCR is disabled on this worker. Enable OCR before retrying.")

        storage = get_book_storage()
        path, remove_path = storage.local_processing_path(storage_key)
        if path.stat().st_size != source_file_size:
            raise ProcessingFailure("Stored PDF size failed integrity verification.")
        with path.open("rb") as pdf_file:
            if pdf_file.read(5) != b"%PDF-":
                raise ProcessingFailure("Stored file does not have a valid PDF signature.")
            pdf_file.seek(max(0, source_file_size - 65536))
            if b"%%EOF" not in pdf_file.read(65536):
                raise ProcessingFailure("The PDF is truncated or has no end-of-file marker.")
        try:
            reader = PdfReader(str(path), strict=False)
            if reader.is_encrypted:
                raise ProcessingFailure("Password-protected PDFs are not supported.")
            page_count = len(reader.pages)
        except ProcessingFailure:
            raise
        except (PdfReadError, OSError, ValueError) as error:
            raise ProcessingFailure("The uploaded file could not be parsed as a PDF.") from error
        if page_count < 1:
            raise ProcessingFailure("The PDF contains no pages.")
        if page_count > MAX_PAGES:
            raise ProcessingFailure(f"The PDF exceeds the configured {MAX_PAGES}-page limit.")

        with SessionLocal.begin() as db:
            source = db.get(OfficialBookSource, source_id)
            if source is None:
                return
            source.page_count = page_count
            source.processing_stage = "text_extraction"
            source.processing_progress = max(
                source.processing_progress, int(source.processed_page_count * 100 / page_count)
            )
            existing_chars = (
                db.scalar(
                    select(
                        func.coalesce(func.sum(func.length(OfficialBookChunk.content)), 0)
                    ).where(OfficialBookChunk.source_id == source_id)
                )
                or 0
            )
            position = (
                db.scalar(
                    select(func.coalesce(func.max(OfficialBookChunk.position), -1)).where(
                        OfficialBookChunk.source_id == source_id
                    )
                )
                or -1
            ) + 1
            next_chapter_position = (
                db.scalar(
                    select(func.coalesce(func.max(Chapter.position), 0)).where(
                        Chapter.book_id == source.book_id
                    )
                )
                or 0
            )
            book_id = source.book_id
            source.processed_page_count = min(source.processed_page_count, page_count)
            start_page = source.processed_page_count
            source.processing_lease_until = datetime.now(UTC) + timedelta(seconds=LEASE_SECONDS)
            db.flush()

        chapters = []
        with SessionLocal() as db:
            chapters = db.scalars(
                select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.position)
            ).all()
        active_chapter = chapters[-1] if chapters else None
        ocr_document = None
        if ocr_requested and os.getenv("OCR_ENABLED", "false").lower() in ("1", "true", "yes"):
            try:
                import pypdfium2
            except ImportError as error:
                raise ProcessingFailure(
                    "OCR dependencies are not installed on the worker."
                ) from error
            ocr_document = pypdfium2.PdfDocument(str(path))
        try:
            for page_index in range(start_page, page_count):
                if time.monotonic() - started > MAX_PROCESSING_SECONDS:
                    raise ProcessingFailure("PDF processing exceeded the configured time limit.")
                page_number = page_index + 1
                page = reader.pages[page_index]
                text = page.extract_text() or ""
                used_ocr = False
                if not text.strip() and ocr_document is not None:
                    text = _ocr_page(ocr_document, page_index, ocr_language)
                    used_ocr = bool(text.strip())
                text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
                if len(text) > MAX_EXTRACTED_CHARACTERS:
                    raise ProcessingFailure("A PDF page exceeds the extracted-text safety limit.")
                existing_chars += len(text)
                if existing_chars > MAX_EXTRACTED_CHARACTERS:
                    raise ProcessingFailure(
                        "Extracted PDF text exceeds the configured safety limit."
                    )
                heading = next(
                    (
                        match.group(1).strip()
                        for line in text.splitlines()
                        if (match := CHAPTER_HEADING.match(line))
                    ),
                    None,
                )
                topic_names = list(
                    dict.fromkeys(
                        match.group(1).strip()
                        for line in text.splitlines()
                        if (match := TOPIC_HEADING.match(line))
                    )
                )
                with SessionLocal.begin() as db:
                    source = db.get(OfficialBookSource, source_id)
                    if source is None:
                        return
                    if heading and (active_chapter is None or active_chapter.name != heading):
                        existing = db.scalar(
                            select(Chapter).where(
                                Chapter.book_id == book_id, Chapter.name == heading
                            )
                        )
                        if existing is None:
                            next_chapter_position += 1
                            existing = Chapter(
                                book_id=book_id,
                                name=heading[:200],
                                position=next_chapter_position,
                            )
                            db.add(existing)
                            db.flush()
                        active_chapter = existing
                    elif active_chapter is None:
                        active_chapter = db.scalar(
                            select(Chapter)
                            .where(Chapter.book_id == book_id)
                            .order_by(Chapter.position)
                        )
                        if active_chapter is None:
                            next_chapter_position += 1
                            active_chapter = Chapter(
                                book_id=book_id,
                                name="Book content",
                                position=next_chapter_position,
                            )
                            db.add(active_chapter)
                            db.flush()
                    active_topics: dict[str, Topic] = {}
                    if active_chapter is not None:
                        for topic_name in topic_names:
                            topic = db.scalar(
                                select(Topic).where(
                                    Topic.chapter_id == active_chapter.id,
                                    Topic.name == topic_name,
                                )
                            )
                            if topic is None:
                                topic = Topic(chapter_id=active_chapter.id, name=topic_name[:240])
                                db.add(topic)
                                db.flush()
                            active_topics[topic_name.casefold()] = topic
                    for content in _chunks(text):
                        active_topic = next(
                            (
                                topic
                                for name, topic in active_topics.items()
                                if name in content.casefold()
                            ),
                            None,
                        )
                        db.add(
                            OfficialBookChunk(
                                source_id=source_id,
                                chapter_id=active_chapter.id if active_chapter else None,
                                topic_id=active_topic.id if active_topic else None,
                                position=position,
                                page_number=page_number,
                                content=content,
                            )
                        )
                        position += 1
                    if used_ocr:
                        source.ocr_used = True
                    source.processed_page_count = page_number
                    source.processing_stage = "ocr" if used_ocr else "text_extraction"
                    source.processing_progress = int(page_number * 100 / page_count)
                    source.processing_lease_until = datetime.now(UTC) + timedelta(
                        seconds=LEASE_SECONDS
                    )
        finally:
            if ocr_document is not None:
                ocr_document.close()

        with SessionLocal.begin() as db:
            source = db.get(OfficialBookSource, source_id)
            if source is None:
                return
            chunk_count = (
                db.scalar(
                    select(func.count())
                    .select_from(OfficialBookChunk)
                    .where(OfficialBookChunk.source_id == source_id)
                )
                or 0
            )
            if chunk_count == 0:
                raise ProcessingFailure(
                    "No selectable text was found. Enable OCR and retry if this is a scanned PDF."
                )
            source.processing_status = "ready"
            source.processing_stage = "ready"
            source.processing_progress = 100
            source.processed_page_count = page_count
            source.processing_lease_until = None
            source.last_error = None
    except ProcessingFailure as error:
        logger.warning("Book %s processing failed: %s", source_id, error)
        _set_failure(source_id, str(error))
    except Exception:
        logger.exception("Unexpected error processing book source %s", source_id)
        _set_failure(
            source_id, "Processing failed unexpectedly. Review worker logs before retrying."
        )
    finally:
        if remove_path and path is not None:
            path.unlink(missing_ok=True)


def process_next_job() -> bool:
    with SessionLocal() as db:
        source_id = _claim_next_job(db)
    if source_id is None:
        return False
    _process_book(source_id)
    return True


def run_worker() -> None:
    poll_seconds = max(1, int(os.getenv("WORKER_POLL_SECONDS", "5")))
    if MAX_CONCURRENT_JOBS < 1:
        raise RuntimeError("MAX_CONCURRENT_PROCESSING_JOBS must be at least one.")
    logger.info(
        "Starting curriculum PDF worker (%s concurrent jobs, %s-second polling)",
        MAX_CONCURRENT_JOBS,
        poll_seconds,
    )
    active: set[Future[None]] = set()
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as executor:
        while True:
            completed = {future for future in active if future.done()}
            for future in completed:
                future.result()
            active.difference_update(completed)
            while len(active) < MAX_CONCURRENT_JOBS:
                try:
                    with SessionLocal() as db:
                        source_id = _claim_next_job(db)
                except Exception:
                    logger.exception("Could not claim a curriculum PDF processing job.")
                    time.sleep(poll_seconds)
                    break
                if source_id is None:
                    break
                active.add(executor.submit(_process_book, source_id))
            if active:
                wait(active, timeout=poll_seconds, return_when=FIRST_COMPLETED)
            else:
                time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_worker()
