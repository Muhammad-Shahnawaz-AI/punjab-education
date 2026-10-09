import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RefreshSession, User

password_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hasher.verify(hashed_password, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail=(
                "Authentication is unavailable. Configure JWT_SECRET_KEY "
                "with at least 32 characters."
            ),
        )
    return secret


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise HTTPException(
            status_code=503, detail=f"Invalid authentication setting: {name}."
        ) from error
    if value < 1:
        raise HTTPException(status_code=503, detail=f"Invalid authentication setting: {name}.")
    return value


def issue_token_pair(db: Session, user: User) -> tuple[str, str, int]:
    now = datetime.now(UTC)
    access_expires_in = _positive_env_int("ACCESS_TOKEN_MINUTES", 15) * 60
    refresh_expires_at = now + timedelta(days=_positive_env_int("REFRESH_TOKEN_DAYS", 7))
    access_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "token_type": "access",
            "iat": now,
            "exp": now + timedelta(seconds=access_expires_in),
        },
        _jwt_secret(),
        algorithm="HS256",
    )
    token_id = uuid4().hex
    refresh_token = jwt.encode(
        {
            "sub": str(user.id),
            "jti": token_id,
            "token_type": "refresh",
            "iat": now,
            "exp": refresh_expires_at,
        },
        _jwt_secret(),
        algorithm="HS256",
    )
    db.add(
        RefreshSession(
            token_id=token_id,
            user_id=user.id,
            expires_at=refresh_expires_at,
        )
    )
    return access_token, refresh_token, access_expires_in


def decode_token(token: str, expected_type: str) -> dict[str, object] | None:
    try:
        claims = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    if claims.get("token_type") != expected_type:
        return None
    return claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    claims = decode_token(credentials.credentials, "access")
    subject = claims.get("sub") if claims is not None else None
    if not isinstance(subject, str) or not subject.isdigit():
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    user = db.get(User, int(subject))
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    return get_current_user(credentials=credentials, db=db)


def require_roles(*roles: str) -> Callable[..., User]:
    def check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return check_role


require_teacher = require_roles("teacher", "admin")
require_admin = require_roles("admin")


def find_active_refresh_session(db: Session, token_id: str, user_id: int) -> RefreshSession | None:
    return db.scalar(
        select(RefreshSession)
        .where(
            RefreshSession.token_id == token_id,
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
        .with_for_update()
    )
