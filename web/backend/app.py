"""Graffito Web Backend (FastAPI)

Provides:
- Auth: initialize superadmin, login, me
- Invites: create invite links, register via invite
- Audit: list submissions, approve/reject/toggle/comment

CORS is enabled; static frontend can be served from ../frontend/dist if built.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import asyncio

import orjson
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI, Depends, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import jwt
from passlib.context import CryptContext

from pydantic import BaseModel

from loguru import logger

from config import get_settings
from core.database import get_db
from services.audit_service import AuditService
from web.backend.decorators import execute_audit_action
import os
import sys
import socket
import platform
import re


# Security helpers
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta_minutes: int) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=expires_delta_minutes)
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
    # Extended for frontend compatibility
    user_id: Optional[str] = None  # mirrors username for admin pages
    role: Optional[str] = None     # 'admin' | 'user'


class InviteCreateIn(BaseModel):
    expires_in_minutes: Optional[int] = 60
    max_uses: Optional[int] = 1


class RegisterViaInviteIn(BaseModel):
    token: str
    username: str
    password: str
    display_name: Optional[str] = None


def orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()


settings = get_settings()


def _client_ip(request: Request) -> str:
    """Determine client IP respecting X-Forwarded-For when configured."""
    try:
        if settings.web.rate_limit.trust_forwarded_for:
            xff = request.headers.get("x-forwarded-for")
            if xff:
                return xff.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    except Exception:
        pass
    return request.client.host if request.client else "unknown"


_rl_conf = settings.web.rate_limit
_default_limits = ([_rl_conf.default] if getattr(_rl_conf, "default", None) else []) if getattr(_rl_conf, "enabled", False) else []
_limiter_storage_uri = getattr(_rl_conf, "storage_uri", None)

if _limiter_storage_uri:
    limiter = Limiter(key_func=_client_ip, storage_uri=_limiter_storage_uri, default_limits=_default_limits)
else:
    limiter = Limiter(key_func=_client_ip, default_limits=_default_limits)


app = FastAPI(default_response_class=JSONResponse)

if getattr(_rl_conf, "enabled", False):
    if _rl_conf.trust_forwarded_for:
        try:
            limiter.config.trust_forwarded_for = True
        except Exception:
            pass
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "请求过于频繁，请稍后再试"}
        ),
    )
    app.add_middleware(SlowAPIMiddleware)


def rl(limit: Optional[str]):
    """Return a rate limit decorator when enabled; otherwise exempt the endpoint."""
    if not getattr(settings.web.rate_limit, "enabled", False) or not limit:
        return limiter.exempt
    return limiter.limit(limit)

# Shared services (can be injected from main); if not injected, we'll create on startup
audit_service: Optional[AuditService] = None
_owns_audit_service: bool = False


def set_services(audit: AuditService) -> None:
    """Inject shared service instances created by the main app.

    If provided, web backend will not re-initialize or shutdown them.
    """
    global audit_service, _owns_audit_service
    audit_service = audit
    _owns_audit_service = False


# ============================================
# SSE (Server-Sent Events) 推送管理器
# ============================================
class SSEConnectionManager:
    """管理 SSE 客户端连接与事件推送"""
    
    def __init__(self):
        # 存储活跃连接: {user_id: [queue1, queue2, ...]}
        self._connections: Dict[str, List[asyncio.Queue]] = {}
    
    async def connect(self, user_id: str) -> asyncio.Queue:
        """添加新的客户端连接"""
        queue = asyncio.Queue(maxsize=100)
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(queue)
        return queue
    
    async def disconnect(self, user_id: str, queue: asyncio.Queue):
        """移除客户端连接"""
        if user_id in self._connections:
            try:
                self._connections[user_id].remove(queue)
                if not self._connections[user_id]:
                    del self._connections[user_id]
            except ValueError:
                pass
    
    async def send_to_user(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """向指定用户发送事件"""
        if user_id not in self._connections:
            return
        
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        dead_queues = []
        for queue in self._connections[user_id]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # 队列满了，移除这个连接
                dead_queues.append(queue)
            except Exception:
                dead_queues.append(queue)
        
        # 清理死连接
        for queue in dead_queues:
            await self.disconnect(user_id, queue)
    
    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """向所有连接的客户端广播事件"""
        for user_id in list(self._connections.keys()):
            await self.send_to_user(user_id, event_type, data)
    
    def get_active_connections_count(self) -> int:
        """获取活跃连接数"""
        return sum(len(queues) for queues in self._connections.values())


# 全局 SSE 管理器实例
sse_manager = SSEConnectionManager()


# CORS
_settings = get_settings()
# 简化 CORS：若配置了 frontend_origin，则仅允许该来源；否则回退至列表配置
try:
    _frontend_origin = getattr(_settings.web, 'frontend_origin', None)
except Exception:
    _frontend_origin = None
_allow_origins = [_frontend_origin] if _frontend_origin else _settings.web.cors_allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_settings.web.cors_allow_credentials,
    allow_methods=_settings.web.cors_allow_methods,
    allow_headers=_settings.web.cors_allow_headers,
)

# 静态资源与渲染图片目录
try:
    app.mount("/static", StaticFiles(directory="static", check_dir=False), name="static")
    # 受保护的静态资源（需要登录）：/data
    class AuthenticatedStaticFiles(StaticFiles):
        """
        受保护的静态文件服务，要求客户端提供有效的 JWT token
        
        验证方式优先级：
        1. Authorization header (推荐) - 通过 fetch API 请求图片资源时使用
        2. URL 参数 token/access_token (兼容) - 仅为兼容 EventSource 等无法设置 header 的场景
        
        前端优化说明：
        - 图片资源应使用 fetch + Authorization header 方式加载
        - URL 参数方式保留作为后向兼容，未来可能移除
        """
        async def __call__(self, scope, receive, send):
            # 仅处理 HTTP 请求
            if scope.get("type") != "http":
                await super().__call__(scope, receive, send)
                return

            # 优先从 Authorization 头获取 Bearer Token（推荐方式）
            auth_value: Optional[str] = None
            try:
                raw_headers = dict(scope.get("headers") or [])
                raw_auth = raw_headers.get(b"authorization")
                if raw_auth:
                    auth_value = raw_auth.decode()
            except Exception:
                auth_value = None

            # 后向兼容：从查询参数获取 token（仅用于无法设置 header 的场景，如 EventSource）
            if not auth_value:
                try:
                    from urllib.parse import parse_qs
                    qs = (scope.get("query_string") or b"").decode()
                    if qs:
                        q = parse_qs(qs)
                        token = (q.get("token") or q.get("access_token") or [None])[0]
                        if token:
                            auth_value = f"Bearer {token}"
                except Exception:
                    pass

            if not auth_value:
                resp = JSONResponse({"detail": "未认证"}, status_code=status.HTTP_401_UNAUTHORIZED)
                await resp(scope, receive, send)
                return

            # 复用现有的 JWT 校验逻辑
            try:
                get_current_user_from_headers(auth_value)
            except HTTPException as exc:
                resp = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
                await resp(scope, receive, send)
                return
            except Exception:
                resp = JSONResponse({"detail": "无效的登录凭证"}, status_code=status.HTTP_401_UNAUTHORIZED)
                await resp(scope, receive, send)
                return

            await super().__call__(scope, receive, send)

    app.mount("/data", AuthenticatedStaticFiles(directory="data", check_dir=False), name="data")
except Exception:
    pass


def get_current_user_from_headers(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")
    token = authorization.split(" ", 1)[1]
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.web.jwt_secret_key, algorithms=[settings.web.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的登录凭证")
    return payload


@app.on_event("startup")
@limiter.exempt
async def on_startup():
    # Ensure DB and Cache are initialized
    await get_db()
    
    # Initialize cache
    try:
        from core.cache_client import get_cache
        cache = await get_cache()
        logger.info(f"缓存客户端初始化成功: backend={cache.backend}, serializer={cache.serializer}")
    except Exception as e:
        logger.error(f"缓存初始化失败: {e}")
    
    # Initialize shared services for audit endpoints if not injected
    global audit_service, _owns_audit_service
    if audit_service is None:
        try:
            audit_service = AuditService()
            await audit_service.initialize()
            _owns_audit_service = True
        except Exception:
            pass


@app.on_event("shutdown")
async def on_shutdown():
    global audit_service, _owns_audit_service
    if _owns_audit_service and audit_service is not None:
        try:
            await audit_service.shutdown()
        except Exception:
            pass
    
    # Close cache
    try:
        from core.cache_client import close_cache
        await close_cache()
    except Exception:
        pass


@app.get("/health")
@limiter.exempt
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
@rl(getattr(settings.web.rate_limit, "init_superadmin", None))
async def init_superadmin(request: Request, body: SuperadminInitIn):
    """Initialize the very first superadmin. If any superadmin exists, forbid."""
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User

        exists_stmt = select(User).where(User.is_superadmin == True).limit(1)
        result = await session.execute(exists_stmt)
        exists = result.scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=400, detail="超级管理员已初始化")

        # Also forbid duplicate usernames
        result = await session.execute(select(User).where(User.username == body.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户名已存在")

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
@rl(getattr(settings.web.rate_limit, "login", None))
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User, AdminProfile

        stmt = select(User).where(User.username == form_data.username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

        token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_superadmin": user.is_superadmin,
        }, get_settings().web.access_token_expires_minutes)
        # update last_login on AdminProfile
        try:
            prof = (await session.execute(select(AdminProfile).where(AdminProfile.user_id == user.id))).scalar_one_or_none()
            now = datetime.now()
            if prof:
                prof.last_login = now
            else:
                # create a lightweight profile to track last_login only
                prof = AdminProfile(user_id=user.id, last_login=now)
                session.add(prof)
            await session.flush()
        except Exception:
            pass
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
            raise HTTPException(status_code=401, detail="用户已被禁用")
        # Simplified role model: admin | user
        role = "admin" if user.is_admin else "user"
        return UserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=user.is_admin,
            is_superadmin=user.is_superadmin,
            user_id=user.username,
            role=role,
        )


# Invite endpoints
@app.post("/invites/create")
@rl(getattr(settings.web.rate_limit, "create_invite", None))
async def create_invite(request: Request, body: InviteCreateIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    db = await get_db()
    async with db.get_session() as session:
        from core.models import InviteToken
        from sqlalchemy import select
        import secrets

        token = secrets.token_urlsafe(32)
        expires_at = None
        if body.expires_in_minutes and body.expires_in_minutes > 0:
            expires_at = datetime.now() + timedelta(minutes=body.expires_in_minutes)

        # 服务器端限制使用次数范围（1-1000）
        _max_uses = body.max_uses if body.max_uses is not None else 1
        if _max_uses < 1:
            _max_uses = 1
        if _max_uses > 1000:
            _max_uses = 1000

        invite = InviteToken(
            token=token,
            created_by_user_id=int(payload["sub"]),
            expires_at=expires_at,
            is_active=True,
            max_uses=_max_uses,
            uses_count=0,
        )
        session.add(invite)
        await session.flush()
        return {
            "token": token,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "max_uses": invite.max_uses,
        }


@app.post("/auth/register-invite", response_model=UserOut)
@rl(getattr(settings.web.rate_limit, "register_invite", None))
async def register_via_invite(request: Request, body: RegisterViaInviteIn):
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User, InviteToken

        # Validate token（去除首尾空白，避免复制粘贴导致的误判）
        token_value = (body.token or "").strip()
        stmt = select(InviteToken).where(InviteToken.token == token_value)
        result = await session.execute(stmt)
        invite = result.scalar_one_or_none()
        if not invite or not invite.is_valid():
            raise HTTPException(status_code=400, detail="邀请码无效或已过期")

        # Check username
        result = await session.execute(select(User).where(User.username == body.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户名已存在")

        # Create normal user (reviewer)
        user = User(
            username=body.username,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
            is_admin=False,
            is_superadmin=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # 增加使用次数并按上限失效
        invite.uses_count = (invite.uses_count or 0) + 1
        if invite.max_uses is None:
            invite.used_by_user_id = user.id
            invite.used_at = datetime.now()
            invite.is_active = False
        else:
            if invite.uses_count >= (invite.max_uses or 1):
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
    processed_by: Optional[str] = None
    created_at: Optional[str] = None
    summary: Optional[str] = None  # AI生成的投稿总结


@app.get("/audit/submissions", response_model=List[SubmissionOut])
async def list_submissions(status_filter: Optional[str] = None, limit: int = 50, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    # Any authenticated active user can review

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
            # 提取 summary
            summary = None
            if s.llm_result and isinstance(s.llm_result, dict):
                summary = s.llm_result.get('summary', '')
                # 如果太长，截断到100字符
                if summary and len(summary) > 100:
                    summary = summary[:97] + '...'
            
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
                processed_by=s.processed_by,
                created_at=s.created_at.isoformat() if s.created_at else None,
                summary=summary,
            ))
        return out


class AuditActionIn(BaseModel):
    comment: Optional[str] = None


@app.post("/audit/{submission_id}/approve")
async def api_approve(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.approve,
        send_sse=True,
        sse_event_type="submission_approved",
        notify_submission_update=notify_submission_update
    )


@app.post("/audit/{submission_id}/reject")
async def api_reject(submission_id: int, body: AuditActionIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.reject_with_message,
        extra=body.comment,
        send_sse=True,
        sse_event_type="submission_rejected",
        notify_submission_update=notify_submission_update
    )


@app.post("/audit/{submission_id}/toggle-anon")
async def api_toggle_anon(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.toggle_anonymous
    )


@app.post("/audit/{submission_id}/comment")
async def api_comment(submission_id: int, body: AuditActionIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.add_comment,
        extra=body.comment or ""
    )


# 扩展审核操作
@app.post("/audit/{submission_id}/hold")
async def api_hold(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.hold
    )


@app.post("/audit/{submission_id}/delete")
async def api_delete(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.delete
    )


@app.post("/audit/{submission_id}/approve-immediate")
async def api_approve_immediate(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.approve_immediate,
        send_sse=True,
        sse_event_type="submission_published",
        notify_submission_update=notify_submission_update
    )


@app.post("/audit/{submission_id}/rerender")
async def api_rerender(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.rerender
    )


@app.post("/audit/{submission_id}/refresh")
async def api_refresh(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.refresh
    )


@app.post("/audit/{submission_id}/reply")
async def api_reply(submission_id: int, body: AuditActionIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.reply_to_sender,
        extra=body.comment
    )


@app.post("/audit/{submission_id}/blacklist")
async def api_blacklist(submission_id: int, body: AuditActionIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    return await execute_audit_action(
        submission_id,
        str(payload.get("username")),
        audit_service.blacklist,
        extra=body.comment
    )


# 投稿详情
class SubmissionDetailOut(BaseModel):
    id: int
    sender_id: str
    sender_nickname: Optional[str] = None
    group_name: Optional[str] = None
    status: str
    is_anonymous: bool
    is_safe: bool
    is_complete: bool
    publish_id: Optional[int] = None
    # 前端历史数据中 raw_content/processed_content 可能是 list
    raw_content: Optional[Any] = None
    processed_content: Optional[Any] = None
    llm_result: Optional[Any] = None
    rendered_images: Optional[List[str]] = None
    comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    processed_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    processed_at: Optional[str] = None
    published_at: Optional[str] = None


@app.get("/audit/{submission_id}/detail", response_model=SubmissionDetailOut)
async def get_submission_detail(submission_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    # Any authenticated active user can review
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import Submission
        
        stmt = select(Submission).where(Submission.id == submission_id)
        result = await session.execute(stmt)
        submission = result.scalar_one_or_none()
        
        if not submission:
            raise HTTPException(status_code=404, detail="投稿未找到")
            
        return SubmissionDetailOut(
            id=submission.id,
            sender_id=submission.sender_id,
            sender_nickname=submission.sender_nickname,
            group_name=submission.group_name,
            status=submission.status,
            is_anonymous=bool(submission.is_anonymous),
            is_safe=bool(submission.is_safe),
            is_complete=bool(submission.is_complete),
            publish_id=submission.publish_id,
            raw_content=submission.raw_content,
            processed_content=submission.processed_content,
            llm_result=submission.llm_result,
            rendered_images=submission.rendered_images,
            comment=submission.comment,
            rejection_reason=submission.rejection_reason,
            processed_by=submission.processed_by,
            created_at=submission.created_at.isoformat() if submission.created_at else None,
            updated_at=submission.updated_at.isoformat() if submission.updated_at else None,
            processed_at=submission.processed_at.isoformat() if submission.processed_at else None,
            published_at=submission.published_at.isoformat() if submission.published_at else None,
        )


class PlatformCommentOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_avatar: Optional[str] = None
    content: str
    like_count: int
    reply_count: int
    created_at: Optional[int] = None


class PlatformCommentsOut(BaseModel):
    success: bool
    platform: str
    comments: List[PlatformCommentOut]
    total: int
    page: int
    page_size: int
    message: Optional[str] = None


@app.get("/audit/{submission_id}/platform-comments")
async def get_submission_platform_comments(
    submission_id: int, 
    page: int = 1,
    page_size: int = 20,
    use_cache: bool = True,
    authorization: Optional[str] = Header(default=None)
):
    """获取投稿在发布平台的评论列表（支持缓存和并行获取）"""
    payload = get_current_user_from_headers(authorization)
    
    from core.models import PublishRecord, Submission
    from core.enums import SubmissionStatus
    from publishers.loader import get_publisher
    from core.data_cache_service import DataCacheService
    from sqlalchemy import select
    
    db = await get_db()
    async with db.get_session() as session:
        # 使用缓存获取投稿
        submission = await DataCacheService.get_submission_by_id(
            submission_id, session, use_cache=use_cache
        )
        
        if not submission:
            raise HTTPException(status_code=404, detail="投稿未找到")
        
        # 检查状态（处理字典和对象两种情况）
        if isinstance(submission, dict):
            status = submission.get('status')
        else:
            status = submission.status
            
        if status != SubmissionStatus.PUBLISHED.value:
            raise HTTPException(status_code=400, detail="投稿尚未发布，无法获取评论")
        
        # 查询发布记录（不缓存，因为 publisher 需要完整对象）
        stmt = select(PublishRecord).where(
            PublishRecord.submission_ids.contains([submission_id])
        ).order_by(PublishRecord.created_at.desc())
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        if not records:
            raise HTTPException(status_code=404, detail="未找到发布记录")
        
        # 过滤出成功的发布记录
        success_records = [record for record in records if record.is_success]
        
        if not success_records:
            return {
                "success": False,
                "message": "没有成功的发布记录",
                "platforms": []
            }
        
        # 定义单个平台评论获取函数（带缓存）
        async def fetch_comments_for_record(record):
            """并行获取单个平台的评论（带缓存）"""
            try:
                record_id = record.id
                platform = record.platform
                
                # 尝试从缓存获取评论
                cached_comments = await DataCacheService.get_platform_comments(
                    record_id, page, page_size, use_cache=use_cache
                )
                
                if cached_comments:
                    logger.debug(f"使用缓存的评论: record_id={record_id}, platform={platform}")
                    return cached_comments
                
                # 缓存未命中，调用 publisher API
                publisher = get_publisher(platform)
                if not publisher:
                    logger.warning(f"未找到平台发布器: {platform}")
                    return None
                
                # 调用 publisher 获取评论
                result = await publisher.get_platform_comments(record, page, page_size)
                
                if result.get('success'):
                    comment_data = {
                        'platform': result.get('platform', platform),
                        'comments': result.get('comments', []),
                        'total': result.get('total', 0),
                        'page': result.get('page', page),
                        'page_size': result.get('page_size', page_size)
                    }
                    
                    # 写入缓存
                    await DataCacheService.set_platform_comments(
                        record_id, page, page_size, comment_data
                    )
                    
                    logger.info(f"获取评论成功: record_id={record_id}, platform={platform}, total={comment_data['total']}")
                    return comment_data
                else:
                    logger.warning(f"获取评论失败: platform={platform}, message={result.get('message')}")
                    return None
                    
            except Exception as e:
                logger.error(f"获取平台评论异常: platform={record.platform}, error={e}", exc_info=True)
                return None
        
        # 并行获取所有平台的评论
        comment_tasks = [fetch_comments_for_record(record) for record in success_records]
        results = await asyncio.gather(*comment_tasks, return_exceptions=True)
        
        # 过滤出有效结果
        all_comments = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"并行获取评论时发生异常: {result}")
                continue
            if result:
                all_comments.append(result)
        
        if not all_comments:
            return {
                "success": False,
                "message": "未能获取任何平台的评论",
                "platforms": []
            }
        
        return {
            "success": True,
            "platforms": all_comments
        }


# 用户管理相关API
class UserDetailOut(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    qq_level: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    login_days: Optional[str] = None
    status: Optional[str] = None
    card: Optional[str] = None
    area: Optional[str] = None
    title: Optional[str] = None
    stats: Optional[Dict[str, int]] = None


class BlacklistUserIn(BaseModel):
    user_id: str
    group_name: str
    reason: Optional[str] = None
    expires_hours: Optional[int] = None  # 可选的过期时间（小时）


class BlacklistOut(BaseModel):
    id: int
    user_id: str
    group_name: str
    reason: Optional[str] = None
    operator_id: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool


@app.get("/management/blacklist", response_model=List[BlacklistOut])
async def get_blacklist(authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import BlackList
        
        stmt = select(BlackList).order_by(BlackList.created_at.desc())
        result = await session.execute(stmt)
        blacklist_entries = result.scalars().all()
        
        return [
            BlacklistOut(
                id=entry.id,
                user_id=entry.user_id,
                group_name=entry.group_name,
                reason=entry.reason,
                operator_id=entry.operator_id,
                created_at=entry.created_at.isoformat() if entry.created_at else "",
                expires_at=entry.expires_at.isoformat() if entry.expires_at else None,
                is_active=entry.is_active()
            )
            for entry in blacklist_entries
        ]


@app.post("/management/blacklist")
async def add_to_blacklist(body: BlacklistUserIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import BlackList
        from datetime import timedelta
        
        # 检查是否已存在
        stmt = select(BlackList).where(
            BlackList.user_id == body.user_id,
            BlackList.group_name == body.group_name
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="用户已在黑名单中")
        
        expires_at = None
        if body.expires_hours and body.expires_hours > 0:
            expires_at = datetime.now() + timedelta(hours=body.expires_hours)
        
        blacklist_entry = BlackList(
            user_id=body.user_id,
            group_name=body.group_name,
            reason=body.reason,
            operator_id=str(payload.get("username")),
            expires_at=expires_at
        )
        session.add(blacklist_entry)
        await session.commit()
        
        return {"success": True, "message": "用户已加入黑名单"}


@app.delete("/management/blacklist/{blacklist_id}")
async def remove_from_blacklist(blacklist_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select, delete
        from core.models import BlackList
        
        # 先查找记录
        stmt = select(BlackList).where(BlackList.id == blacklist_id)
        result = await session.execute(stmt)
        blacklist_entry = result.scalar_one_or_none()
        
        if not blacklist_entry:
            raise HTTPException(status_code=404, detail="黑名单记录未找到")
        
        # 删除记录
        delete_stmt = delete(BlackList).where(BlackList.id == blacklist_id)
        await session.execute(delete_stmt)
        await session.commit()
        
        return {"success": True, "message": "已从黑名单中移除"}


@app.get("/management/users/{user_id}/detail", response_model=UserDetailOut)
async def get_user_detail(user_id: str, submission_id: Optional[int] = None, authorization: Optional[str] = Header(default=None)):
    """获取用户详情（通过 NapCat API 和投稿统计）
    
    Args:
        user_id: 用户 QQ 号
        submission_id: 可选的投稿ID，用于获取对应的 receiver_id
        authorization: 认证令牌
    """
    payload = get_current_user_from_headers(authorization)
    
    # 获取用户的投稿信息以确定 receiver_id
    receiver_id = None
    if submission_id:
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            from core.models import Submission
            
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if submission:
                receiver_id = submission.receiver_id
    
    # 如果没有提供 submission_id，尝试从用户的任意投稿中获取 receiver_id
    if not receiver_id:
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            from core.models import Submission
            
            stmt = select(Submission).where(Submission.sender_id == user_id).limit(1)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if submission:
                receiver_id = submission.receiver_id
    
    # 调用审核服务获取用户详细信息
    if receiver_id and audit_service:
        result = await audit_service._get_user_info_from_napcat(user_id, receiver_id)
    else:
        result = {}
    
    # 获取用户的投稿统计
    stats = {"total": 0, "published": 0, "rejected": 0, "pending": 0}
    try:
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select, func
            from core.models import Submission
            from core.enums import SubmissionStatus
            
            # 总数
            total_stmt = select(func.count(Submission.id)).where(Submission.sender_id == user_id)
            total_result = await session.execute(total_stmt)
            stats["total"] = total_result.scalar() or 0
            
            # 已发布
            published_stmt = select(func.count(Submission.id)).where(
                Submission.sender_id == user_id,
                Submission.status == SubmissionStatus.PUBLISHED.value
            )
            published_result = await session.execute(published_stmt)
            stats["published"] = published_result.scalar() or 0
            
            # 已拒绝
            rejected_stmt = select(func.count(Submission.id)).where(
                Submission.sender_id == user_id,
                Submission.status == SubmissionStatus.REJECTED.value
            )
            rejected_result = await session.execute(rejected_stmt)
            stats["rejected"] = rejected_result.scalar() or 0
            
            # 待处理
            pending_stmt = select(func.count(Submission.id)).where(
                Submission.sender_id == user_id,
                Submission.status.in_([
                    SubmissionStatus.PENDING.value,
                    SubmissionStatus.PROCESSING.value,
                    SubmissionStatus.WAITING.value
                ])
            )
            pending_result = await session.execute(pending_stmt)
            stats["pending"] = pending_result.scalar() or 0
    except Exception as e:
        logger.warning(f"获取用户投稿统计失败: {e}")
    
    # 获取昵称（优先从 NapCat 获取，否则从最近投稿获取）
    nickname = result.get('nickname')
    if not nickname:
        try:
            db = await get_db()
            async with db.get_session() as session:
                from sqlalchemy import select
                from core.models import Submission
                
                stmt = select(Submission).where(Submission.sender_id == user_id).order_by(Submission.created_at.desc()).limit(1)
                result_sub = await session.execute(stmt)
                latest_sub = result_sub.scalar_one_or_none()
                
                if latest_sub and latest_sub.sender_nickname:
                    nickname = latest_sub.sender_nickname
        except Exception:
            pass
    
    # 状态码映射
    status_map = {
        10: "离线",
        20: "在线",
        30: "离开",
        40: "隐身",
        50: "忙碌",
        60: "Q我吧",
        70: "请勿打扰"
    }
    status_code = result.get('status')
    status_text = status_map.get(status_code, f"未知({status_code})") if status_code is not None else "未知"
    
    # 性别映射
    sex_map = {
        "male": "男",
        "female": "女",
        "unknown": "未知"
    }
    sex_value = result.get('sex', 'unknown')
    sex_text = sex_map.get(sex_value, sex_value)
    
    return UserDetailOut(
        user_id=user_id,
        nickname=nickname or result.get('nickname'),
        qq_level=str(result.get('qqLevel', '未知')),
        age=str(result.get('age', '未知')),
        sex=sex_text,
        login_days=str(result.get('login_days', '未知')),
        status=status_text,
        card=result.get('card', ''),
        area=result.get('area', ''),
        title=result.get('title', ''),
        stats=stats
    )


# 管理员管理 API（与前端 UserManagement.vue 对接）
class AdminOut(BaseModel):
    id: int
    user_id: str
    nickname: Optional[str] = None
    role: str
    permissions: List[str] = []
    is_active: bool
    last_login: Optional[str] = None
    created_at: Optional[str] = None


class AdminCreateIn(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    notes: Optional[str] = None


class AdminUpdateIn(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    notes: Optional[str] = None


@app.get("/management/admins", response_model=List[AdminOut])
async def list_admins(authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select, or_
        from core.models import User, AdminProfile

        users = (
            await session.execute(
                select(User).where(or_(User.is_admin == True, User.is_superadmin == True))
            )
        ).scalars().all()
        profiles = (await session.execute(select(AdminProfile))).scalars().all() if users else []
        uid_to_profile = {p.user_id: p for p in profiles}

        out: List[AdminOut] = []
        for u in users:
            p = uid_to_profile.get(u.id)
            role = "admin"
            last_login = p.last_login.isoformat() if p and p.last_login else None
            created_at = u.created_at.isoformat() if u.created_at else None
            out.append(AdminOut(
                id=u.id,
                user_id=u.username,
                nickname=p.nickname if p and p.nickname else (u.display_name or None),
                role=role,
                permissions=[],
                is_active=bool(u.is_active),
                last_login=last_login,
                created_at=created_at,
            ))
        return out


@app.post("/management/admins")
async def create_admin(body: AdminCreateIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User, AdminProfile

        # 仅允许为已注册用户授予管理员角色
        target_username = body.user_id
        u = (await session.execute(select(User).where(User.username == target_username))).scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="用户不存在，请先邀请/注册用户")

        # 标记为管理员
        u.is_admin = True
        u.is_superadmin = False

        # 创建/更新 AdminProfile
        prof = (await session.execute(select(AdminProfile).where(AdminProfile.user_id == u.id))).scalar_one_or_none()
        if not prof:
            prof = AdminProfile(user_id=u.id)
            session.add(prof)
        prof.nickname = body.nickname
        # Simplified role/permissions model
        prof.role = "admin"
        prof.permissions = []
        prof.notes = body.notes

        await session.flush()
        return {"success": True, "message": "管理员创建成功"}


@app.put("/management/admins/{admin_id}")
async def update_admin(admin_id: int, body: AdminUpdateIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User, AdminProfile

        u = (await session.execute(select(User).where(User.id == admin_id))).scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="管理员未找到")

        # 更新基本信息（简化角色/权限）
        u.is_admin = True
        u.is_superadmin = False
        if body.nickname is not None:
            u.display_name = body.nickname or u.display_name

        prof = (await session.execute(select(AdminProfile).where(AdminProfile.user_id == u.id))).scalar_one_or_none()
        if not prof:
            prof = AdminProfile(user_id=u.id)
            session.add(prof)
        prof.nickname = body.nickname if body.nickname is not None else prof.nickname
        prof.role = "admin"
        prof.permissions = []
        prof.notes = body.notes if body.notes is not None else prof.notes

        await session.flush()
        return {"success": True, "message": "管理员已更新"}


class AdminStatusIn(BaseModel):
    is_active: bool


@app.patch("/management/admins/{admin_id}/status")
async def toggle_admin_status(admin_id: int, body: AdminStatusIn, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import User

        u = (await session.execute(select(User).where(User.id == admin_id))).scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="管理员未找到")

        # 防止用户禁用自身
        if u.id == int(payload.get("sub")):
            raise HTTPException(status_code=400, detail="不能禁用自己")

        u.is_active = bool(body.is_active)
        await session.flush()
        return {"success": True, "message": "状态已更新"}


@app.delete("/management/admins/{admin_id}")
async def delete_admin(admin_id: int, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select, delete
        from core.models import User, AdminProfile

        u = (await session.execute(select(User).where(User.id == admin_id))).scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="管理员未找到")
        # 防止删除自己
        if u.id == int(payload.get("sub")):
            raise HTTPException(status_code=400, detail="不能删除自己")

        # 取消管理员权限，但保留用户账号
        u.is_admin = False
        u.is_superadmin = False
        await session.execute(delete(AdminProfile).where(AdminProfile.user_id == u.id))
        await session.flush()
        return {"success": True, "message": "管理员已删除"}


# 暂存区管理API
class StoredPostOut(BaseModel):
    id: int
    submission_id: int
    group_name: str
    publish_id: int
    priority: int
    created_at: str
    submission: Optional[SubmissionOut] = None


@app.get("/management/stored-posts", response_model=List[StoredPostOut])
async def get_stored_posts(group_name: Optional[str] = None, authorization: Optional[str] = Header(default=None)):
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import StoredPost, Submission
        
        stmt = select(StoredPost).order_by(StoredPost.priority.desc(), StoredPost.created_at)
        if group_name:
            stmt = stmt.where(StoredPost.group_name == group_name)
        
        result = await session.execute(stmt)
        stored_posts = result.scalars().all()
        
        # 获取对应的投稿信息
        submission_ids = [sp.submission_id for sp in stored_posts]
        if submission_ids:
            sub_stmt = select(Submission).where(Submission.id.in_(submission_ids))
            sub_result = await session.execute(sub_stmt)
            submissions = {s.id: s for s in sub_result.scalars().all()}
        else:
            submissions = {}
        
        return [
            StoredPostOut(
                id=sp.id,
                submission_id=sp.submission_id,
                group_name=sp.group_name,
                publish_id=sp.publish_id,
                priority=sp.priority,
                created_at=sp.created_at.isoformat() if sp.created_at else "",
                submission=SubmissionOut(
                    id=submissions[sp.submission_id].id,
                    sender_id=submissions[sp.submission_id].sender_id,
                    sender_nickname=submissions[sp.submission_id].sender_nickname,
                    group_name=submissions[sp.submission_id].group_name,
                    status=submissions[sp.submission_id].status,
                    is_anonymous=bool(submissions[sp.submission_id].is_anonymous),
                    is_safe=bool(submissions[sp.submission_id].is_safe),
                    is_complete=bool(submissions[sp.submission_id].is_complete),
                    publish_id=submissions[sp.submission_id].publish_id,
                    processed_by=submissions[sp.submission_id].processed_by,
                    created_at=submissions[sp.submission_id].created_at.isoformat() if submissions[sp.submission_id].created_at else None,
                ) if sp.submission_id in submissions else None
            )
            for sp in stored_posts
        ]


@app.post("/management/stored-posts/publish")
async def publish_stored_posts(group_name: str, authorization: Optional[str] = Header(default=None)):
    
    try:
        from services.submission_service import SubmissionService
        service = SubmissionService()
        success = await service.publish_stored_posts(group_name)
        
        if success:
            return {"success": True, "message": f"暂存区 {group_name} 发布成功"}
        else:
            return {"success": False, "message": "发布失败"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发布失败: {str(e)}")


@app.delete("/management/stored-posts/clear")
async def clear_stored_posts(group_name: str, authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import delete
        from core.models import StoredPost
        
        delete_stmt = delete(StoredPost).where(StoredPost.group_name == group_name)
        await session.execute(delete_stmt)
        await session.commit()
        
        return {"success": True, "message": f"暂存区 {group_name} 已清空"}


# 统计数据API
class StatsOut(BaseModel):
    total_submissions: int
    pending_submissions: int
    approved_submissions: int
    published_submissions: int
    rejected_submissions: int
    stored_posts_count: int
    blacklisted_users: int
    pending_feedbacks: int
    active_groups: List[str]
    
    # 最近7天的数据
    recent_submissions: Dict[str, int]  # 日期 -> 数量（7天）
    # 最近30天的数据
    recent_30d_submissions: Dict[str, int]  # 日期 -> 数量（30天）


@app.get("/management/stats", response_model=StatsOut)
async def get_stats(authorization: Optional[str] = Header(default=None)):
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select, func, and_
        from core.models import Submission, StoredPost, BlackList
        from core.enums import SubmissionStatus
        
        # 基础统计
        total_stmt = select(func.count(Submission.id))
        total_result = await session.execute(total_stmt)
        total_submissions = total_result.scalar() or 0
        
        pending_stmt = select(func.count(Submission.id)).where(
            Submission.status.in_([SubmissionStatus.PENDING.value, SubmissionStatus.PROCESSING.value, SubmissionStatus.WAITING.value])
        )
        pending_result = await session.execute(pending_stmt)
        pending_submissions = pending_result.scalar() or 0
        
        approved_stmt = select(func.count(Submission.id)).where(Submission.status == SubmissionStatus.APPROVED.value)
        approved_result = await session.execute(approved_stmt)
        approved_submissions = approved_result.scalar() or 0
        
        published_stmt = select(func.count(Submission.id)).where(Submission.status == SubmissionStatus.PUBLISHED.value)
        published_result = await session.execute(published_stmt)
        published_submissions = published_result.scalar() or 0
        
        rejected_stmt = select(func.count(Submission.id)).where(Submission.status == SubmissionStatus.REJECTED.value)
        rejected_result = await session.execute(rejected_stmt)
        rejected_submissions = rejected_result.scalar() or 0
        
        stored_stmt = select(func.count(StoredPost.id))
        stored_result = await session.execute(stored_stmt)
        stored_posts_count = stored_result.scalar() or 0
        
        blacklist_stmt = select(func.count(BlackList.id))
        blacklist_result = await session.execute(blacklist_stmt)
        blacklisted_users = blacklist_result.scalar() or 0
        
        # 待处理反馈
        from core.models import Feedback
        feedback_stmt = select(func.count(Feedback.id)).where(Feedback.status == 'pending')
        feedback_result = await session.execute(feedback_stmt)
        pending_feedbacks = feedback_result.scalar() or 0
        
        # 活跃群组
        groups_stmt = select(Submission.group_name).distinct().where(Submission.group_name.is_not(None))
        groups_result = await session.execute(groups_stmt)
        active_groups = [g for g in groups_result.scalars().all() if g]
        
        # 最近30天的投稿数据（一次查询，前端同时需要 7/30 天）
        from datetime import timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_30_stmt = select(
            func.date(Submission.created_at).label('date'),
            func.count(Submission.id).label('count')
        ).where(
            Submission.created_at >= thirty_days_ago
        ).group_by(func.date(Submission.created_at))

        recent_30_result = await session.execute(recent_30_stmt)
        recent_30_rows = recent_30_result.all()

        # 构建 30 天完整日期 -> 数量 字典，缺失日期补 0
        def _normalize_date(v) -> str:
            if isinstance(v, str):
                return v
            if hasattr(v, "strftime") and v is not None:
                return v.strftime('%Y-%m-%d')
            return str(v) if v is not None else ""

        raw_map: Dict[str, int] = {}
        for row in recent_30_rows:
            date_str = _normalize_date(getattr(row, 'date', None))
            raw_map[date_str] = int(getattr(row, 'count', 0) or 0)

        # 生成连续 30 天与 7 天的序列
        today = datetime.now().date()
        recent_30d_submissions: Dict[str, int] = {}
        recent_submissions: Dict[str, int] = {}
        for i in range(30):
            d = today - timedelta(days=29 - i)
            key = d.strftime('%Y-%m-%d')
            recent_30d_submissions[key] = int(raw_map.get(key, 0))
            # 同时构建最近7天（最后7个点）
            if i >= 23:  # 30-7 = 23
                recent_submissions[key] = int(raw_map.get(key, 0))

        return StatsOut(
            total_submissions=total_submissions,
            pending_submissions=pending_submissions,
            approved_submissions=approved_submissions,
            published_submissions=published_submissions,
            rejected_submissions=rejected_submissions,
            stored_posts_count=stored_posts_count,
            blacklisted_users=blacklisted_users,
            pending_feedbacks=pending_feedbacks,
            active_groups=active_groups,
            recent_submissions=recent_submissions,
            recent_30d_submissions=recent_30d_submissions,
        )



# 系统状态API（管理员可访问）
class SystemStatusOut(BaseModel):
    system: Dict[str, Any]
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    swap: Dict[str, Any]
    disks: List[Dict[str, Any]]
    network: Dict[str, Any]
    process: Dict[str, Any]
    timestamp: str


# 日志管理 API（仅 superadmin）
class LogEntry(BaseModel):
    timestamp: str
    level: str
    location: str  # name:function:line
    message: str


class LogsOut(BaseModel):
    logs: List[LogEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


@app.get("/management/system/status", response_model=SystemStatusOut)
async def get_system_status(authorization: Optional[str] = Header(default=None)):
    payload = get_current_user_from_headers(authorization)

    try:
        import psutil  # type: ignore
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器缺少 psutil 依赖，请安装后重试")

    # CPU 信息
    try:
        cpu_percent = float(psutil.cpu_percent(interval=None))
        per_cpu_percent = [float(x) for x in psutil.cpu_percent(interval=None, percpu=True)]
    except Exception:
        cpu_percent = 0.0
        per_cpu_percent = []

    try:
        load_avg = os.getloadavg()  # type: ignore[attr-defined]
        load_avg_out: Optional[List[float]] = [float(x) for x in load_avg]
    except Exception:
        load_avg_out = None

    # 内存信息
    vm = psutil.virtual_memory()
    mem_info = {
        "total": int(getattr(vm, "total", 0)),
        "available": int(getattr(vm, "available", 0)),
        "used": int(getattr(vm, "used", 0)),
        "percent": float(getattr(vm, "percent", 0.0)),
        "free": int(getattr(vm, "free", 0)),
        "buffers": int(getattr(vm, "buffers", 0) or 0),
        "cached": int(getattr(vm, "cached", 0) or 0),
    }

    # 交换内存
    sm = psutil.swap_memory()
    swap_info = {
        "total": int(getattr(sm, "total", 0)),
        "used": int(getattr(sm, "used", 0)),
        "free": int(getattr(sm, "free", 0)),
        "percent": float(getattr(sm, "percent", 0.0)),
        "sin": int(getattr(sm, "sin", 0) or 0),
        "sout": int(getattr(sm, "sout", 0) or 0),
    }

    # 磁盘信息
    disks: List[Dict[str, Any]] = []
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            total = int(getattr(usage, "total", 0))
            if total <= 0:
                continue
            disks.append({
                "device": getattr(part, "device", None) or part.mountpoint,
                "mountpoint": getattr(part, "mountpoint", ""),
                "fstype": getattr(part, "fstype", None),
                "total": total,
                "used": int(getattr(usage, "used", 0)),
                "free": int(getattr(usage, "free", 0)),
                "percent": float(getattr(usage, "percent", 0.0)),
            })
    except Exception:
        pass

    # 网络
    try:
        nio = psutil.net_io_counters()
        net_info = {
            "bytes_sent": int(getattr(nio, "bytes_sent", 0)),
            "bytes_recv": int(getattr(nio, "bytes_recv", 0)),
            "packets_sent": int(getattr(nio, "packets_sent", 0)),
            "packets_recv": int(getattr(nio, "packets_recv", 0)),
            "errin": int(getattr(nio, "errin", 0)),
            "errout": int(getattr(nio, "errout", 0)),
            "dropin": int(getattr(nio, "dropin", 0)),
            "dropout": int(getattr(nio, "dropout", 0)),
        }
    except Exception:
        net_info = {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0}

    # 进程
    try:
        proc = psutil.Process(os.getpid())
        pmem = proc.memory_info()
        proc_info = {
            "pid": proc.pid,
            "cpu_percent": float(proc.cpu_percent(interval=None) or 0.0),
            "memory_rss": int(getattr(pmem, "rss", 0)),
            "memory_vms": int(getattr(pmem, "vms", 0)),
            "open_files": len(proc.open_files() or []),
            "num_threads": int(proc.num_threads() or 0),
        }
    except Exception:
        proc_info = {"pid": os.getpid(), "cpu_percent": 0.0, "memory_rss": 0, "memory_vms": 0}

    # 系统
    try:
        boot_ts = getattr(psutil, "boot_time", lambda: None)()
        boot_time_iso = datetime.fromtimestamp(boot_ts).isoformat() if boot_ts else None
        uptime_seconds = int((datetime.now().timestamp() - boot_ts)) if boot_ts else None
    except Exception:
        boot_time_iso = None
        uptime_seconds = None

    system_info = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version.split(" ")[0],
        "hostname": socket.gethostname(),
        "boot_time": boot_time_iso,
        "uptime_seconds": uptime_seconds,
    }

    return SystemStatusOut(
        system=system_info,
        cpu={
            "physical_cores": int(getattr(psutil, "cpu_count", lambda logical=False: 0)(logical=False) or 0),
            "total_cores": int(getattr(psutil, "cpu_count", lambda logical=True: 0)(logical=True) or 0),
            "cpu_percent": cpu_percent,
            "per_cpu_percent": per_cpu_percent,
            "load_avg": load_avg_out,
        },
        memory=mem_info,
        swap=swap_info,
        disks=disks,
        network=net_info,
        process=proc_info,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/management/logs", response_model=LogsOut)
async def get_logs(
    date: Optional[str] = None,  # 日期过滤，格式: YYYY-MM-DD
    level: Optional[str] = None,  # 日志级别过滤: DEBUG|INFO|WARNING|ERROR|CRITICAL
    page: int = 1,
    page_size: int = 100,
    search: Optional[str] = None,  # 关键词搜索
    order: Optional[str] = "desc",  # 排序方式: asc|desc
    authorization: Optional[str] = Header(default=None)
):
    """获取系统日志（仅超级管理员）"""
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    
    import re
    from pathlib import Path
    
    # 确定要读取的日志文件
    logs_dir = Path("data/logs")
    if not logs_dir.exists():
        return LogsOut(logs=[], total=0, page=page, page_size=page_size, has_more=False)
    
    # 如果指定了日期，只读取该日期的日志
    if date:
        try:
            # 验证日期格式
            datetime.strptime(date, "%Y-%m-%d")
            log_files = [logs_dir / f"graffito_{date}.log"]
            log_files = [f for f in log_files if f.exists()]
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")
    else:
        # 否则读取所有日志文件，按日期倒序
        log_files = sorted(logs_dir.glob("graffito_*.log"), reverse=True)
    
    if not log_files:
        return LogsOut(logs=[], total=0, page=page, page_size=page_size, has_more=False)
    
    # 日志格式: {time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}
    log_pattern = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*'
        r'(?P<level>\w+)\s*\|\s*'
        r'(?P<location>.+?)\s*-\s*'
        r'(?P<message>.*)$'
    )
    
    all_logs: List[LogEntry] = []
    
    # 读取日志文件
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    match = log_pattern.match(line)
                    if match:
                        log_level = match.group('level').strip()
                        log_message = match.group('message').strip()
                        
                        # 日志级别过滤
                        if level and log_level.upper() != level.upper():
                            continue
                        
                        # 关键词搜索
                        if search and search.lower() not in log_message.lower():
                            continue
                        
                        all_logs.append(LogEntry(
                            timestamp=match.group('timestamp'),
                            level=log_level,
                            location=match.group('location').strip(),
                            message=log_message
                        ))
        except Exception as e:
            logger.warning(f"读取日志文件 {log_file} 失败: {e}")
            continue
    
    # 按时间戳排序（支持正序和倒序）
    reverse_order = order.lower() != "asc" if order else True
    all_logs.sort(key=lambda x: x.timestamp, reverse=reverse_order)
    
    # 分页
    total = len(all_logs)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    paginated_logs = all_logs[start_idx:end_idx]
    has_more = end_idx < total
    
    return LogsOut(
        logs=paginated_logs,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more
    )


@app.get("/management/logs/files")
async def list_log_files(authorization: Optional[str] = Header(default=None)):
    """获取所有日志文件列表（仅超级管理员）"""
    payload = get_current_user_from_headers(authorization)
    if not payload.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    
    from pathlib import Path
    
    logs_dir = Path("data/logs")
    if not logs_dir.exists():
        return {"files": []}
    
    log_files = sorted(logs_dir.glob("graffito_*.log"), reverse=True)
    
    file_info = []
    for log_file in log_files:
        try:
            stat = log_file.stat()
            # 从文件名提取日期
            date_match = re.match(r'graffito_(\d{4}-\d{2}-\d{2})\.log', log_file.name)
            date_str = date_match.group(1) if date_match else None
            
            file_info.append({
                "filename": log_file.name,
                "date": date_str,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        except Exception as e:
            logger.warning(f"获取日志文件 {log_file} 信息失败: {e}")
            continue
    
    return {"files": file_info}


# ============================================
# 反馈管理 API
# ============================================
class FeedbackOut(BaseModel):
    id: int
    user_id: str
    receiver_id: str
    group_name: Optional[str] = None
    content: str
    status: str
    admin_reply: Optional[str] = None
    replied_by: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    replied_at: Optional[str] = None


class FeedbackReplyIn(BaseModel):
    reply: str


@app.get("/management/feedbacks", response_model=List[FeedbackOut])
async def get_feedbacks(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    group_name: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    authorization: Optional[str] = Header(default=None)
):
    """获取反馈列表"""
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select, and_
        from core.models import Feedback
        
        # 构建查询
        stmt = select(Feedback).order_by(Feedback.created_at.desc())
        
        # 添加过滤条件
        filters = []
        if status:
            filters.append(Feedback.status == status)
        if user_id:
            filters.append(Feedback.user_id == user_id)
        if group_name:
            filters.append(Feedback.group_name == group_name)
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        result = await session.execute(stmt)
        feedbacks = result.scalars().all()
        
        return [
            FeedbackOut(
                id=fb.id,
                user_id=fb.user_id,
                receiver_id=fb.receiver_id,
                group_name=fb.group_name,
                content=fb.content,
                status=fb.status,
                admin_reply=fb.admin_reply,
                replied_by=fb.replied_by,
                created_at=fb.created_at.isoformat() if fb.created_at else "",
                updated_at=fb.updated_at.isoformat() if fb.updated_at else None,
                replied_at=fb.replied_at.isoformat() if fb.replied_at else None
            )
            for fb in feedbacks
        ]


@app.get("/management/feedbacks/{feedback_id}", response_model=FeedbackOut)
async def get_feedback_detail(feedback_id: int, authorization: Optional[str] = Header(default=None)):
    """获取反馈详情"""
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import Feedback
        
        stmt = select(Feedback).where(Feedback.id == feedback_id)
        result = await session.execute(stmt)
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈未找到")
        
        # 自动标记为已读
        if feedback.status == 'pending':
            feedback.status = 'read'
            await session.flush()
        
        return FeedbackOut(
            id=feedback.id,
            user_id=feedback.user_id,
            receiver_id=feedback.receiver_id,
            group_name=feedback.group_name,
            content=feedback.content,
            status=feedback.status,
            admin_reply=feedback.admin_reply,
            replied_by=feedback.replied_by,
            created_at=feedback.created_at.isoformat() if feedback.created_at else "",
            updated_at=feedback.updated_at.isoformat() if feedback.updated_at else None,
            replied_at=feedback.replied_at.isoformat() if feedback.replied_at else None
        )


@app.post("/management/feedbacks/{feedback_id}/reply")
async def reply_feedback(
    feedback_id: int,
    body: FeedbackReplyIn,
    authorization: Optional[str] = Header(default=None)
):
    """回复反馈"""
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import Feedback
        
        stmt = select(Feedback).where(Feedback.id == feedback_id)
        result = await session.execute(stmt)
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈未找到")
        
        # 更新回复
        feedback.admin_reply = body.reply
        feedback.replied_by = str(payload.get("username"))
        feedback.replied_at = datetime.now()
        feedback.status = 'resolved'
        
        await session.flush()
        
        # 通过 QQ 发送回复给用户
        try:
            # 导入必要的模块
            from core.plugin import plugin_manager
            receiver = plugin_manager.get_receiver("qq_receiver")
            
            if receiver:
                # 发送私聊消息
                message = f"【系统回复】您的反馈已收到回复：\n\n{body.reply}"
                await receiver.send_private_message_by_self(
                    feedback.receiver_id,
                    feedback.user_id,
                    message
                )
                logger.info(f"已向用户 {feedback.user_id} 发送反馈回复")
        except Exception as e:
            logger.error(f"发送反馈回复失败: {e}", exc_info=True)
            # 回复失败不影响保存
        
        return {"success": True, "message": "回复成功"}


@app.patch("/management/feedbacks/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: int,
    status: str,
    authorization: Optional[str] = Header(default=None)
):
    """更新反馈状态"""
    payload = get_current_user_from_headers(authorization)
    
    if status not in ['pending', 'read', 'resolved']:
        raise HTTPException(status_code=400, detail="无效的状态值")
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select
        from core.models import Feedback
        
        stmt = select(Feedback).where(Feedback.id == feedback_id)
        result = await session.execute(stmt)
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈未找到")
        
        feedback.status = status
        await session.flush()
        
        return {"success": True, "message": "状态已更新"}


@app.delete("/management/feedbacks/{feedback_id}")
async def delete_feedback(feedback_id: int, authorization: Optional[str] = Header(default=None)):
    """删除反馈"""
    payload = get_current_user_from_headers(authorization)
    
    db = await get_db()
    async with db.get_session() as session:
        from sqlalchemy import select, delete
        from core.models import Feedback
        
        stmt = select(Feedback).where(Feedback.id == feedback_id)
        result = await session.execute(stmt)
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈未找到")
        
        delete_stmt = delete(Feedback).where(Feedback.id == feedback_id)
        await session.execute(delete_stmt)
        await session.commit()
        
        return {"success": True, "message": "反馈已删除"}


# ============================================
# 举报审核管理 API
# ============================================
class ReportProcessIn(BaseModel):
    action: str  # delete | keep
    reason: str


@app.get("/management/reports")
async def get_reports(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    authorization: Optional[str] = Header(default=None)
):
    """获取举报列表"""
    payload = get_current_user_from_headers(authorization)
    
    from services.report_service import ReportService
    from sqlalchemy import select
    from core.models import Report, Submission
    
    offset = (page - 1) * page_size
    reports, total = await ReportService.get_reports_for_review(
        status=status,
        limit=page_size,
        offset=offset
    )
    
    # 获取关联的投稿信息
    report_list = []
    db = await get_db()
    async with db.get_session() as session:
        for report in reports:
            result = await session.execute(
                select(Submission).where(Submission.id == report.submission_id)
            )
            submission = result.scalar_one_or_none()
            
            report_dict = report.to_dict()
            report_dict['submission'] = submission.to_dict() if submission else None
            report_list.append(report_dict)
    
    return {
        "success": True,
        "data": {
            "items": report_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@app.get("/management/reports/{report_id}")
async def get_report_detail(
    report_id: int,
    authorization: Optional[str] = Header(default=None)
):
    """获取举报详情"""
    payload = get_current_user_from_headers(authorization)
    
    from services.report_service import ReportService
    from sqlalchemy import select
    from core.models import Report, Submission, PlatformComment
    
    report = await ReportService.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="举报未找到")
    
    db = await get_db()
    async with db.get_session() as session:
        # 获取投稿信息
        result = await session.execute(
            select(Submission).where(Submission.id == report.submission_id)
        )
        submission = result.scalar_one_or_none()
        
        # 获取评论信息
        comments = await ReportService.get_platform_comments(report.submission_id)
        
        report_dict = report.to_dict()
        report_dict['submission'] = submission.to_dict() if submission else None
        report_dict['submission_full'] = {
            'raw_content': submission.raw_content,
            'llm_result': submission.llm_result,
            'processed_content': submission.processed_content
        } if submission else None
        report_dict['comments'] = [c.to_dict() for c in comments]
        
        return {
            "success": True,
            "data": report_dict
        }


@app.post("/management/reports/{report_id}/process")
async def process_report(
    report_id: int,
    body: ReportProcessIn,
    authorization: Optional[str] = Header(default=None)
):
    """处理举报"""
    payload = get_current_user_from_headers(authorization)
    
    if body.action not in ['delete', 'keep']:
        raise HTTPException(status_code=400, detail="无效的处理动作")
    
    from services.report_service import ReportService
    from core.models import Submission
    from sqlalchemy import select
    
    # 获取举报和投稿信息
    report = await ReportService.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="举报未找到")
    
    db = await get_db()
    async with db.get_session() as session:
        result = await session.execute(
            select(Submission).where(Submission.id == report.submission_id)
        )
        submission = result.scalar_one_or_none()
        
        if not submission:
            raise HTTPException(status_code=404, detail="投稿未找到")
    
    # 使用统一的举报处理服务
    result = await ReportService.handle_report_action(
        report=report,
        submission=submission,
        action=body.action,
        reason=body.reason,
        processed_by=str(payload.get("username"))
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message', '处理失败'))
    
    return {"success": True, "message": "处理成功"}


# ============================================
# SSE 推送端点
# ============================================
async def event_stream_generator(queue: asyncio.Queue):
    """SSE 事件流生成器"""
    try:
        # 发送初始连接成功消息
        yield f"data: {orjson.dumps({'type': 'connected', 'data': {}, 'timestamp': datetime.now().isoformat()}).decode()}\n\n"
        
        # 持续发送事件
        while True:
            try:
                # 等待新消息，超时发送心跳
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {orjson.dumps(message).decode()}\n\n"
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                yield f": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"SSE stream error: {e}")


@app.get("/events/stream")
@limiter.exempt
async def sse_stream(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = None
):
    """SSE 事件流端点"""
    # EventSource 不支持自定义 headers，所以支持从 URL 参数获取 token
    auth_header = authorization
    if not auth_header and token:
        auth_header = f"Bearer {token}"
    
    payload = get_current_user_from_headers(auth_header)
    user_id = str(payload.get("sub"))
    
    # 创建连接队列
    queue = await sse_manager.connect(user_id)
    
    async def cleanup():
        """清理连接"""
        await sse_manager.disconnect(user_id, queue)
    
    # 返回 SSE 流
    return StreamingResponse(
        event_stream_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )


@app.get("/events/connections")
async def get_sse_connections(authorization: Optional[str] = Header(default=None)):
    """获取 SSE 连接统计"""
    payload = get_current_user_from_headers(authorization)
    
    return {
        "active_connections": sse_manager.get_active_connections_count()
    }


# ============================================
# 辅助函数：在审核操作时发送 SSE 通知
# ============================================
async def notify_submission_update(submission_id: int, event_type: str, extra_data: Dict[str, Any] = None):
    """发送投稿更新通知"""
    data = {
        "submission_id": submission_id,
        **(extra_data or {})
    }
    await sse_manager.broadcast(event_type, data)


