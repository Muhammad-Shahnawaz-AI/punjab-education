import os
import re
from typing import Annotated

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


def build_portal_answer(language: str, subject: str = "General Education") -> str:
    if language == "ur":
        return (
            f"یہ {subject} کے لیے تعلیمی پورٹل ہے۔ منتظم نے ابھی تک کتابیں شامل نہیں کیں، اس لیے دستیاب کتابی مواد موجود نہیں ہے۔ "
            "میں صرف تعلیمی سوالات، نصابی موضوعات، سبق، امتحان، مطالعہ، اور تعلیمی رہنمائی میں مدد دے سکتا ہوں۔ "
            "اگر آپ چاہیں تو میں آپ کے لیے کسی موضوع کی وضاحت، خلاصہ، یا مشق سوالات بنا سکتا ہوں۔"
        )
    return (
        f"This is an education platform focused on {subject}. The administrator has not added books to the portal yet, so there are no uploaded books available right now. "
        "I can only help with educational questions, curriculum topics, lessons, study guidance, exams, and school or university learning support. "
        "I can still explain a concept, provide a quick summary, or generate practice questions for this subject."
    )


def detect_subject(prompt: str, requested_subject: str | None = None) -> str:
    if requested_subject and requested_subject.strip():
        return requested_subject.strip()
    text = prompt.casefold()
    for subject, keywords in {
        "Mathematics": ("math", "mathematics", "algebra", "geometry", "equation", "calculus", "percentage"),
        "Science": ("science", "biology", "chemistry", "physics", "cell", "experiment", "energy"),
        "English": ("english", "grammar", "essay", "literature", "reading", "sentence", "vocabulary"),
        "Computer Science": ("computer", "programming", "coding", "algorithm", "software", "python", "data"),
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


def build_local_education_answer(
    prompt: str,
    language: str,
    subject: str,
    intent: str,
    excerpts: list[dict[str, object]],
    image_data: str | None = None,
) -> str:
    subject_label = detect_subject(prompt, subject)
    intent_label = detect_intent(prompt, intent)
    topic = re.sub(r"[^\w\s\u0600-\u06ff]", " ", prompt).strip()[:90] or "this topic"

    knowledge = {
        "Mathematics": "Mathematics works by building understanding from patterns, operations, and logic. Start with the core idea, then solve step by step using definitions and formulas.",
        "Science": "Science explains natural phenomena through observation, evidence, and experimentation. Use clear steps: identify the principle, relate it to the question, and explain the cause and effect.",
        "English": "English learning improves vocabulary, grammar, reading, and writing. A strong answer should explain the idea clearly, use correct structure, and support it with examples.",
        "Computer Science": "Computer science focuses on logic, problem solving, and how algorithms work. Break the task into inputs, processing, and expected output before explaining the method.",
        "Social Studies": "Social studies connects people, history, geography, and civic life. Explain the event, its importance, and the reasoning behind it using context.",
        "General Education": "Education questions are best answered by clearly explaining the concept, giving a useful example, and linking it to the subject skill being learned.",
    }

    if intent_label == "summary":
        body = f"Summary of {topic}: the main idea is to focus on the key concept, the most important facts, and the reason it matters in {subject_label.lower()}. Use a short explanation and a practical example."
    elif intent_label == "quiz":
        body = f"Practice question: explain or solve one key idea from {topic} in {subject_label}. Then provide the answer with a short reason and one example."
    elif intent_label == "solve":
        body = f"To solve this in {subject_label}, first identify the known values, choose the correct method, write the steps clearly, and check the final result with common sense."
    else:
        body = f"Concept explanation: {topic} in {subject_label} is best understood by defining the main idea, linking it to examples, and showing how it is used in real learning."

    if excerpts:
        body += " The selected book excerpts support a concept-based answer, so the explanation should stay grounded in the chapter topic and avoid introducing unrelated facts."
    if image_data:
        body += " The attached image should be interpreted as educational visual content, and the answer should explain the diagram, graph, or text in a learning-focused way."

    body = f"{knowledge.get(subject_label, knowledge['General Education'])} {body}"

    if language == "ur":
        return (
            "میں ایک چھوٹا اور تعلیمی طور پر محدود تعلیمی معاون ہوں۔ "
            f"{body} "
            "آپ کا سوال تعلیمی موضوع کے اندر ہونا چاہیے، اور میں صرف اسکول/کالج کی تعلیم، نصاب، سبق، امتحان، یا مطالعہ سے متعلق مدد دے سکتا ہوں۔"
        )
    return (
        "I am a small education-only learning assistant. "
        f"{body} "
        "This response stays within school, curriculum, lesson, study, and assessment support and avoids unrelated non-educational topics."
    )


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
        term.casefold()
        for term in re.findall(r"[\w\u0600-\u06ff]{2,}", prompt, flags=re.UNICODE)
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

    if not excerpts and not prompt.strip():
        raise HTTPException(status_code=400, detail="Please enter a learning question.")

    if not excerpts:
        return build_portal_answer(language, detect_subject(prompt, subject))

    return build_local_education_answer(prompt, language, detect_subject(prompt, subject), detect_intent(prompt, intent), excerpts, image_data)[:12000]


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
        answer = _chat_completion(
            prompt,
            request.language,
            [],
            subject=request.subject,
            intent=request.intent,
            image_data=request.image_data,
        )
        return StudyChatResponse(answer=answer, citations=[])

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
