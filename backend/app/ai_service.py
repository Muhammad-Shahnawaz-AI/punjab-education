from __future__ import annotations

import os
import random
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator
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

    @model_validator(mode="after")
    def validate_mcq_options(self) -> "MCQItem":
        option_values = [str(option).strip() for option in self.options]
        if len(set(option_values)) != 4:
            raise ValueError("MCQ options must be unique")
        if self.correct_answer.strip() not in option_values:
            raise ValueError("correct_answer must match one of the provided options")
        return self


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
        "base_url": (
            os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
            or "https://api.openai.com/v1"
        ),
    }


def _ur_text(value: str) -> str:
    return {
        "easy": "آسان",
        "medium": "درمیانی",
        "hard": "مشکل",
    }.get(value, value)


def _build_prompt(req: dict[str, Any]) -> str:
    language = req.get("language") or "en"
    source_context = "\n\nApproved textbook source excerpts:\n" + "\n".join(
        f"[{source['source_name']} | {source['book']} | {source['chapter']} | "
        f"page {source['page']}]\n{source['text']}"
        for source in req.get("source_excerpts", [])
    ) if req.get("source_excerpts") else ""
    if language == "ur":
        return (
            f"Punjab curriculum context: {req['curriculum']} | {req.get('subject')} | "
            f"{req.get('book')} | {req.get('chapter')} | {req.get('topic')} | "
            f"difficulty={req.get('difficulty')} | count={req.get('count')} | "
            f"learning objectives={req.get('learning_objectives') or 'general conceptual mastery'}. "
            "Generate curriculum-aligned, factually grounded educational material only, use the supplied topic and chapter context, "
            "and ensure all content is valid for classroom use."
            f"{source_context}"
        )
    return (
        f"Punjab curriculum context: {req['curriculum']} | {req.get('subject')} | {req.get('book')} | "
        f"{req.get('chapter')} | {req.get('topic')} | difficulty={req.get('difficulty')} | "
        f"count={req.get('count')} | learning objectives={req.get('learning_objectives') or 'general conceptual mastery'}. "
        "Generate curriculum-aligned, factually grounded educational material only, using the supplied context and valid educational structure."
        f"{source_context}"
    )


def _generate_mcq_payload(req: dict[str, Any], index: int) -> dict[str, Any]:
    topic = str(req["topic"]).strip() or "the selected topic"
    subject = str(req["subject"]).strip() or "the subject"
    difficulty = req.get("difficulty", "medium")
    question_variants = [
        f"Which statement best explains {topic} in {subject}?",
        f"What is the most accurate understanding of {topic} in {subject}?",
        f"Which option reflects the correct learning goal for {topic}?",
        f"Which explanation shows the strongest understanding of {topic}?",
    ]
    correct_answer = (
        f"Understanding {topic} requires applying the core idea, chapter context, and subject skills in {subject}."
    )
    distractors = [
        f"{topic} can be memorized without making sense of the chapter or subject concept.",
        f"{topic} is unrelated to learning goals and classroom application in {subject}.",
        f"{topic} is best learned by guessing rather than applying a clear principle or example.",
    ]
    options = [correct_answer, *distractors]
    rng = random.Random((index + 1) * 13 + len(topic))
    rng.shuffle(options)

    if req.get("language") == "ur":
        correct_answer_ur = (
            f"{topic} کو سمجھنے کے لیے {subject} کے مرکزی خیال، سبق کے سیاق و سباق اور عملی اطلاق کو سمجھنا ضروری ہے۔"
        )
        distractors_ur = [
            f"{topic} کو صرف یاد رکھ کر اور سبق سے الگ ہو کر سیکھا جا سکتا ہے۔",
            f"{topic} کا تعلق {subject} کے تعلیمی مقاصد سے نہیں ہے۔",
            f"{topic} کو Guessing کے ذریعے سمجھا جا سکتا ہے بغیر اصول کے۔",
        ]
        options_ur = [correct_answer_ur, *distractors_ur]
        rng_ur = random.Random((index + 1) * 17 + len(subject))
        rng_ur.shuffle(options_ur)
        return {
            "question": f"{index + 1}. {topic} کے بارے میں سب سے درست بیان کیا ہے؟",
            "options": options_ur,
            "correct_answer": correct_answer_ur,
            "explanation": f"یہ سوال {topic} کے بنیادی تصور، اس کے مقام، اور {subject} میں اس کے اطلاق کو واضح کرتا ہے۔",
            "difficulty": _ur_text(difficulty),
            "topic": topic,
            "learning_objective": f"{topic} کو {subject} کے تعلیمی مقاصد کے مطابق سمجھنا اور اس کا اطلاق کرنا۔",
        }

    return {
        "question": f"{index + 1}. {question_variants[index % len(question_variants)]}",
        "options": options,
        "correct_answer": correct_answer,
        "explanation": f"This item checks that {topic} is understood in the right classroom context and applied through the key concept in {subject}.",
        "difficulty": difficulty,
        "topic": topic,
        "learning_objective": f"Explain and apply the main idea of {topic} within {subject}.",
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
        if req.get("source_excerpts"):
            raise HTTPException(
                status_code=503,
                detail="Configure an AI provider to generate questions grounded in the selected textbook.",
            )
        return _build_local_items(req)

    prompt = _build_prompt(req)
    try:
        response = httpx.post(
            f"{config['base_url']}/chat/completions",
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
            if req.get("source_excerpts"):
                raise HTTPException(
                    status_code=502,
                    detail="The AI provider returned no textbook-grounded content.",
                )
            return _build_local_items(req)
        parsed = __import__("json").loads(generated)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            return parsed["items"]
    except Exception:
        if req.get("source_excerpts"):
            raise HTTPException(
                status_code=502,
                detail="The AI provider failed to generate textbook-grounded content.",
            )
        return _build_local_items(req)
    if req.get("source_excerpts"):
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an unsupported textbook-grounded response.",
        )
    return _build_local_items(req)


def generate_ai_bundle(
    req: dict[str, Any],
    source_excerpts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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

    provider_items = _provider_generation(
        {**cleaned, "source_excerpts": source_excerpts or []}
    )
    generated = _validate_generated_items(provider_items, cleaned["question_type"])
    return {
        "status": "ok",
        "request": {**cleaned, "count": max(1, min(cleaned["count"], 10))},
        "items": generated,
        "sources": [
            {
                key: source[key]
                for key in ("book", "chapter", "page", "source_name", "source_url")
            }
            for source in source_excerpts or []
        ],
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
