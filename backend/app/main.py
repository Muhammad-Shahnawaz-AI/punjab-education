import os
import re
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai_service import generate_ai_bundle, persist_generation_log
from app.auth import router as auth_router
from app.book_library import router as book_library_router
from app.book_uploads import router as book_uploads_router
from app.curriculum import router as curriculum_router
from app.database import get_db
from app.models import (
    AIGenerationLog,
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
from app.official_content import router as official_content_router
from app.security import get_optional_user, require_teacher
from app.study_chat import router as study_chat_router

app = FastAPI(title="Punjab Education Intelligence Platform API", version="0.1.0")
app.include_router(auth_router)
app.include_router(curriculum_router)
app.include_router(book_library_router)
app.include_router(book_uploads_router)
app.include_router(study_chat_router)
app.include_router(official_content_router)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CurriculumName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
SubjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
BookName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
ChapterName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
TopicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class GenerateRequest(BaseModel):
    curriculum: CurriculumName
    subject: SubjectName
    book: BookName
    chapter: ChapterName
    topic: TopicName
    question_type: Literal["mcq", "subjective", "quiz", "assignment"]
    count: int = Field(default=10, ge=1, le=50)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    language: Literal["en", "ur"] = "en"
    grade: str | None = Field(default=None, max_length=50)
    learning_objectives: str | None = Field(default=None, max_length=500)


class AIHistoryItem(BaseModel):
    id: int
    question_type: str
    subject: str
    chapter: str
    topic: str
    difficulty: str
    language: str
    status: str
    created_at: str


class DashboardSubject(BaseModel):
    name: str
    books: int
    chapters: int
    topics: int


class DashboardGeneration(BaseModel):
    subject: str
    chapter: str
    topic: str
    created_at: str


class DashboardOverview(BaseModel):
    curricula: int
    grades: int
    subjects: int
    books: int
    approved_books: int
    chapters: int
    topics: int
    subject_catalog: list[DashboardSubject]
    recent_generations: list[DashboardGeneration]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard/overview", response_model=DashboardOverview)
def dashboard_overview(
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> DashboardOverview:
    real_curricula = Curriculum.is_sample.is_(False)
    curriculum_ids = select(Curriculum.id).where(real_curricula)
    grade_ids = select(Grade.id).where(Grade.curriculum_id.in_(curriculum_ids))
    subject_ids = select(Subject.id).where(Subject.grade_id.in_(grade_ids))
    book_ids = select(Book.id).where(Book.subject_id.in_(subject_ids))
    chapter_ids = select(Chapter.id).where(Chapter.book_id.in_(book_ids))

    curriculum_count = (
        db.scalar(select(func.count()).select_from(Curriculum).where(real_curricula)) or 0
    )
    grade_count = (
        db.scalar(select(func.count()).select_from(Grade).where(Grade.id.in_(grade_ids))) or 0
    )
    subject_count = (
        db.scalar(select(func.count()).select_from(Subject).where(Subject.id.in_(subject_ids))) or 0
    )
    book_count = db.scalar(select(func.count()).select_from(Book).where(Book.id.in_(book_ids))) or 0
    approved_book_count = (
        db.scalar(
            select(func.count())
            .select_from(OfficialBookSource)
            .where(
                OfficialBookSource.book_id.in_(book_ids),
                OfficialBookSource.processing_status == "ready",
            )
        )
        or 0
    )
    chapter_count = (
        db.scalar(select(func.count()).select_from(Chapter).where(Chapter.id.in_(chapter_ids))) or 0
    )
    topic_count = (
        db.scalar(select(func.count()).select_from(Topic).where(Topic.chapter_id.in_(chapter_ids)))
        or 0
    )

    subject_rows = db.execute(
        select(
            Subject.name,
            func.count(func.distinct(Book.id)),
            func.count(func.distinct(Chapter.id)),
            func.count(func.distinct(Topic.id)),
        )
        .join(Grade, Grade.id == Subject.grade_id)
        .join(Curriculum, Curriculum.id == Grade.curriculum_id)
        .outerjoin(Book, Book.subject_id == Subject.id)
        .outerjoin(Chapter, Chapter.book_id == Book.id)
        .outerjoin(Topic, Topic.chapter_id == Chapter.id)
        .where(Curriculum.is_sample.is_(False))
        .group_by(Subject.name)
        .order_by(Subject.name)
        .limit(8)
    ).all()

    generation_query = select(AIGenerationLog).order_by(AIGenerationLog.created_at.desc())
    if user is None or user.role == "student":
        recent_generations = []
    else:
        logs = db.scalars(
            generation_query.where(AIGenerationLog.created_by_id == user.id).limit(5)
        ).all()
        recent_generations = [
            DashboardGeneration(
                subject=log.subject,
                chapter=log.chapter,
                topic=log.topic,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ]

    return DashboardOverview(
        curricula=curriculum_count,
        grades=grade_count,
        subjects=subject_count,
        books=book_count,
        approved_books=approved_book_count,
        chapters=chapter_count,
        topics=topic_count,
        subject_catalog=[
            DashboardSubject(
                name=name,
                books=books,
                chapters=chapters,
                topics=topics,
            )
            for name, books, chapters, topics in subject_rows
        ],
        recent_generations=recent_generations,
    )


@app.post("/api/ai/generate")
def generate(
    req: GenerateRequest,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    request_data = req.model_dump()
    filters = [
        func.lower(Book.name) == req.book.casefold(),
        func.lower(Subject.name) == req.subject.casefold(),
        func.lower(Curriculum.name) == req.curriculum.casefold(),
    ]
    grade_match = re.search(r"\d+", req.grade or "")
    if grade_match:
        filters.append(Grade.level == int(grade_match.group()))
    matching_books = db.scalars(
        select(Book)
        .join(Subject, Subject.id == Book.subject_id)
        .join(Grade, Grade.id == Subject.grade_id)
        .join(Curriculum, Curriculum.id == Grade.curriculum_id)
        .where(*filters)
        .limit(2)
    ).all()
    if not matching_books:
        raise HTTPException(
            status_code=422,
            detail="Question generation requires a book in the approved curriculum catalog.",
        )
    if len(matching_books) > 1:
        raise HTTPException(
            status_code=422,
            detail="Specify the grade to select the correct approved textbook.",
        )
    matching_book = matching_books[0]
    source = db.scalar(
        select(OfficialBookSource).where(
            OfficialBookSource.book_id == matching_book.id,
            OfficialBookSource.processing_status == "ready",
        )
    )
    if source is None:
        raise HTTPException(
            status_code=422,
            detail="The selected book has no successfully processed textbook PDF yet.",
        )
    chapter = db.scalar(
        select(Chapter).where(
            Chapter.book_id == matching_book.id,
            func.lower(Chapter.name) == req.chapter.casefold(),
        )
    )
    if chapter is None:
        raise HTTPException(
            status_code=422,
            detail=f"Chapter '{req.chapter}' was not found in the selected approved book.",
        )
    topic = db.scalar(
        select(Topic).where(
            Topic.chapter_id == chapter.id,
            func.lower(Topic.name) == req.topic.casefold(),
        )
    )
    if topic is None:
        raise HTTPException(
            status_code=422,
            detail=f"Topic '{req.topic}' was not mapped to the selected approved chapter.",
        )
    chunks = db.scalars(
        select(OfficialBookChunk)
        .where(
            OfficialBookChunk.source_id == source.id,
            OfficialBookChunk.chapter_id == chapter.id,
            or_(
                OfficialBookChunk.topic_id == topic.id,
                OfficialBookChunk.content.ilike(f"%{req.topic}%"),
            ),
        )
        .order_by(OfficialBookChunk.page_number)
        .limit(5)
    ).all()
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No indexed textbook excerpts were found for the selected topic.",
        )
    source_excerpts: list[dict[str, object]] = [
        {
            "book": matching_book.name,
            "chapter": chapter.name,
            "page": chunk.page_number,
            "text": chunk.content,
            "source_name": source.source_name,
            "source_url": source.source_url,
        }
        for chunk in chunks
    ]
    payload = generate_ai_bundle(request_data, source_excerpts=source_excerpts)
    persist_generation_log(db, user.id, req.model_dump(), payload)
    return payload


@app.get("/api/ai/history", response_model=list[AIHistoryItem])
def history(
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    logs = db.scalars(
        select(AIGenerationLog)
        .where(AIGenerationLog.created_by_id == user.id)
        .order_by(AIGenerationLog.created_at.desc())
    ).all()
    return [
        AIHistoryItem(
            id=log.id,
            question_type=log.question_type,
            subject=log.subject,
            chapter=log.chapter,
            topic=log.topic,
            difficulty=log.difficulty,
            language=log.language,
            status=log.status,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]


@app.get("/api/ai/insights")
def insights(
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    if user.role == "student":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    logs = db.scalars(
        select(AIGenerationLog)
        .where(AIGenerationLog.created_by_id == user.id)
        .order_by(AIGenerationLog.created_at.desc())
        .limit(5)
    ).all()
    latest = logs[0] if logs else None
    return {
        "status": "ok",
        "summary": {
            "total_generations": len(logs),
            "latest_topic": latest.topic if latest else "N/A",
            "preferred_language": latest.language if latest else "en",
            "latest_question_type": latest.question_type if latest else "mcq",
        },
        "insights": [
            {
                "title": "Curriculum alignment",
                "text": "Generated items remain grounded in the selected chapter and topic context.",
            },
            {
                "title": "Language support",
                "text": "English and Urdu generation are supported with the selected language explicitly passed into each prompt.",
            },
        ],
    }


@app.get("/api/ai/recommendations")
def recommendations(
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    if user.role == "student":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    suggestions = db.scalars(
        select(AIGenerationLog).where(AIGenerationLog.created_by_id == user.id).limit(3)
    ).all()
    recommendations_list = []
    for log in suggestions:
        recommendations_list.append(
            {
                "topic": log.topic,
                "type": log.question_type,
                "recommendation": f"Create a follow-up {log.question_type} set for {log.topic} using {log.difficulty} difficulty and {log.language} language.",
            }
        )
    return {
        "status": "ok",
        "items": recommendations_list
        or [
            {
                "topic": "General practice",
                "type": "mcq",
                "recommendation": "Review chapter concepts and generate a mixed practice set to reinforce mastery.",
            }
        ],
    }
