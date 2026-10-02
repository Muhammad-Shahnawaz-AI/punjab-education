from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book, Chapter, Curriculum, Grade, Subject, Topic

router = APIRouter(prefix="/api", tags=["curriculum"])


class CurriculumItem(BaseModel):
    id: str
    name: str
    description: str
    is_sample: bool


class CurriculumList(BaseModel):
    curricula: list[CurriculumItem]


class CatalogItem(BaseModel):
    id: int
    name: str


class CatalogList(BaseModel):
    items: list[CatalogItem]


@router.get("/curriculum", response_model=CurriculumList)
def list_curricula(db: Session = Depends(get_db)) -> CurriculumList:
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.name)).all()
    return CurriculumList(
        curricula=[
            CurriculumItem(
                id=curriculum.code,
                name=curriculum.name,
                description=curriculum.description,
                is_sample=curriculum.is_sample,
            )
            for curriculum in curricula
        ]
    )


@router.get("/curriculum/{curriculum_code}/grades", response_model=CatalogList)
def list_grades(curriculum_code: str, db: Session = Depends(get_db)) -> CatalogList:
    curriculum = db.scalar(select(Curriculum).where(Curriculum.code == curriculum_code))
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    grades = db.scalars(
        select(Grade).where(Grade.curriculum_id == curriculum.id).order_by(Grade.level)
    ).all()
    return CatalogList(
        items=[CatalogItem(id=grade.id, name=f"Grade {grade.level}") for grade in grades]
    )


@router.get("/grades/{grade_id}/subjects", response_model=CatalogList)
def list_subjects(grade_id: int, db: Session = Depends(get_db)) -> CatalogList:
    if db.get(Grade, grade_id) is None:
        raise HTTPException(status_code=404, detail="Grade not found")
    subjects = db.scalars(
        select(Subject).where(Subject.grade_id == grade_id).order_by(Subject.name)
    ).all()
    return CatalogList(items=[CatalogItem(id=item.id, name=item.name) for item in subjects])


@router.get("/subjects/{subject_id}/books", response_model=CatalogList)
def list_books(subject_id: int, db: Session = Depends(get_db)) -> CatalogList:
    if db.get(Subject, subject_id) is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    books = db.scalars(select(Book).where(Book.subject_id == subject_id).order_by(Book.name)).all()
    return CatalogList(items=[CatalogItem(id=item.id, name=item.name) for item in books])


@router.get("/books/{book_id}/chapters", response_model=CatalogList)
def list_chapters(book_id: int, db: Session = Depends(get_db)) -> CatalogList:
    if db.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db.scalars(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.position)
    ).all()
    return CatalogList(items=[CatalogItem(id=item.id, name=item.name) for item in chapters])


@router.get("/chapters/{chapter_id}/topics", response_model=CatalogList)
def list_topics(chapter_id: int, db: Session = Depends(get_db)) -> CatalogList:
    if db.get(Chapter, chapter_id) is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    topics = db.scalars(
        select(Topic).where(Topic.chapter_id == chapter_id).order_by(Topic.name)
    ).all()
    return CatalogList(items=[CatalogItem(id=item.id, name=item.name) for item in topics])
