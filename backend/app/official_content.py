import json
import re
from collections.abc import Sequence
from io import BytesIO
from pathlib import PurePath
from typing import Literal
from urllib.parse import urlparse

from app.database import get_db
from app.models import (
    Book,
    Chapter,
    Curriculum,
    Grade,
    OfficialBookChunk,
    OfficialBookSource,
    Subject,
    Topic,
    User,
)
from app.security import get_current_user, require_admin
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/curriculum", tags=["official curriculum"])
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 1000
MAX_EXTRACTED_CHARACTERS = 5_000_000
CHUNK_SIZE = 1600
CHUNK_OVERLAP = 200
CHAPTER_HEADING = re.compile(
    r"^\s*(?:chapter|unit|باب)\s+[\d۰-۹٠-٩]+[\s:.\-–—]+(.{2,200})\s*$",
    re.IGNORECASE,
)
TOPIC_HEADING = re.compile(r"^\s*\d+(?:\.\d+)+\s+(.{2,200})\s*$")


class ChapterOutline(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_page: int = Field(default=1, ge=1, le=MAX_PDF_PAGES)
    topics: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("topics", mode="before")
    @classmethod
    def normalize_topics(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized = [
            topic.strip() if isinstance(topic, str) else topic
            for topic in value
        ]
        if any(not isinstance(topic, str) or not topic for topic in normalized):
            raise ValueError("Topic names must not be empty.")
        if any(len(topic) > 240 for topic in normalized):
            raise ValueError("Topic names must be at most 240 characters.")
        if len({topic.casefold() for topic in normalized}) != len(normalized):
            raise ValueError("Topic names must be unique within a chapter.")
        return normalized


class BookSearchResult(BaseModel):
    book_id: int
    book: str
    curriculum: str
    grade: int
    subject: str
    chapter: str | None
    topic: str | None
    page_number: int
    excerpt: str
    source_name: str
    source_url: str
    rights_basis: str


def _extract_pages(
    pdf_data: bytes,
    use_ocr: bool,
    ocr_language: Literal["eng", "urd", "eng+urd"] = "eng",
) -> tuple[list[str], bool]:
    if not pdf_data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(pdf_data), strict=False)
        if reader.is_encrypted:
            raise HTTPException(
                status_code=422, detail="Password-protected PDFs are not supported."
            )
        page_count = len(reader.pages)
        if page_count == 0:
            raise HTTPException(status_code=422, detail="The PDF contains no pages.")
        if page_count > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=413, detail=f"PDFs may contain at most {MAX_PDF_PAGES} pages."
            )
        pages = [
            "\n".join(
                line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()
            )
            for page in reader.pages
        ]
    except HTTPException:
        raise
    except (PdfReadError, OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail="The PDF could not be read.") from error

    ocr_used = False
    if use_ocr and any(not page for page in pages):
        try:
            import pypdfium2
            import pytesseract
        except ImportError as error:
            raise HTTPException(
                status_code=503,
                detail="OCR support is unavailable. Install pypdfium2 and pytesseract.",
            ) from error

        try:
            document = pypdfium2.PdfDocument(pdf_data)
            try:
                for index, page_text in enumerate(pages):
                    if page_text:
                        continue
                    bitmap = document[index].render(scale=1.5)
                    pages[index] = "\n".join(
                        line.strip()
                        for line in pytesseract.image_to_string(
                            bitmap.to_pil(), lang=ocr_language
                        ).splitlines()
                        if line.strip()
                    )
                    ocr_used = True
            finally:
                document.close()
        except (OSError, RuntimeError) as error:
            raise HTTPException(
                status_code=503,
                detail="OCR could not run. Verify the Tesseract OCR executable is installed.",
            ) from error

    if sum(map(len, pages)) > MAX_EXTRACTED_CHARACTERS:
        raise HTTPException(
            status_code=413, detail="The extracted PDF text exceeds the supported size."
        )
    if not any(pages):
        raise HTTPException(
            status_code=422,
            detail="No selectable text was found. Enable OCR for scanned PDFs.",
        )
    return pages, ocr_used


def _outline_from_pages(pages: Sequence[str]) -> list[ChapterOutline]:
    outlines: list[ChapterOutline] = []
    for page_number, text in enumerate(pages, start=1):
        for line in text.splitlines():
            chapter_match = CHAPTER_HEADING.match(line)
            if chapter_match:
                outlines.append(
                    ChapterOutline(name=chapter_match.group(1).strip(), start_page=page_number)
                )
                continue
            topic_match = TOPIC_HEADING.match(line)
            if topic_match and outlines:
                topic = topic_match.group(1).strip()
                if topic not in outlines[-1].topics:
                    outlines[-1].topics.append(topic)
    return outlines


def _split_page(text: str) -> list[str]:
    normalized = " ".join(text.split())
    return [
        normalized[start : start + CHUNK_SIZE].strip()
        for start in range(0, len(normalized), CHUNK_SIZE - CHUNK_OVERLAP)
        if normalized[start : start + CHUNK_SIZE].strip()
    ]


def _upsert_catalog(
    db: Session,
    curriculum_code: str,
    curriculum_name: str,
    grade_level: int,
    subject_name: str,
    book_name: str,
) -> Book:
    curriculum = db.scalar(select(Curriculum).where(Curriculum.code == curriculum_code))
    if curriculum is None:
        curriculum = Curriculum(
            code=curriculum_code,
            name=curriculum_name,
            description="Verified Punjab Board curriculum material.",
            is_sample=False,
        )
        db.add(curriculum)
        db.flush()
    elif curriculum.is_sample:
        curriculum.is_sample = False
        curriculum.name = curriculum_name

    grade = db.scalar(
        select(Grade).where(
            Grade.curriculum_id == curriculum.id,
            Grade.level == grade_level,
        )
    )
    if grade is None:
        grade = Grade(curriculum_id=curriculum.id, level=grade_level)
        db.add(grade)
        db.flush()

    subject = db.scalar(
        select(Subject).where(Subject.grade_id == grade.id, Subject.name == subject_name)
    )
    if subject is None:
        subject = Subject(grade_id=grade.id, name=subject_name)
        db.add(subject)
        db.flush()

    book = db.scalar(select(Book).where(Book.subject_id == subject.id, Book.name == book_name))
    if book is None:
        book = Book(subject_id=subject.id, name=book_name)
        db.add(book)
        db.flush()
    return book


@router.post("/books/import", status_code=status.HTTP_201_CREATED)
async def import_official_book(
    curriculum_name: str = Form(min_length=1, max_length=160),
    curriculum_code: str = Form(default="punjab-board", min_length=1, max_length=80),
    grade_level: int = Form(ge=1, le=12),
    subject_name: str = Form(min_length=1, max_length=160),
    book_name: str = Form(min_length=1, max_length=200),
    source_name: str = Form(min_length=1, max_length=160),
    source_url: HttpUrl = Form(),
    rights_basis: str = Form(min_length=10, max_length=2000),
    rights_confirmed: bool = Form(),
    outline: str | None = Form(default=None, max_length=30_000),
    use_ocr: bool = Form(default=False),
    ocr_language: Literal["eng", "urd", "eng+urd"] = Form(default="eng"),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Import a rights-reviewed PDF; this endpoint does not download third-party URLs."""
    if not rights_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Confirm that you have permission to store and process this textbook.",
        )
    curriculum_name = curriculum_name.strip()
    curriculum_code = curriculum_code.strip()
    subject_name = subject_name.strip()
    book_name = book_name.strip()
    source_name = source_name.strip()
    rights_basis = rights_basis.strip()
    if not all(
        (curriculum_name, curriculum_code, subject_name, book_name, source_name, rights_basis)
    ):
        raise HTTPException(
            status_code=422,
            detail="Curriculum, grade, subject, book, source, and rights metadata are required.",
        )
    parsed_url = urlparse(str(source_url))
    if parsed_url.scheme != "https" or parsed_url.username or parsed_url.password:
        raise HTTPException(
            status_code=422,
            detail="The source URL must use HTTPS and must not contain credentials.",
        )
    filename = PurePath(file.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    pdf_data = await file.read(MAX_PDF_BYTES + 1)
    if len(pdf_data) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413, detail="Official textbook PDFs must be 50 MB or smaller."
        )

    pages, ocr_used = _extract_pages(pdf_data, use_ocr, ocr_language)
    if outline:
        try:
            raw_outline = json.loads(outline)
            if not isinstance(raw_outline, list):
                raise ValueError("Outline must be a JSON array.")
            chapters = [ChapterOutline.model_validate(item) for item in raw_outline]
        except (json.JSONDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Outline must be a JSON array of chapters with name, start_page, "
                    "and optional topics."
                ),
            ) from error
    else:
        chapters = _outline_from_pages(pages)
    if not chapters:
        raise HTTPException(
            status_code=422,
            detail="No chapter headings were detected. Supply a reviewed chapter outline as JSON.",
        )
    if any(chapter.start_page > len(pages) for chapter in chapters):
        raise HTTPException(
            status_code=422, detail="A chapter start page exceeds the PDF page count."
        )
    if sorted(chapter.start_page for chapter in chapters) != [
        chapter.start_page for chapter in chapters
    ]:
        raise HTTPException(
            status_code=422, detail="Chapter outline entries must be ordered by page."
        )
    if len({chapter.name.casefold() for chapter in chapters}) != len(chapters):
        raise HTTPException(
            status_code=422, detail="Chapter names must be unique within the outline."
        )

    book = _upsert_catalog(
        db,
        curriculum_code,
        curriculum_name,
        grade_level,
        subject_name,
        book_name,
    )
    if db.scalar(select(OfficialBookSource.id).where(OfficialBookSource.book_id == book.id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This book already has an imported official source.",
        )
    source = OfficialBookSource(
        book_id=book.id,
        source_name=source_name,
        source_url=str(source_url),
        rights_basis=rights_basis,
        rights_verified_by_id=admin.id,
        filename=filename[:255],
        file_size=len(pdf_data),
        page_count=len(pages),
        pdf_data=pdf_data,
        ocr_used=ocr_used,
    )
    db.add(source)
    db.flush()

    db_chapters: list[tuple[ChapterOutline, Chapter, list[tuple[str, Topic]]]] = []
    next_position = (
        db.scalar(
            select(func.coalesce(func.max(Chapter.position), 0)).where(Chapter.book_id == book.id)
        )
        or 0
    )
    for index, outline_chapter in enumerate(chapters, start=1):
        chapter = db.scalar(
            select(Chapter).where(
                Chapter.book_id == book.id,
                Chapter.name == outline_chapter.name.strip(),
            )
        )
        if chapter is None:
            next_position += 1
            chapter = Chapter(
                book_id=book.id,
                name=outline_chapter.name.strip(),
                position=next_position,
            )
            db.add(chapter)
            db.flush()
        topics: list[tuple[str, Topic]] = []
        for topic_name in outline_chapter.topics:
            clean_topic = topic_name.strip()
            if not clean_topic:
                continue
            topic = db.scalar(
                select(Topic).where(Topic.chapter_id == chapter.id, Topic.name == clean_topic)
            )
            if topic is None:
                topic = Topic(chapter_id=chapter.id, name=clean_topic)
                db.add(topic)
                db.flush()
            topics.append((clean_topic, topic))
        db_chapters.append((outline_chapter, chapter, topics))

    position = 0
    for page_number, page_text in enumerate(pages, start=1):
        active = next(
            (item for item in reversed(db_chapters) if item[0].start_page <= page_number),
            None,
        )
        for content in _split_page(page_text):
            matched_topic = None
            chapter_id = active[1].id if active else None
            if active:
                normalized = content.casefold()
                matched_topic = next(
                    (topic for name, topic in active[2] if name.casefold() in normalized), None
                )
            db.add(
                OfficialBookChunk(
                    source_id=source.id,
                    chapter_id=chapter_id,
                    topic_id=matched_topic.id if matched_topic else None,
                    position=position,
                    page_number=page_number,
                    content=content,
                )
            )
            position += 1
    db.commit()
    return {
        "status": "imported",
        "book_id": book.id,
        "book": book.name,
        "grade": grade_level,
        "subject": subject_name,
        "chapters": len(db_chapters),
        "indexed_chunks": position,
        "page_count": len(pages),
        "ocr_used": ocr_used,
        "rights_basis": rights_basis,
        "source_url": str(source_url),
    }


@router.get("/search", response_model=list[BookSearchResult])
def search_official_content(
    q: str = Query(min_length=2, max_length=200),
    grade: int | None = Query(default=None, ge=1, le=12),
    subject: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BookSearchResult]:
    escaped_query = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped_query}%"
    stmt = (
        select(
            OfficialBookChunk, OfficialBookSource, Book, Subject, Grade, Curriculum, Chapter, Topic
        )
        .join(OfficialBookSource, OfficialBookSource.id == OfficialBookChunk.source_id)
        .join(Book, Book.id == OfficialBookSource.book_id)
        .join(Subject, Subject.id == Book.subject_id)
        .join(Grade, Grade.id == Subject.grade_id)
        .join(Curriculum, Curriculum.id == Grade.curriculum_id)
        .outerjoin(Chapter, Chapter.id == OfficialBookChunk.chapter_id)
        .outerjoin(Topic, Topic.id == OfficialBookChunk.topic_id)
        .where(OfficialBookChunk.content.ilike(pattern, escape="\\"))
        .order_by(OfficialBookChunk.page_number)
        .limit(limit)
    )
    if grade is not None:
        stmt = stmt.where(Grade.level == grade)
    if subject:
        stmt = stmt.where(Subject.name.ilike(subject.strip()))
    rows = db.execute(stmt).all()
    return [
        BookSearchResult(
            book_id=book.id,
            book=book.name,
            curriculum=curriculum.name,
            grade=grade_record.level,
            subject=subject_record.name,
            chapter=chapter.name if chapter else None,
            topic=topic.name if topic else None,
            page_number=chunk.page_number,
            excerpt=chunk.content,
            source_name=source.source_name,
            source_url=source.source_url,
            rights_basis=source.rights_basis,
        )
        for chunk, source, book, subject_record, grade_record, curriculum, chapter, topic in rows
    ]
