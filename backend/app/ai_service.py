from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models import AIGenerationLog


class MCQItem(BaseModel):
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str
    difficulty: str = "medium"
    topic: str
    learning_objective: str | None = None


class SubjectiveItem(BaseModel):
    question: str
    expected_answer: str
    marks: int = Field(ge=1, le=20)
    difficulty: str = "medium"
    topic: str
    language: str = "en"


class QuizBundle(BaseModel):
    title: str
    instructions: str
    questions: list[dict[str, Any]] = Field(min_length=1)
    difficulty: str = "medium"
    language: str = "en"


class AssignmentBundle(BaseModel):
    title: str
    objectives: list[str] = Field(min_length=1)
    instructions: str
    tasks: list[dict[str, Any]] = Field(min_length=1)
    difficulty: str = "medium"
    topic: str
    learning_outcomes: list[str] = Field(min_length=1)


class AIRequestContext(BaseModel):
    curriculum: str
    subject: str
    book: str
    chapter: str
    topic: str
    question_type: str
    count: int = Field(ge=1, le=50)
    difficulty: str = "medium"
    language: str = "en"
    grade: str | None = None
    learning_objectives: str | None = None


def _provider_config() -> dict[str, str]:
    return {
        "provider": os.getenv("LLM_PROVIDER", "local-fallback").strip() or "local-fallback",
        "model": os.getenv("LLM_MODEL", "local-curriculum-generator").strip() or "local-curriculum-generator",
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
    }


def _ur_text(value: str) -> str:
    return {
        "easy": "آسان",
        "medium": "درمیانی",
        "hard": "مشکل",
    }.get(value, value)


def _build_prompt(req: dict[str, Any]) -> str:
    language = req.get("language") or "en"
    if language == "ur":
        return (
            f"Punjab curriculum context: {req['curriculum']} | {req.get('subject')} | "
            f"{req.get('book')} | {req.get('chapter')} | {req.get('topic')} | "
            f"difficulty={req.get('difficulty')} | count={req.get('count')} | "
            f"learning objectives={req.get('learning_objectives') or 'general conceptual mastery'}. "
            "Generate curriculum-aligned, factually grounded educational material only, use the supplied topic and chapter context, "
            "and ensure all content is valid for classroom use."
        )
    return (
        f"Punjab curriculum context: {req['curriculum']} | {req.get('subject')} | {req.get('book')} | "
        f"{req.get('chapter')} | {req.get('topic')} | difficulty={req.get('difficulty')} | "
        f"count={req.get('count')} | learning objectives={req.get('learning_objectives') or 'general conceptual mastery'}. "
        "Generate curriculum-aligned, factually grounded educational material only, using the supplied context and valid educational structure."
    )


def _generate_mcq_payload(req: dict[str, Any], index: int) -> dict[str, Any]:
    topic = req["topic"]
    subject = req["subject"]
    difficulty = req.get("difficulty", "medium")
    if req.get("language") == "ur":
        return {
            "question": f"{index + 1}. {topic} کے متعلق درست بیان کیا ہے؟",
            "options": [
                f"{subject} میں {topic} کے لیے اصول پر مبنی سمجھ ضروری ہے۔",
                f"{topic} کو بے ترتیب طریقے سے سیکھا جا سکتا ہے۔",
                f"{topic} کا تعلق درسی کتاب سے باہر نہیں ہے۔",
                f"{topic} کی وضاحت معیاری ربط کے بغیر ہوتی ہے۔",
            ],
            "correct_answer": f"{subject} میں {topic} کے لیے اصول پر مبنی سمجھ ضروری ہے۔",
            "explanation": f"یہ سوال {topic} کے مرکزی تصور کو ظاہر کرتا ہے اور اس موضوع کی سچائی کو اساتذہ کے نصاب کے مطابق ثابت کرتا ہے۔",
            "difficulty": _ur_text(difficulty),
            "topic": topic,
            "learning_objective": f"{topic} کو {subject} کے تحت سمجھنا اور اس کے بنیادی اصول جاننا۔",
        }
    return {
        "question": f"Which statement best explains {topic} in {subject}? (Item {index + 1})",
        "options": [
            f"Understanding {topic} requires applying core principles from the {subject} curriculum.",
            f"{topic} can be learned without any connection to the chapter concept.",
            f"{topic} is unrelated to learning objectives in {subject}.",
            f"The correct explanation for {topic} depends only on random recall.",
        ],
        "correct_answer": f"Understanding {topic} requires applying core principles from the {subject} curriculum.",
        "explanation": f"This item reinforces the learning objective for {topic} and checks the key concept within the relevant chapter, book, and curriculum context.",
        "difficulty": difficulty,
        "topic": topic,
        "learning_objective": f"Explain and apply the key ideas behind {topic} within {subject}.",
    }


def _generate_subjective_payload(req: dict[str, Any], index: int) -> dict[str, Any]:
    topic = req["topic"]
    if req.get("language") == "ur":
        return {
            "question": f"{index + 1}. {topic} کی تعریف کرتے ہوئے ایک مختصر وضاحت دیں۔",
            "expected_answer": f"{topic} کے بنیادی اصول، تعلق اور عملی اطلاق کو واضح طور پر بیان کریں۔",
            "marks": 5,
            "difficulty": _ur_text(req.get("difficulty", "medium")),
            "topic": topic,
            "language": "ur",
        }
    return {
        "question": f"{index + 1}. Describe {topic} in your own words and explain how it connects to the chapter learning goals.",
        "expected_answer": f"A clear explanation of {topic}, including the key principle, its relevance to the chapter, and a brief application to the subject context.",
        "marks": 5,
        "difficulty": req.get("difficulty", "medium"),
        "topic": topic,
        "language": "en",
    }


def _generate_quiz_payload(req: dict[str, Any]) -> dict[str, Any]:
    if req.get("language") == "ur":
        return {
            "title": f"{req['topic']} کا مختصر کوئز",
            "instructions": "ہر سوال کا درست جواب منتخب کریں۔ آٹھ سوالات کے بعد نتائج دیکھیں۔",
            "questions": [_generate_mcq_payload(req, i) for i in range(min(int(req.get("count", 5)), 5))],
            "difficulty": _ur_text(req.get("difficulty", "medium")),
            "language": "ur",
        }
    return {
        "title": f"{req['topic']} quick quiz",
        "instructions": "Choose the best answer for each item and review the explanation after submission.",
        "questions": [_generate_mcq_payload(req, i) for i in range(min(int(req.get("count", 5)), 5))],
        "difficulty": req.get("difficulty", "medium"),
        "language": "en",
    }


def _generate_assignment_payload(req: dict[str, Any]) -> dict[str, Any]:
    if req.get("language") == "ur":
        return {
            "title": f"{req['topic']} تفویض",
            "objectives": [
                f"{req['topic']} کے بنیادی اصول کو سمجھنا۔",
                f"اس موضوع میں عملی مثالیں دینا۔",
            ],
            "instructions": "موضوع کو واضح طریقے سے بیان کریں، مثالیں دیں اور اپنے جواب کو انفرادی طور پر تیار کریں۔",
            "tasks": [
                {"task": f"{req['topic']} کی تعریف اور اہم نکات لکھیں۔", "marks": 10},
                {"task": "پہلی مثال اور دوسرا سوال بنائیں۔", "marks": 10},
            ],
            "difficulty": _ur_text(req.get("difficulty", "medium")),
            "topic": req["topic"],
            "learning_outcomes": [
                f"{req['topic']} کے اہم اصول بیان کر سکتے ہیں۔",
                f"موضوع کو عملی زندگی سے جوڑ سکتے ہیں۔",
            ],
            "language": "ur",
        }
    return {
        "title": f"{req['topic']} assignment",
        "objectives": [
            f"Explain the key ideas behind {req['topic']}.",
            f"Apply the concept to a real classroom example.",
        ],
        "instructions": "Answer each task in complete sentences and add a brief explanation for the final response.",
        "tasks": [
            {"task": f"Define {req['topic']} clearly and explain why it matters.", "marks": 10},
            {"task": "Provide one worked example and one short reflection.", "marks": 10},
        ],
        "difficulty": req.get("difficulty", "medium"),
        "topic": req["topic"],
        "learning_outcomes": [
            f"Students can explain the concept of {req['topic']}.",
            f"Students can connect the topic to practice and assessment tasks.",
        ],
        "language": "en",
    }


def _validate_generated_items(items: list[dict[str, Any]], question_type: str) -> list[dict[str, Any]]:
    errors: list[str] = []
    seen_questions: set[str] = set()
    validated: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("question") or item.get("title") or "").strip().lower()
        if not key:
            errors.append("Empty question payload")
            continue
        if key in seen_questions:
            errors.append(f"Duplicate question: {key}")
            continue
        seen_questions.add(key)
        if question_type == "mcq":
            try:
                MCQItem.model_validate(item)
                validated.append(item)
            except ValidationError as exc:
                errors.append(str(exc))
        elif question_type == "subjective":
            try:
                SubjectiveItem.model_validate(item)
                validated.append(item)
            except ValidationError as exc:
                errors.append(str(exc))
        elif question_type == "quiz":
            try:
                QuizBundle.model_validate(item)
                validated.append(item)
            except ValidationError as exc:
                errors.append(str(exc))
        elif question_type == "assignment":
            try:
                AssignmentBundle.model_validate(item)
                validated.append(item)
            except ValidationError as exc:
                errors.append(str(exc))
    if not validated:
        raise HTTPException(status_code=422, detail=f"AI generation failed validation: {'; '.join(errors) or 'empty output'}")
    return validated


def _build_local_items(req: dict[str, Any]) -> list[dict[str, Any]]:
    question_type = req.get("question_type", "mcq")
    count = max(1, min(int(req.get("count", 5)), 10))
    if question_type == "mcq":
        return [_generate_mcq_payload(req, i) for i in range(count)]
    if question_type == "subjective":
        return [_generate_subjective_payload(req, i) for i in range(count)]
    if question_type == "quiz":
        return [_generate_quiz_payload(req)]
    if question_type == "assignment":
        return [_generate_assignment_payload(req)]
    raise HTTPException(status_code=400, detail="Unsupported question type")


def _provider_generation(req: dict[str, Any]) -> list[dict[str, Any]]:
    config = _provider_config()
    provider = config["provider"]
    if provider == "local-fallback" or not config["api_key"]:
        return _build_local_items(req)

    prompt = _build_prompt(req)
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": "Generate curriculum-aligned educational content in valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        generated = message.strip()
        if not generated:
            return _build_local_items(req)
        parsed = __import__("json").loads(generated)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            return parsed["items"]
    except Exception:
        return _build_local_items(req)
    return _build_local_items(req)


def generate_ai_bundle(req: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        "curriculum": str(req.get("curriculum", "")).strip(),
        "subject": str(req.get("subject", "")).strip(),
        "book": str(req.get("book", "")).strip(),
        "chapter": str(req.get("chapter", "")).strip(),
        "topic": str(req.get("topic", "")).strip(),
        "question_type": str(req.get("question_type", "mcq")).strip() or "mcq",
        "count": int(req.get("count", 5) or 5),
        "difficulty": str(req.get("difficulty", "medium")).strip() or "medium",
        "language": str(req.get("language", "en")).strip() or "en",
        "grade": str(req.get("grade", "") or "").strip(),
        "learning_objectives": str(req.get("learning_objectives", "") or "").strip(),
    }
    if not all(cleaned[field] for field in ("curriculum", "subject", "book", "chapter", "topic")):
        raise HTTPException(status_code=422, detail="Curriculum, subject, book, chapter, and topic are required")

    provider_items = _provider_generation(cleaned)
    generated = _validate_generated_items(provider_items, cleaned["question_type"])
    return {
        "status": "ok",
        "request": {**cleaned, "count": max(1, min(cleaned["count"], 10))},
        "items": generated,
        "message": f"Generated {len(generated)} curriculum-grounded {cleaned['question_type']} item(s).",
    }


def persist_generation_log(
    db: Session,
    user_id: int | None,
    request: dict[str, Any],
    payload: dict[str, Any],
    status: str = "completed",
) -> AIGenerationLog:
    log = AIGenerationLog(
        created_by_id=user_id,
        curriculum=request.get("curriculum", ""),
        subject=request.get("subject", ""),
        book=request.get("book", ""),
        chapter=request.get("chapter", ""),
        topic=request.get("topic", ""),
        question_type=request.get("question_type", "mcq"),
        count=int(request.get("count", 1) or 1),
        difficulty=request.get("difficulty", "medium"),
        language=request.get("language", "en"),
        prompt=_build_prompt(request),
        response=payload,
        status=status,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
