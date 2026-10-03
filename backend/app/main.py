import os
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_service import generate_ai_bundle, persist_generation_log
from app.auth import router as auth_router
from app.curriculum import router as curriculum_router
from app.database import get_db
from app.models import AIGenerationLog, User
from app.security import get_current_user, require_teacher

app = FastAPI(title="Punjab Education Intelligence Platform API", version="0.1.0")
app.include_router(auth_router)
app.include_router(curriculum_router)
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/ai/generate")
def generate(
    req: GenerateRequest,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    payload = generate_ai_bundle(req.model_dump())
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
    return {"status": "ok", "items": recommendations_list or [{"topic": "General practice", "type": "mcq", "recommendation": "Review chapter concepts and generate a mixed practice set to reinforce mastery."}]}
