from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="student")
    settings: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Curriculum(Base):
    __tablename__ = "curricula"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    grades: Mapped[list["Grade"]] = relationship(back_populates="curriculum")


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (UniqueConstraint("curriculum_id", "level", name="uq_grade_curriculum_level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(ForeignKey("curricula.id"), index=True)
    level: Mapped[int] = mapped_column(Integer)
    curriculum: Mapped[Curriculum] = relationship(back_populates="grades")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="grade")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("grade_id", "name", name="uq_subject_grade_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    grade: Mapped[Grade] = relationship(back_populates="subjects")
    books: Mapped[list["Book"]] = relationship(back_populates="subject")


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (UniqueConstraint("subject_id", "name", name="uq_book_subject_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[Subject] = relationship(back_populates="books")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="book")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("book_id", "position", name="uq_chapter_book_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=1)
    book: Mapped[Book] = relationship(back_populates="chapters")
    topics: Mapped[list["Topic"]] = relationship(back_populates="chapter")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("chapter_id", "name", name="uq_topic_chapter_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    chapter: Mapped[Chapter] = relationship(back_populates="topics")
    questions: Mapped[list["Question"]] = relationship(back_populates="topic")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(24))
    content: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    language: Mapped[str] = mapped_column(String(8), default="en")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[Topic] = relationship(back_populates="questions")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    questions: Mapped[list["AssessmentQuestion"]] = relationship(back_populates="assessment")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "position", name="uq_assessment_question_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    assessment: Mapped[Assessment] = relationship(back_populates="questions")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    answers: Mapped[list["AttemptAnswer"]] = relationship(back_populates="attempt")


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), index=True)
    assessment_question_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_questions.id"), index=True
    )
    response: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attempt: Mapped[Attempt] = relationship(back_populates="answers")


class GeneratedBatch(Base):
    __tablename__ = "generated_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    language: Mapped[str] = mapped_column(String(8), default="en")
    items: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
