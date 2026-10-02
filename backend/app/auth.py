import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Assessment, User
from app.security import (
    decode_token,
    find_active_refresh_session,
    get_current_user,
    hash_password,
    issue_token_pair,
    require_admin,
    require_teacher,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["authentication"])
PasswordInput = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class AuthRequest(BaseModel):
    email: EmailStr
    password: PasswordInput


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class RefreshRequest(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=20, max_length=4096)]


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: Literal["student", "teacher", "admin"]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    access_expires_in: int
    user: PublicUser


class AdminUserRequest(AuthRequest):
    role: Literal["student", "teacher", "admin"]


class UserListResponse(BaseModel):
    users: list[PublicUser]


class AssessmentListResponse(BaseModel):
    assessments: list[dict[str, int | str]]


class AuthRateLimiter:
    def __init__(self, limit: int = 12, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def check(self, endpoint: str, client: str) -> None:
        now = time.monotonic()
        key = (endpoint, client)
        with self.lock:
            attempts = self.attempts[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.limit:
                raise HTTPException(status_code=429, detail="Too many authentication attempts")
            attempts.append(now)


rate_limiter = AuthRateLimiter()


def rate_limit_auth(request: Request) -> None:
    client = request.client.host if request.client is not None else "unknown"
    rate_limiter.check(request.url.path, client)


def token_response(db: Session, user: User) -> TokenResponse:
    access_token, refresh_token, expires_in = issue_token_pair(db, user)
    db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_in=expires_in,
        user=PublicUser.model_validate(user),
    )


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
def register(request: AuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = str(request.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, hashed_password=hash_password(request.password), role="student")
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from error
    return token_response(db, user)


@router.post("/auth/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_auth)])
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = str(request.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return token_response(db, user)


@router.post("/auth/refresh", response_model=TokenResponse, dependencies=[Depends(rate_limit_auth)])
def refresh(request: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    claims = decode_token(request.refresh_token, "refresh")
    subject = claims.get("sub") if claims is not None else None
    token_id = claims.get("jti") if claims is not None else None
    if not isinstance(subject, str) or not subject.isdigit() or not isinstance(token_id, str):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = int(subject)
    refresh_session = find_active_refresh_session(db, token_id, user_id)
    user = db.get(User, user_id)
    if refresh_session is None or user is None:
        raise HTTPException(status_code=401, detail="Refresh token has expired or was revoked")
    refresh_session.revoked_at = datetime.now(UTC)
    return token_response(db, user)


@router.post("/auth/logout", dependencies=[Depends(rate_limit_auth)])
def logout(
    request: RefreshRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    claims = decode_token(request.refresh_token, "refresh")
    token_id = claims.get("jti") if claims is not None else None
    subject = claims.get("sub") if claims is not None else None
    if subject != str(user.id) or not isinstance(token_id, str):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    refresh_session = find_active_refresh_session(db, token_id, user.id)
    if refresh_session is not None:
        refresh_session.revoked_at = datetime.now(UTC)
        db.commit()
    return {"status": "ok"}


@router.get("/auth/me", response_model=PublicUser)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/auth/admin/users", response_model=UserListResponse)
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserListResponse:
    users = db.scalars(select(User).order_by(User.id)).all()
    return UserListResponse(users=[PublicUser.model_validate(user) for user in users])


@router.post("/auth/admin/users", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
def create_user(
    request: AdminUserRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    email = str(request.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        hashed_password=hash_password(request.password),
        role=request.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from error
    db.refresh(user)
    return user


@router.get("/teacher/assessments", response_model=AssessmentListResponse)
def list_teacher_assessments(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> AssessmentListResponse:
    statement = select(Assessment).order_by(Assessment.id)
    if teacher.role != "admin":
        statement = statement.where(Assessment.created_by_id == teacher.id)
    assessments = db.scalars(statement).all()
    return AssessmentListResponse(
        assessments=[
            {"id": assessment.id, "title": assessment.title, "status": assessment.status}
            for assessment in assessments
        ]
    )
