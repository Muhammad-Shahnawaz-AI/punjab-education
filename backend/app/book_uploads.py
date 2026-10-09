import logging
import math
import os
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.book_storage import (
    MAX_PARTS,
    PDF_PART_SIZE,
    BookStorage,
    LocalBookStorage,
    PartManifest,
    get_book_storage,
)
from app.database import get_db
from app.models import (
    Book,
    BookUploadSession,
    Curriculum,
    Grade,
    OfficialBookChunk,
    OfficialBookSource,
    Subject,
    User,
)
from app.security import require_admin

router = APIRouter(prefix="/api/admin/books", tags=["admin book uploads"])
logger = logging.getLogger(__name__)
DEFAULT_MAX_PDF_SIZE = 20 * 1024 * 1024 * 1024
MAX_ACTIVE_UPLOADS = int(os.getenv("MAX_CONCURRENT_UPLOADS", "3"))
MAX_SESSION_TTL = int(os.getenv("UPLOAD_SESSION_TTL_SECONDS", "86400"))
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ ()-]+")


class CreateUploadRequest(BaseModel):
    filename: str = Field(min_length=5, max_length=1024)
    content_type: str = Field(default="application/pdf", max_length=100)
    file_size: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    author: str | None = Field(default=None, max_length=200)
    grade_id: int
    subject_id: int
    source_name: str = Field(min_length=1, max_length=160)
    source_url: AnyHttpUrl
    rights_basis: str = Field(min_length=10, max_length=2000)
    rights_confirmed: bool
    language: str = Field(default="English", min_length=1, max_length=32)
    edition: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    use_ocr: bool = False
    ocr_language: str = Field(default="eng", pattern=r"^(eng|urd|eng\+urd)$")


class UploadSessionResponse(BaseModel):
    id: str
    status: str
    filename: str
    file_size: int
    part_size: int
    part_count: int
    uploaded_bytes: int
    uploaded_parts: dict[str, int]
    provider: str
    expires_at: datetime
    book_id: int | None = None


class AuthorizePartRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class RetryProcessingRequest(BaseModel):
    use_ocr: bool | None = None
    ocr_language: str | None = Field(default=None, pattern=r"^(eng|urd|eng\+urd)$")


class BookManagementItem(BaseModel):
    book_id: int
    title: str
    filename: str
    file_size: int
    grade: int
    subject: str
    curriculum: str
    author: str | None
    language: str
    edition: str | None
    description: str | None
    upload_date: datetime
    upload_status: str
    processing_status: str
    processing_stage: str
    processing_progress: int
    page_count: int
    ocr_used: bool
    last_error: str | None
    retry_count: int
    checksum_sha256: str | None


class UploadPolicy(BaseModel):
    max_size_bytes: int
    part_size_bytes: int
    max_concurrent_uploads: int
    provider: str


def _max_size() -> int:
    try:
        maximum = int(os.getenv("MAX_PDF_SIZE_BYTES", str(DEFAULT_MAX_PDF_SIZE)))
    except ValueError as error:
        raise HTTPException(
            status_code=503, detail="MAX_PDF_SIZE_BYTES must be an integer."
        ) from error
    if PDF_PART_SIZE < 1:
        raise HTTPException(status_code=503, detail="MULTIPART_CHUNK_SIZE_BYTES must be positive.")
    if maximum < 1 or math.ceil(maximum / PDF_PART_SIZE) > MAX_PARTS:
        raise HTTPException(
            status_code=503,
            detail=(
                "MAX_PDF_SIZE_BYTES must be positive and fit within the configured "
                "multipart limits."
            ),
        )
    return maximum


def _storage_backend() -> str:
    provider = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if provider not in ("local", "s3"):
        raise HTTPException(
            status_code=503, detail="STORAGE_BACKEND must be configured as local or s3."
        )
    if MAX_ACTIVE_UPLOADS < 1 or MAX_SESSION_TTL < 1:
        raise HTTPException(
            status_code=503,
            detail="Upload concurrency and session expiration settings must be positive.",
        )
    return provider


def _storage() -> BookStorage:
    try:
        return get_book_storage()
    except (RuntimeError, OSError) as error:
        logger.exception("Book storage configuration is unavailable")
        raise HTTPException(status_code=503, detail=str(error)) from error


def _clean_filename(filename: str) -> str:
    basename = PurePath(filename.replace("\\", "/")).name
    cleaned = SAFE_FILENAME.sub("_", basename).strip(" .")
    if not cleaned or not cleaned.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Choose a file with a .pdf extension.")
    return cleaned[:255]


def _session_or_404(db: Session, upload_id: str, user_id: int) -> BookUploadSession:
    session = db.get(BookUploadSession, upload_id)
    if session is None or session.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Upload session not found.")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC) and session.status not in ("completed", "cancelled"):
        session.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Upload session expired. Start a new upload.")
    return session


def _session_response(session: BookUploadSession, storage: BookStorage) -> UploadSessionResponse:
    count = math.ceil(session.expected_size / PDF_PART_SIZE)
    if session.status == "completed":
        parts = {
            str(number): _expected_part_size(session, number) for number in range(1, count + 1)
        }
    else:
        try:
            parts = storage.uploaded_part_sizes(
                session.storage_key, session.storage_upload_id, count
            )
        except Exception as error:
            logger.exception("Could not inspect parts for upload session %s", session.id)
            raise HTTPException(
                status_code=503, detail="Upload status is temporarily unavailable."
            ) from error
    uploaded_bytes = sum(parts.values())
    return UploadSessionResponse(
        id=session.id,
        status=session.status,
        filename=session.filename,
        file_size=session.expected_size,
        part_size=PDF_PART_SIZE,
        part_count=count,
        uploaded_bytes=uploaded_bytes,
        uploaded_parts=parts,
        provider=session.provider,
        expires_at=session.expires_at,
        book_id=session.book_id,
    )


def _expected_part_size(session: BookUploadSession, number: int) -> int:
    count = math.ceil(session.expected_size / PDF_PART_SIZE)
    if number < 1 or number > count:
        raise HTTPException(status_code=422, detail="Upload part number is out of range.")
    return min(PDF_PART_SIZE, session.expected_size - (number - 1) * PDF_PART_SIZE)


def _discard_completed_upload(
    db: Session, session: BookUploadSession, storage: BookStorage
) -> None:
    try:
        storage.delete(session.storage_key)
    except Exception as error:
        logger.exception("Could not discard completed upload session %s", session.id)
        raise HTTPException(
            status_code=503, detail="The rejected PDF could not be removed from storage."
        ) from error
    session.status = "failed"
    db.commit()


@router.post("/uploads", response_model=UploadSessionResponse, status_code=201)
def create_upload(
    request: CreateUploadRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UploadSessionResponse:
    filename = _clean_filename(request.filename)
    maximum = _max_size()
    if request.file_size > maximum:
        raise HTTPException(
            status_code=413,
            detail=f"The configured PDF size limit is {maximum} bytes.",
        )
    if request.content_type.lower().split(";", 1)[0].strip() not in (
        "application/pdf",
        "application/octet-stream",
    ):
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")
    if not request.rights_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Confirm that you have permission to store and process this book.",
        )
    source_url = str(request.source_url)
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or parsed_url.username or parsed_url.password:
        raise HTTPException(
            status_code=422, detail="The source URL must use HTTPS without credentials."
        )
    title = request.title.strip()
    source_name = request.source_name.strip()
    rights_basis = request.rights_basis.strip()
    language = request.language.strip()
    if not title or not source_name or not rights_basis or not language:
        raise HTTPException(status_code=422, detail="Required book metadata cannot be blank.")

    subject = db.get(Subject, request.subject_id)
    grade = db.get(Grade, request.grade_id)
    if subject is None or grade is None or subject.grade_id != grade.id:
        raise HTTPException(
            status_code=422, detail="Select a subject belonging to the chosen grade."
        )
    curriculum = db.get(Curriculum, grade.curriculum_id)
    if curriculum is None or curriculum.is_sample:
        raise HTTPException(status_code=422, detail="Select a real curriculum catalog.")
    existing_book = db.scalar(
        select(Book).where(Book.subject_id == subject.id, func.lower(Book.name) == title.casefold())
    )
    if existing_book is not None and db.scalar(
        select(OfficialBookSource.id).where(OfficialBookSource.book_id == existing_book.id)
    ):
        raise HTTPException(
            status_code=409, detail="This curriculum book already has a PDF source."
        )
    active_uploads = (
        db.scalar(
            select(func.count())
            .select_from(BookUploadSession)
            .where(
                BookUploadSession.owner_id == admin.id,
                BookUploadSession.status.in_(("initiated", "uploading")),
                BookUploadSession.expires_at > datetime.now(UTC),
            )
        )
        or 0
    )
    if active_uploads >= MAX_ACTIVE_UPLOADS:
        raise HTTPException(
            status_code=429,
            detail=f"At most {MAX_ACTIVE_UPLOADS} uploads may be active per administrator.",
        )
    provider = _storage_backend()
    storage = _storage()
    key = f"official-books/{uuid.uuid4().hex}.pdf"
    session_id = str(uuid.uuid4())
    try:
        provider_upload_id = storage.begin(key)
        if isinstance(storage, LocalBookStorage):
            root = storage.root
            reserved = (
                db.scalar(
                    select(func.coalesce(func.sum(BookUploadSession.expected_size), 0)).where(
                        BookUploadSession.status.in_(("initiated", "uploading")),
                        BookUploadSession.expires_at > datetime.now(UTC),
                    )
                )
                or 0
            )
            free_bytes = shutil.disk_usage(root).free
            if free_bytes < (reserved + request.file_size) * 2:
                storage.delete(key, provider_upload_id)
                raise HTTPException(
                    status_code=507,
                    detail="Local storage lacks space for the upload and its temporary assembly.",
                )
        session = BookUploadSession(
            id=session_id,
            owner_id=admin.id,
            storage_key=key,
            storage_upload_id=provider_upload_id,
            provider=provider,
            status="initiated",
            filename=filename,
            expected_size=request.file_size,
            metadata_json={
                **request.model_dump(mode="json"),
                "filename": filename,
                "title": title,
                "source_name": source_name,
                "source_url": source_url,
                "rights_basis": rights_basis,
                "language": language,
            },
            uploaded_parts={},
            expires_at=datetime.now(UTC) + timedelta(seconds=min(MAX_SESSION_TTL, 7 * 86400)),
        )
        db.add(session)
        db.commit()
    except HTTPException:
        raise
    except Exception as error:
        db.rollback()
        logger.exception("Could not create a book upload session")
        raise HTTPException(status_code=503, detail="Could not initialize book storage.") from error
    return _session_response(session, storage)


@router.get("/upload-policy", response_model=UploadPolicy)
def upload_policy(
    _admin: User = Depends(require_admin),
) -> UploadPolicy:
    _storage()
    return UploadPolicy(
        max_size_bytes=_max_size(),
        part_size_bytes=PDF_PART_SIZE,
        max_concurrent_uploads=MAX_ACTIVE_UPLOADS,
        provider=_storage_backend(),
    )


@router.get("/uploads/{upload_id}", response_model=UploadSessionResponse)
def get_upload(
    upload_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UploadSessionResponse:
    session = _session_or_404(db, upload_id, admin.id)
    return _session_response(session, _storage())


@router.post("/uploads/{upload_id}/parts/{part_number}/authorize")
def authorize_part(
    upload_id: str,
    part_number: int,
    request: AuthorizePartRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    session = _session_or_404(db, upload_id, admin.id)
    if session.status not in ("initiated", "uploading"):
        raise HTTPException(status_code=409, detail="This upload session is not accepting parts.")
    expected_size = _expected_part_size(session, part_number)
    storage = _storage()
    checksum = request.sha256.lower()
    parts = dict(session.uploaded_parts or {})
    parts[str(part_number)] = {"size": expected_size, "sha256": checksum}
    session.uploaded_parts = parts
    if session.provider == "local":
        db.commit()
        return {
            "url": f"/api/admin/books/uploads/{session.id}/parts/{part_number}",
            "method": "PUT",
            "size": expected_size,
            "provider": "local",
        }
    try:
        url = storage.authorize_part(
            session.storage_key,
            session.storage_upload_id,
            part_number,
            expected_size,
            checksum,
        )
        db.commit()
    except Exception as error:
        logger.exception("Could not authorize S3 part for upload %s", session.id)
        raise HTTPException(
            status_code=503, detail="Could not authorize this upload part."
        ) from error
    return {"url": url or "", "method": "PUT", "size": expected_size, "provider": "s3"}


@router.put("/uploads/{upload_id}/parts/{part_number}", status_code=204)
async def upload_local_part(
    upload_id: str,
    part_number: int,
    request: Request,
    part_sha256: str | None = Header(default=None, alias="X-Part-SHA256"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    session = _session_or_404(db, upload_id, admin.id)
    if session.provider != "local":
        raise HTTPException(
            status_code=405, detail="Upload this part using its authorized storage URL."
        )
    if session.status not in ("initiated", "uploading"):
        raise HTTPException(status_code=409, detail="This upload session is not accepting parts.")
    expected_size = _expected_part_size(session, part_number)
    if part_sha256 is None or re.fullmatch(r"[a-fA-F0-9]{64}", part_sha256) is None:
        raise HTTPException(status_code=400, detail="X-Part-SHA256 must contain a SHA-256 digest.")
    manifest_entry = (session.uploaded_parts or {}).get(str(part_number))
    if manifest_entry is None or str(manifest_entry["sha256"]).lower() != part_sha256.lower():
        raise HTTPException(status_code=409, detail="Part checksum differs from its authorization.")
    content_length = request.headers.get("content-length")
    if (
        content_length is None
        or not content_length.isdigit()
        or int(content_length) != expected_size
    ):
        raise HTTPException(status_code=400, detail="Upload part Content-Length is incorrect.")
    try:
        digest = await _storage().store_local_part(
            session.storage_key,
            part_number,
            expected_size,
            part_sha256.lower(),
            request.stream(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Could not store part %s for upload %s", part_number, session.id)
        raise HTTPException(status_code=507, detail="Could not persist the upload part.") from error
    if digest != part_sha256.lower():
        raise HTTPException(status_code=400, detail="Upload part checksum did not match.")
    session.status = "uploading"
    db.commit()
    return Response(status_code=204)


@router.post("/uploads/{upload_id}/complete", response_model=UploadSessionResponse)
def complete_upload(
    upload_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UploadSessionResponse:
    session = _session_or_404(db, upload_id, admin.id)
    if session.status == "completed":
        return _session_response(session, _storage())
    if session.status not in ("initiated", "uploading"):
        raise HTTPException(status_code=409, detail="This upload session cannot be completed.")
    count = math.ceil(session.expected_size / PDF_PART_SIZE)
    storage = _storage()
    try:
        sizes = storage.uploaded_part_sizes(session.storage_key, session.storage_upload_id, count)
        expected_parts: PartManifest = {
            str(number): (session.uploaded_parts or {}).get(str(number), {})
            for number in range(1, count + 1)
        }
        expected_sizes = {
            number: int(part["size"])
            for number, part in expected_parts.items()
            if "size" in part and "sha256" in part
        }
        if (
            sizes
            != {str(number): _expected_part_size(session, number) for number in range(1, count + 1)}
            or len(expected_sizes) != count
            or expected_sizes
            != {str(number): _expected_part_size(session, number) for number in range(1, count + 1)}
        ):
            raise HTTPException(
                status_code=409, detail="One or more upload parts are missing or incomplete."
            )
        actual_size, digest = storage.complete(
            session.storage_key,
            session.storage_upload_id,
            expected_parts,
            session.expected_size,
        )
        with storage.open(session.storage_key) as pdf:
            if pdf.read(5) != b"%PDF-":
                _discard_completed_upload(db, session, storage)
                raise HTTPException(
                    status_code=415, detail="The uploaded file does not have a PDF signature."
                )
        if actual_size != session.expected_size:
            _discard_completed_upload(db, session, storage)
            raise HTTPException(
                status_code=400, detail="Uploaded file size does not match the session."
            )
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Could not complete upload session %s", session.id)
        raise HTTPException(
            status_code=503, detail="Could not verify the completed PDF upload."
        ) from error

    metadata = session.metadata_json
    grade = db.get(Grade, int(metadata["grade_id"]))
    subject = db.get(Subject, int(metadata["subject_id"]))
    if grade is None or subject is None or subject.grade_id != grade.id:
        _discard_completed_upload(db, session, storage)
        raise HTTPException(
            status_code=409, detail="The selected curriculum metadata is no longer valid."
        )
    book_name = str(metadata["title"]).strip()
    book = db.scalar(
        select(Book).where(
            Book.subject_id == subject.id, func.lower(Book.name) == book_name.casefold()
        )
    )
    if book is None:
        book = Book(subject_id=subject.id, name=book_name)
        db.add(book)
        db.flush()
    existing_source = db.scalar(
        select(OfficialBookSource).where(OfficialBookSource.book_id == book.id)
    )
    if existing_source is not None:
        _discard_completed_upload(db, session, storage)
        raise HTTPException(
            status_code=409, detail="This curriculum book already has a PDF source."
        )
    source = OfficialBookSource(
        book_id=book.id,
        source_name=str(metadata["source_name"]),
        source_url=str(metadata["source_url"]),
        rights_basis=str(metadata["rights_basis"]),
        rights_verified_by_id=admin.id,
        filename=session.filename,
        file_size=actual_size,
        page_count=0,
        pdf_data=None,
        ocr_used=False,
        storage_key=session.storage_key,
        checksum_sha256=digest,
        author=metadata.get("author"),
        language=str(metadata.get("language", "English")),
        edition=metadata.get("edition"),
        description=metadata.get("description"),
        processing_status="queued",
        processing_stage="queued",
        processing_progress=0,
        processed_page_count=0,
        processing_lease_until=None,
        pipeline_version="v1",
    )
    db.add(source)
    session.status = "completed"
    session.checksum_sha256 = digest
    session.book_id = book.id
    session.completed_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        try:
            storage.delete(session.storage_key)
            failed_session = db.get(BookUploadSession, upload_id)
            if failed_session is not None:
                failed_session.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not clean up a duplicate book upload %s", upload_id)
        raise HTTPException(
            status_code=409,
            detail="Another administrator already uploaded a source for this curriculum book.",
        ) from error
    except Exception as error:
        db.rollback()
        try:
            storage.delete(session.storage_key)
            failed_session = db.get(BookUploadSession, upload_id)
            if failed_session is not None:
                failed_session.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not clean up failed book upload %s", upload_id)
        logger.exception("Could not persist completed book upload %s", upload_id)
        raise HTTPException(
            status_code=503, detail="The completed PDF could not be registered in the catalog."
        ) from error
    db.refresh(session)
    return _session_response(session, storage)


@router.get("", response_model=list[BookManagementItem])
def list_uploaded_books(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[BookManagementItem]:
    rows = db.execute(
        select(OfficialBookSource, Book, Subject, Grade, Curriculum)
        .join(Book, Book.id == OfficialBookSource.book_id)
        .join(Subject, Subject.id == Book.subject_id)
        .join(Grade, Grade.id == Subject.grade_id)
        .join(Curriculum, Curriculum.id == Grade.curriculum_id)
        .where(OfficialBookSource.storage_key.is_not(None))
        .order_by(OfficialBookSource.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        BookManagementItem(
            book_id=book.id,
            title=book.name,
            filename=source.filename,
            file_size=source.file_size,
            grade=grade.level,
            subject=subject.name,
            curriculum=curriculum.name,
            author=source.author,
            language=source.language,
            edition=source.edition,
            description=source.description,
            upload_date=source.created_at,
            upload_status="completed",
            processing_status=source.processing_status,
            processing_stage=source.processing_stage,
            processing_progress=source.processing_progress,
            page_count=source.page_count,
            ocr_used=source.ocr_used,
            last_error=source.last_error,
            retry_count=source.retry_count,
            checksum_sha256=source.checksum_sha256,
        )
        for source, book, subject, grade, curriculum in rows
    ]


@router.get("/{book_id}", response_model=BookManagementItem)
def get_uploaded_book(
    book_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BookManagementItem:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")
    source = db.scalar(
        select(OfficialBookSource).where(
            OfficialBookSource.book_id == book_id,
            OfficialBookSource.storage_key.is_not(None),
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Uploaded PDF not found.")
    subject = db.get(Subject, book.subject_id)
    grade = db.get(Grade, subject.grade_id) if subject else None
    curriculum = db.get(Curriculum, grade.curriculum_id) if grade else None
    if subject is None or grade is None or curriculum is None:
        raise HTTPException(status_code=409, detail="Book curriculum metadata is unavailable.")
    return BookManagementItem(
        book_id=book.id,
        title=book.name,
        filename=source.filename,
        file_size=source.file_size,
        grade=grade.level,
        subject=subject.name,
        curriculum=curriculum.name,
        author=source.author,
        language=source.language,
        edition=source.edition,
        description=source.description,
        upload_date=source.created_at,
        upload_status="completed",
        processing_status=source.processing_status,
        processing_stage=source.processing_stage,
        processing_progress=source.processing_progress,
        page_count=source.page_count,
        ocr_used=source.ocr_used,
        last_error=source.last_error,
        retry_count=source.retry_count,
        checksum_sha256=source.checksum_sha256,
    )


@router.post("/{book_id}/retry", response_model=BookManagementItem)
def retry_processing(
    book_id: int,
    request: RetryProcessingRequest | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BookManagementItem:
    source = db.scalar(
        select(OfficialBookSource).where(
            OfficialBookSource.book_id == book_id,
            OfficialBookSource.storage_key.is_not(None),
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Uploaded PDF not found.")
    if source.processing_status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="This book is already queued or processing.")
    source.processing_status = "queued"
    source.processing_stage = "queued"
    source.processing_progress = 0
    source.processed_page_count = 0
    source.last_error = None
    source.retry_count += 1
    source.processing_lease_until = None
    upload_session = db.scalar(
        select(BookUploadSession)
        .where(BookUploadSession.book_id == book_id)
        .order_by(BookUploadSession.created_at.desc())
    )
    if upload_session is not None and request is not None:
        metadata = dict(upload_session.metadata_json or {})
        if request.use_ocr is not None:
            metadata["use_ocr"] = request.use_ocr
        if request.ocr_language is not None:
            metadata["ocr_language"] = request.ocr_language
        upload_session.metadata_json = metadata
    db.query(OfficialBookChunk).filter(OfficialBookChunk.source_id == source.id).delete(
        synchronize_session=False
    )
    db.commit()
    return get_uploaded_book(book_id, admin, db)


@router.delete("/{book_id}", status_code=204)
def delete_uploaded_book(
    book_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    source = db.scalar(
        select(OfficialBookSource).where(
            OfficialBookSource.book_id == book_id,
            OfficialBookSource.storage_key.is_not(None),
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Uploaded PDF not found.")
    storage = _storage()
    try:
        storage.delete(source.storage_key or "")
    except Exception as error:
        logger.exception("Could not delete stored PDF for book %s", book_id)
        raise HTTPException(
            status_code=503, detail="The PDF could not be deleted from storage."
        ) from error
    db.delete(source)
    db.commit()
    return Response(status_code=204)


@router.delete("/uploads/{upload_id}", status_code=204)
def cancel_upload(
    upload_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    session = _session_or_404(db, upload_id, admin.id)
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="A completed upload cannot be cancelled.")
    try:
        _storage().delete(session.storage_key, session.storage_upload_id)
    except Exception as error:
        logger.exception("Could not cancel upload session %s", session.id)
        raise HTTPException(
            status_code=503, detail="Upload cleanup failed; retry cancellation."
        ) from error
    session.status = "cancelled"
    db.commit()
    return Response(status_code=204)
