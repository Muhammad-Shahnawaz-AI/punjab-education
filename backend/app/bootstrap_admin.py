import os

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def bootstrap_admin() -> None:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or len(password) < 12:
        raise SystemExit(
            "Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD (at least 12 characters)."
        )

    with SessionLocal.begin() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role != "admin":
                raise SystemExit("The configured bootstrap account exists but is not an admin.")
            print("Bootstrap admin already exists.")
            return
        db.add(User(email=email, hashed_password=hash_password(password), role="admin"))
    print(f"Created bootstrap admin: {email}")


if __name__ == "__main__":
    bootstrap_admin()
