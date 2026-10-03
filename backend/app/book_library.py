from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePath
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserBook, UserBookChunk
from app.security import get_current_user

router = APIRouter(prefix="/api/study/books", tags=["study library"])
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 1000
MAX_EXTRACTED_CHARACTERS = 5_000_000
CHUNK_SIZE = 1600
CHUNK_OVERLAP = 200


class UserBookResponse(BaseModel):
    id: int
    title: str
    filename: str
    file_size: int
    page_count: int
    created_at: datetime

    @classmethod
    def from_book(cls, book: UserBook) -> "UserBookResponse":
        return cls(
            id=book.id,
            title=book.title,
            filename=book.filename,
            file_size=book.file_size,
            page_count=book.page_count,
            created_at=book.created_at or datetime.now(UTC),
        )


def extract_pdf_chunks(pdf_data: bytes) -> tuple[int, list[tuple[int, str]]]:
    if not pdf_data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")

    try:
        reader = PdfReader(BytesIO(pdf_data), strict=False)
        if reader.is_encrypted:
            raise HTTPException(status_code=422, detail="Password-protected PDFs are not supported.")
        page_count = len(reader.pages)
        if page_count == 0:
            raise HTTPException(status_code=422, detail="The PDF contains no pages.")
        if page_count > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=413,
                detail=f"PDFs may contain at most {MAX_PDF_PAGES} pages.",
            )

        chunks: list[tuple[int, str]] = []
        extracted_characters = 0
        for page_number, page in enumerate(reader.pages, start=1):
            text = " ".join((page.extract_text() or "").split())
            extracted_characters += len(text)
            if extracted_characters > MAX_EXTRACTED_CHARACTERS:
                raise HTTPException(
                    status_code=413,
                    detail="The extracted PDF text exceeds the supported size.",
                )
            start = 0
            while start < len(text):
                content = text[start : start + CHUNK_SIZE].strip()
                if content:
                    chunks.append((page_number, content))
                start += CHUNK_SIZE - CHUNK_OVERLAP
    except HTTPException:
        raise
    except (PdfReadError, OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail="The PDF could not be read.") from error

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No selectable text was found. Scanned PDFs need OCR before upload.",
        )
    return page_count, chunks


@router.post("", response_model=UserBookResponse, status_code=status.HTTP_201_CREATED)
async def upload_book(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=240),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserBookResponse:
    filename = PurePath(file.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    pdf_data = await file.read(MAX_PDF_BYTES + 1)
    if len(pdf_data) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDFs must be no larger than {MAX_PDF_BYTES // (1024 * 1024)} MB.",
        )

    page_count, chunks = extract_pdf_chunks(pdf_data)
    clean_title = (title or "").strip() or filename.removesuffix(".pdf").removesuffix(".PDF")
    if not clean_title:
        raise HTTPException(status_code=422, detail="A book title is required.")
    book = UserBook(
        owner_id=user.id,
        title=clean_title[:240],
        filename=filename[:255],
        content_type="application/pdf",
        file_size=len(pdf_data),
        page_count=page_count,
        pdf_data=pdf_data,
    )
    db.add(book)
    db.flush()
    db.add_all(
        [
            UserBookChunk(
                book_id=book.id,
                position=position,
                page_number=page_number,
                content=content,
            )
            for position, (page_number, content) in enumerate(chunks)
        ]
    )
    db.commit()
    db.refresh(book)
    return UserBookResponse.from_book(book)


@router.get("", response_model=list[UserBookResponse])
def list_books(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserBookResponse]:
    books = db.scalars(
        select(UserBook).where(UserBook.owner_id == user.id).order_by(UserBook.created_at.desc())
    ).all()
    return [UserBookResponse.from_book(book) for book in books]


@router.get("/{book_id}/file")
def download_book(
    book_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    book = db.scalar(
        select(UserBook).where(UserBook.id == book_id, UserBook.owner_id == user.id)
    )
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")
    return Response(
        content=book.pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(book.filename)}"},
    )


@router.delete("/{book_id}")
def delete_book(
    book_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    book = db.scalar(
        select(UserBook).where(UserBook.id == book_id, UserBook.owner_id == user.id)
    )
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found.")
    db.query(UserBookChunk).filter(UserBookChunk.book_id == book.id).delete(
        synchronize_session=False
    )
    db.delete(book)
    db.commit()
    return {"status": "deleted"}
