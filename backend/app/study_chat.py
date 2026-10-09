import os
import re
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserBook, UserBookChunk
from app.security import get_current_user

EDUCATION_TERMS = {
    "school",
    "student",
    "teacher",
    "education",
    "curriculum",
    "subject",
    "chapter",
    "lesson",
    "exam",
    "quiz",
    "assignment",
    "homework",
    "study",
    "book",
    "math",
    "mathematics",
    "physics",
    "chemistry",
    "biology",
    "english",
    "urdu",
    "science",
    "history",
    "geography",
    "computer",
    "grade",
    "class",
    "university",
    "learning",
    "knowledge",
    "photosynthesis",
}

NON_EDUCATION_TERMS = {
    "politics",
    "war",
    "weapon",
    "bomb",
    "violence",
    "gambling",
    "porn",
    "casino",
    "drugs",
    "hacking",
    "crypto",
    "finance",
    "stock",
    "trading",
    "sports",
    "movie",
    "music",
    "celebrity",
    "recipe",
    "cooking",
    "travel",
}

router = APIRouter(prefix="/api/study", tags=["study chat"])
StudyPrompt = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class StudyChatRequest(BaseModel):
    book_ids: list[int] = Field(default_factory=list, max_length=3)
    prompt: StudyPrompt
    language: str = Field(default="en", pattern="^(en|ur)$")
    image_data: str | None = Field(default=None, max_length=200_000)
    subject: str = Field(default="General Education", max_length=80)
    intent: str = Field(default="explain", max_length=40)
    grade: str = Field(default="General", max_length=40)

    @field_validator("book_ids")
    @classmethod
    def book_ids_must_be_unique(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Select each book only once.")
        return value


def _normalize_to_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip()


def is_education_related_query(prompt: str) -> bool:
    text = re.sub(r"[^a-zA-Z0-9\u0600-\u06ff\s]", " ", prompt.casefold())
    tokens = set(re.findall(r"[\w\u0600-\u06ff]+", text))
    if not tokens:
        return False
    if tokens & NON_EDUCATION_TERMS:
        return False
    if tokens & EDUCATION_TERMS:
        return True
    return any(
        phrase in text
        for phrase in (
            "school",
            "student",
            "teacher",
            "lesson",
            "subject",
            "exam",
            "study",
            "chapter",
            "curriculum",
            "homework",
            "education",
            "learning",
        )
    )


def detect_subject(prompt: str, requested_subject: str | None = None) -> str:
    if requested_subject and requested_subject.strip():
        return requested_subject.strip()
    text = prompt.casefold()
    for subject, keywords in {
        "Mathematics": (
            "math",
            "mathematics",
            "algebra",
            "geometry",
            "equation",
            "calculus",
            "percentage",
        ),
        "Science": ("science", "biology", "chemistry", "physics", "cell", "experiment", "energy"),
        "English": (
            "english",
            "grammar",
            "essay",
            "literature",
            "reading",
            "sentence",
            "vocabulary",
        ),
        "Computer Science": (
            "computer",
            "programming",
            "coding",
            "algorithm",
            "software",
            "python",
            "data",
        ),
        "Social Studies": ("history", "geography", "civics", "social", "economics", "culture"),
    }.items():
        if any(keyword in text for keyword in keywords):
            return subject
    return "General Education"


def detect_intent(prompt: str, requested_intent: str | None = None) -> str:
    if requested_intent and requested_intent.strip():
        return requested_intent.strip().lower()
    text = prompt.casefold()
    if any(word in text for word in ("summarize", "summary", "overview", "brief")):
        return "summary"
    if any(word in text for word in ("quiz", "mcq", "practice", "question", "test")):
        return "quiz"
    if any(word in text for word in ("solve", "calculate", "equation", "answer")):
        return "solve"
    if any(word in text for word in ("define", "what is", "explain", "why", "how does")):
        return "explain"
    return "explain"


class StudyCitation(BaseModel):
    book_id: int
    book_title: str
    page_number: int


class StudyChatResponse(BaseModel):
    answer: str
    citations: list[StudyCitation]


def retrieve_relevant_chunks(
    db: Session,
    owner_id: int,
    book_ids: list[int],
    prompt: str,
) -> list[tuple[UserBook, UserBookChunk]]:
    books = db.scalars(
        select(UserBook).where(
            UserBook.owner_id == owner_id,
            UserBook.id.in_(book_ids),
        )
    ).all()
    if len(books) != len(book_ids):
        raise HTTPException(status_code=404, detail="One or more selected books were not found.")

    chunks = db.execute(
        select(UserBook, UserBookChunk)
        .join(UserBookChunk, UserBookChunk.book_id == UserBook.id)
        .where(UserBook.owner_id == owner_id, UserBook.id.in_(book_ids))
    ).all()
    terms = {
        term.casefold() for term in re.findall(r"[\w\u0600-\u06ff]{2,}", prompt, flags=re.UNICODE)
    }

    def relevance(row: tuple[UserBook, UserBookChunk]) -> tuple[int, int, int]:
        book, chunk = row
        text = chunk.content.casefold()
        matched_terms = sum(1 for term in terms if term in text)
        phrase_match = int(prompt.casefold() in text)
        return matched_terms, phrase_match, -chunk.position

    ranked = sorted(chunks, key=relevance, reverse=True)
    selected = [row for row in ranked if relevance(row)[0] > 0 or relevance(row)[1] > 0][:6]
    if not selected:
        selected = ranked[:6]
    return selected


def _chat_completion(
    prompt: str,
    language: str,
    excerpts: list[dict[str, object]],
    subject: str = "General Education",
    intent: str = "explain",
    image_data: str | None = None,
) -> str:
    if not is_education_related_query(prompt):
        raise HTTPException(
            status_code=400,
            detail="I can help only with education-related queries and school learning topics.",
        )

    if not excerpts:
        raise HTTPException(
            status_code=422,
            detail="No relevant text was found in the selected books.",
        )

    provider = os.getenv("LLM_PROVIDER", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = (
        os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        or "https://api.openai.com/v1"
    )
    if not provider or not model or not api_key:
        raise HTTPException(
            status_code=503,
            detail="Study AI is not configured. Set LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY.",
        )
    if urlparse(base_url).scheme != "https":
        raise HTTPException(
            status_code=503,
            detail="Study AI requires an HTTPS LLM_BASE_URL.",
        )

    excerpt_context = "\n\n".join(
        f"[{excerpt['book_title']}, page {excerpt['page_number']}]\n{excerpt['text']}"
        for excerpt in excerpts
    )
    language_name = "Urdu" if language == "ur" else "English"
    user_content: str | list[dict[str, object]] = (
        f"Subject: {subject}\nRequested task: {intent}\n"
        f"Question: {prompt}\n\nSelected book excerpts:\n{excerpt_context}"
    )
    if image_data:
        user_content = [
            {
                "type": "text",
                "text": (
                    f"Subject: {subject}\nRequested task: {intent}\n"
                    f"Question: {prompt}\n\nSelected book excerpts:\n{excerpt_context}"
                ),
            },
            {"type": "image_url", "image_url": {"url": image_data}},
        ]
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"******",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Answer in {language_name}. This is an education study assistant. "
                            "Answer using only the selected book excerpts and attached educational "
                            "image. If they do not contain enough information, clearly say so. "
                            "Do not invent facts. Keep the answer concise and cite supporting pages."
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.2,
            },
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="The configured Study AI provider request failed.",
        ) from error

    try:
        answer = response.json()["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
        raise HTTPException(
            status_code=502,
            detail="The configured Study AI provider returned an invalid response.",
        ) from error
    if not answer:
        raise HTTPException(
            status_code=502,
            detail="The configured Study AI provider returned an empty answer.",
        )
    return answer[:12000]


@router.post("/chat", response_model=StudyChatResponse)
def chat_about_books(
    request: StudyChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyChatResponse:
    prompt = _normalize_to_text(request.prompt)
    if not prompt:
        raise HTTPException(status_code=400, detail="Please enter an education-related question.")
    if not is_education_related_query(prompt):
        raise HTTPException(
            status_code=400,
            detail="I can help only with education-related queries and school learning topics.",
        )

    if not request.book_ids:
        raise HTTPException(
            status_code=422,
            detail="Select at least one uploaded book to ask a source-grounded question.",
        )

    relevant = retrieve_relevant_chunks(db, user.id, request.book_ids, prompt)
    excerpts: list[dict[str, object]] = []
    citations: list[StudyCitation] = []
    seen_citations: set[tuple[int, int]] = set()
    for book, chunk in relevant:
        excerpts.append(
            {
                "book_title": book.title,
                "page_number": chunk.page_number,
                "text": chunk.content[:2000],
            }
        )
        citation = (book.id, chunk.page_number)
        if citation not in seen_citations:
            citations.append(
                StudyCitation(
                    book_id=book.id,
                    book_title=book.title,
                    page_number=chunk.page_number,
                )
            )
            seen_citations.add(citation)
    answer = _chat_completion(
        prompt,
        request.language,
        excerpts,
        subject=request.subject,
        intent=request.intent,
        image_data=request.image_data,
    )
    return StudyChatResponse(answer=answer, citations=citations)
