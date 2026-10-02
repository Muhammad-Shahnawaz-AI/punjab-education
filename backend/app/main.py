import os
from typing import Annotated, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints

from app.curriculum import router as curriculum_router

app = FastAPI(title="Punjab Education Intelligence Platform API", version="0.1.0")
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/ai/generate")
def generate(req: GenerateRequest):
    # First-cut contract. Connect this endpoint to the chosen LLM/RAG service next.
    return {
        "status": "queued",
        "request": req.model_dump(),
        "items": [],
        "message": "AI provider integration pending.",
    }
