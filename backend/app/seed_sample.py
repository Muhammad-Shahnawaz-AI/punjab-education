from sqlalchemy import select

from app.database import SessionLocal
from app.models import Book, Chapter, Curriculum, Grade, Subject, Topic

SAMPLE_CODE = "sample-placeholder"
SAMPLE_NOTICE = "SAMPLE PLACEHOLDER DATA ONLY. This is not official Punjab curriculum content."


def seed_sample() -> None:
    with SessionLocal.begin() as db:
        existing = db.scalar(select(Curriculum).where(Curriculum.code == SAMPLE_CODE))
        if existing is not None:
            return

        curriculum = Curriculum(
            code=SAMPLE_CODE,
            name="Sample Curriculum (Placeholder)",
            description=SAMPLE_NOTICE,
            is_sample=True,
        )
        db.add(curriculum)
        for level in range(9, 13):
            grade = Grade(level=level, curriculum=curriculum)
            subject = Subject(name="Sample Subject", grade=grade)
            book = Book(name="Sample Book", subject=subject)
            chapter = Chapter(name="Sample Chapter", position=1, book=book)
            topic = Topic(name="Sample Topic", chapter=chapter)
            db.add_all([grade, subject, book, chapter, topic])


if __name__ == "__main__":
    seed_sample()
    print(f"Seeded {SAMPLE_NOTICE}")
