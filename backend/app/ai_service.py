from __future__ import annotations

import json
import os
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
        "provider": os.getenv("LLM_PROVIDER", "").strip(),
        "model": os.getenv("LLM_MODEL", "").strip(),
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        "base_url": (
            os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
            or "https://api.openai.com/v1"
        ),
    }


def _build_prompt(req: dict[str, Any]) -> str:
    language = req.get("language") or "en"
    source_context = (
        "\n\nApproved textbook source excerpts:\n"
        + "\n".join(
            f"[{source['source_name']} | {source['book']} | {source['chapter']} | "
            f"page {source['page']}]\n{source['text']}"
            for source in req.get("source_excerpts", [])
        )
        if req.get("source_excerpts")
        else ""
    )
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


def _validate_generated_items(
    items: list[dict[str, Any]], question_type: str
) -> list[dict[str, Any]]:
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
        raise HTTPException(
            status_code=422,
            detail=f"AI generation failed validation: {'; '.join(errors) or 'empty output'}",
        )
    return validated


def _provider_generation(req: dict[str, Any]) -> list[dict[str, Any]]:
    config = _provider_config()
    if not config["provider"] or not config["model"] or not config["api_key"]:
        raise HTTPException(
            status_code=503,
            detail="AI generation requires LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY configuration.",
        )

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
                    {
                        "role": "system",
                        "content": "Generate curriculum-aligned educational content in valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
            },
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="The configured AI provider request failed.",
        ) from error

    try:
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        parsed = json.loads(message)
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise HTTPException(
            status_code=502,
            detail="The configured AI provider returned an invalid JSON response.",
        ) from error
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        return parsed["items"]
    raise HTTPException(
        status_code=502,
        detail="The configured AI provider response must contain a JSON list of items.",
    )


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
        raise HTTPException(
            status_code=422, detail="Curriculum, subject, book, chapter, and topic are required"
        )

    provider_items = _provider_generation({**cleaned, "source_excerpts": source_excerpts or []})
    generated = _validate_generated_items(provider_items, cleaned["question_type"])
    return {
        "status": "ok",
        "request": {**cleaned, "count": max(1, min(cleaned["count"], 10))},
        "items": generated,
        "sources": [
            {key: source[key] for key in ("book", "chapter", "page", "source_name", "source_url")}
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
