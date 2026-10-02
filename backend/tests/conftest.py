from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base, Book, Chapter, Curriculum, Grade, Subject, Topic


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
            code="sample-fixture",
            name="Sample Curriculum",
            description="Sample data only.",
            is_sample=True,
        )
        grade_nine = Grade(level=9, curriculum=curriculum)
        Grade(level=10, curriculum=curriculum)
        subject = Subject(name="Sample Subject", grade=grade_nine)
        book = Book(name="Sample Book", subject=subject)
        chapter = Chapter(name="Sample Chapter", position=1, book=book)
        Topic(name="Sample Topic", chapter=chapter)
        db.add(curriculum)

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
