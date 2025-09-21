"""XWall Web Backend (FastAPI)

Provides:
- Auth: initialize superadmin, login, me
- Invites: create invite links, register via invite
- Audit: list submissions, approve/reject/toggle/comment

CORS is enabled; static frontend can be served from ../frontend/dist if built.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import orjson
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

import jwt
from passlib.context import CryptContext

from pydantic import BaseModel

from config import get_settings
from core.database import get_db


# Security helpers
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta_minutes: int) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.web.jwt_secret_key, algorithm=settings.web.jwt_algorithm)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Pydantic schemas
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    is_admin: bool
    is_superadmin: bool


class InviteCreateIn(BaseModel):
    expires_in_minutes: Optional[int] = 60


class RegisterViaInviteIn(BaseModel):
    token: str
    username: str
    password: str
    display_name: Optional[str] = None


def orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()


app = FastAPI(default_response_class=JSONResponse)


# CORS
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.web.cors_allow_origins,
    allow_credentials=_settings.web.cors_allow_credentials,
    allow_methods=_settings.web.cors_allow_methods,
    allow_headers=_settings.web.cors_allow_headers,
)


def get_current_user_from_headers(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.web.jwt_secret_key, algorithms=[settings.web.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


@app.on_event("startup")
async def on_startup():
    # Ensure DB is initialized
    await get_db()


@app.get("/health")
async def health():
    db = await get_db()
    ok = await db.health_check()
    return {"ok": ok}


# Auth endpoints
class SuperadminInitIn(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None


@app.get("/auth/has-superadmin")
async def has_superadmin() -> Dict[str, bool]:
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User
        result = await session.execute(select(User).where(User.is_superadmin == True).limit(1))
        return {"exists": result.scalar_one_or_none() is not None}


@app.post("/auth/init-superadmin", response_model=UserOut)
async def init_superadmin(body: SuperadminInitIn):
    """Initialize the very first superadmin. If any superadmin exists, forbid."""
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User

        exists_stmt = select(User).where(User.is_superadmin == True).limit(1)
        result = await session.execute(exists_stmt)
        exists = result.scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=400, detail="Superadmin already initialized")

        # Also forbid duplicate usernames
        result = await session.execute(select(User).where(User.username == body.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")

        user = User(
            username=body.username,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
            is_admin=True,
            is_superadmin=True,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        return UserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=user.is_admin,
            is_superadmin=user.is_superadmin,
        )


@app.post("/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User

        stmt = select(User).where(User.username == form_data.username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

        token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_superadmin": user.is_superadmin,
        }, get_settings().web.access_token_expires_minutes)
        return TokenResponse(access_token=token)


from fastapi import Header


@app.get("/auth/me", response_model=UserOut)
async def me(authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    user_id = int(payload.get("sub"))
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User

        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive")
        return UserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=user.is_admin,
            is_superadmin=user.is_superadmin,
        )


# Invite endpoints
@app.post("/invites/create")
async def create_invite(body: InviteCreateIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Only superadmin can create invites")

    db = await get_db()
    async with db.get_session() as session:
        from core.models import InviteToken
        from sqlalchemy import select
        import secrets

        token = secrets.token_urlsafe(32)
        expires_at = None
        if body.expires_in_minutes and body.expires_in_minutes > 0:
            expires_at = datetime.utcnow() + timedelta(minutes=body.expires_in_minutes)

        invite = InviteToken(
            token=token,
            created_by_user_id=int(payload["sub"]),
            expires_at=expires_at,
            is_active=True,
        )
        session.add(invite)
        await session.flush()
        return {"token": token, "expires_at": expires_at.isoformat() if expires_at else None}


@app.post("/auth/register-invite", response_model=UserOut)
async def register_via_invite(body: RegisterViaInviteIn):
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User, InviteToken

        # Validate token
        stmt = select(InviteToken).where(InviteToken.token == body.token)
        result = await session.execute(stmt)
        invite = result.scalar_one_or_none()
        if not invite or not invite.is_valid():
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        # Check username
        result = await session.execute(select(User).where(User.username == body.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Create admin user
        user = User(
            username=body.username,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
            is_admin=True,
            is_superadmin=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        invite.used_by_user_id = user.id
        invite.used_at = datetime.utcnow()
        invite.is_active = False

        return UserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=user.is_admin,
            is_superadmin=user.is_superadmin,
        )


# Audit endpoints
class SubmissionOut(BaseModel):
    id: int
    sender_id: str
    sender_nickname: Optional[str] = None
    group_name: Optional[str] = None
    status: str
    is_anonymous: bool
    is_safe: bool
    is_complete: bool
    publish_id: Optional[int] = None
    created_at: Optional[str] = None


@app.get("/audit/submissions", response_model=List[SubmissionOut])
async def list_submissions(status_filter: Optional[str] = None, limit: int = 50, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")

    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import Submission

        stmt = select(Submission).order_by(Submission.created_at.desc()).limit(limit)
        if status_filter:
            from sqlalchemy import and_
            stmt = select(Submission).where(Submission.status == status_filter).order_by(Submission.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        rows = result.scalars().all()
        out: List[SubmissionOut] = []
        for s in rows:
            out.append(SubmissionOut(
                id=s.id,
                sender_id=s.sender_id,
                sender_nickname=s.sender_nickname,
                group_name=s.group_name,
                status=s.status,
                is_anonymous=bool(s.is_anonymous),
                is_safe=bool(s.is_safe),
                is_complete=bool(s.is_complete),
                publish_id=s.publish_id,
                created_at=s.created_at.isoformat() if s.created_at else None,
            ))
        return out


class AuditActionIn(BaseModel):
    comment: Optional[str] = None


@app.post("/audit/{submission_id}/approve")
async def api_approve(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    from services.audit_service import AuditService
    service = AuditService()
    res = await service.approve(submission_id, operator_id=str(payload.get("username")))
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@app.post("/audit/{submission_id}/reject")
async def api_reject(submission_id: int, body: AuditActionIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    from services.audit_service import AuditService
    service = AuditService()
    res = await service.reject_with_message(submission_id, operator_id=str(payload.get("username")), extra=body.comment)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@app.post("/audit/{submission_id}/toggle-anon")
async def api_toggle_anon(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    from services.audit_service import AuditService
    service = AuditService()
    res = await service.toggle_anonymous(submission_id, operator_id=str(payload.get("username")))
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


@app.post("/audit/{submission_id}/comment")
async def api_comment(submission_id: int, body: AuditActionIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    from services.audit_service import AuditService
    service = AuditService()
    res = await service.add_comment(submission_id, operator_id=str(payload.get("username")), comment=(body.comment or ""))
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


# Optional: serve frontend if exists (prefer dist/ then raw frontend dir)
try:
    from fastapi.staticfiles import StaticFiles

    root = Path(__file__).resolve().parent.parent
    frontend_dist = root / "frontend" / "dist"
    frontend_src = root / "frontend"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    elif frontend_src.exists():
        app.mount("/", StaticFiles(directory=str(frontend_src), html=True), name="frontend-src")
except Exception:
    # static serving is optional
    pass


