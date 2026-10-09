from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import rate_limiter
from app.database import get_db
from app.main import app
from app.models import Base, Book, Chapter, Curriculum, Grade, Subject, Topic, User
from app.security import issue_token_pair


@pytest.fixture
def catalog_client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with testing_sessions.begin() as db:
        curriculum = Curriculum(
            code="punjab-fixture",
            name="Punjab Board Test Fixture",
            description="Isolated test fixture; never used as production curriculum.",
            is_sample=False,
        )
        sample_curriculum = Curriculum(
            code="sample-placeholder",
            name="Sample Curriculum",
            description="Sample data only.",
            is_sample=True,
        )
        grade_nine = Grade(level=9, curriculum=curriculum)
        Grade(level=10, curriculum=curriculum)
        subject = Subject(name="Mathematics", grade=grade_nine)
        book = Book(name="Mathematics 9", subject=subject)
        chapter = Chapter(name="Number Systems", position=1, book=book)
        Topic(name="Integers", chapter=chapter)
        db.add_all([curriculum, sample_curriculum])

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def auth_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, dict[str, str]], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-signing-key-that-is-long-enough-123")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_sessions = testing_sessions
    roles = {
        "teacher": User(email="teacher@example.com", hashed_password="unused", role="teacher"),
        "admin": User(email="admin@example.com", hashed_password="unused", role="admin"),
    }
    tokens: dict[str, str] = {}
    with testing_sessions.begin() as db:
        db.add_all(list(roles.values()))
        curriculum = Curriculum(
            code="upload-test-curriculum",
            name="Upload Test Curriculum",
            description="Isolated upload test data.",
            is_sample=False,
        )
        grade = Grade(level=9, curriculum=curriculum)
        subject = Subject(name="Mathematics", grade=grade)
        db.add_all([curriculum, grade, subject])
        db.flush()
        for role, user in roles.items():
            access_token, _, _ = issue_token_pair(db, user)
            tokens[role] = access_token

    with rate_limiter.lock:
        rate_limiter.attempts.clear()
    try:
        with TestClient(app) as client:
            yield client, tokens
    finally:
        with rate_limiter.lock:
            rate_limiter.attempts.clear()
        app.dependency_overrides.clear()
        del app.state.test_sessions
        engine.dispose()
