"""校园即时通 v3 — FastAPI 后端"""
import os
import asyncio
import secrets
import time
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# ── Structured JSON logging ──

class JsonFormatter(logging.Formatter):
    """JSON log formatter -- outputs structured JSON lines."""
    def format(self, record):
        obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            obj["extra"] = record.extra
        return json.dumps(obj, ensure_ascii=False, default=str)

BASE_DIR = Path(__file__).parent
_LOG_DIR = Path("/var/log/campus") if Path("/var/log/campus").is_dir() else BASE_DIR

def _ensure_log_handler(logger_name: str, filename: str, level: int = logging.INFO) -> logging.Logger:
    """Get or create a logger with a JSON file handler."""
    log = logging.getLogger(logger_name)
    if log.handlers:
        return log
    handler = logging.FileHandler(_LOG_DIR / filename, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    handler.setLevel(level)
    log.addHandler(handler)
    log.setLevel(level)
    return log

# Audit logger -- security events
try:
    audit_logger = _ensure_log_handler("audit", "audit.log")
    app_logger = _ensure_log_handler("app", "app.log")
    error_logger = _ensure_log_handler("error", "error.log", logging.ERROR)
except Exception:
    audit_logger = logging.getLogger("audit")
    app_logger = logging.getLogger("app")
    error_logger = logging.getLogger("error")
    logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI, HTTPException, Request, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from jwt.exceptions import InvalidTokenError
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
import redis.asyncio as aioredis

load_dotenv()

# ── Redis cache ──
_redis: aioredis.Redis | None = None
CACHE_TTL = {"activities": 30, "notices": 30, "colleges": 300, "activity": 10}
_pw_reset_cooldowns: dict[str, float] = {}
_int_cooldown: dict[str, list[float]] = {}
_login_lock = None  # asyncio.Lock, initialized in lifespan

async def _check_login_attempts(student_id: str) -> tuple[int, bool]:
    """Check login attempts via Redis. Returns (remaining_attempts, is_locked)."""
    if _redis is None:
        return (5, False)  # fallback — don't block without Redis
    key = f"login_attempts:{student_id}"
    try:
        count = await _redis.get(key)
        count = int(count) if count else 0
        if count >= 5:
            ttl = await _redis.ttl(key)
            ttl = max(0, ttl if ttl > 0 else 900)
            return (0, True)
        return (5 - count, False)
    except Exception:
        return (5, False)

async def _incr_login_attempts(student_id: str):
    """Atomically increment failed login counter with 15-min expiry."""
    if _redis is None:
        return
    key = f"login_attempts:{student_id}"
    try:
        pipe = _redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 900)  # 15 min window
        await pipe.execute()
    except Exception:
        app_logger.debug("Redis login_attempts incr failed — rate limiter degraded")

async def _clear_login_attempts(student_id: str):
    if _redis is None:
        return
    try:
        await _redis.delete(f"login_attempts:{student_id}")
    except Exception:
        app_logger.debug("Redis login_attempts clear failed")

async def cache_get(key: str):
    if _redis is None: return None
    try:
        val = await _redis.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None

async def cache_set(key: str, value, ttl: int = 30):
    if _redis is None: return
    try:
        await _redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning(f"Non-critical error in cache_set: {e}")

async def cache_delete(pattern: str):
    if _redis is None: return
    try:
        keys = await _redis.keys(pattern)
        if keys: await _redis.delete(*keys)
    except Exception as e:
        logger.warning(f"Non-critical error in cache_delete: {e}")

import db as database

import bcrypt  # fallback for legacy password hashes

ph = PasswordHasher()

def _validate_password(password: str) -> str | None:
    """Validate password strength for PUBLIC registration only.
    Internal/admin password operations bypass this check."""
    if len(password) < 6:
        return "密码至少6位"
    if not re.search(r'[a-zA-Z]', password) or not re.search(r'[0-9]', password):
        return "密码需包含字母和数字"
    return None

def _hash_pw(password: str) -> str:
    # Use bcrypt for compatibility
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Huawei Push Kit config (keys from env, never hardcoded)
_HUAWEI_PUSH_CLIENT_ID = os.getenv("HUAWEI_PUSH_CLIENT_ID", "")
_HUAWEI_PUSH_CLIENT_SECRET = os.getenv("HUAWEI_PUSH_CLIENT_SECRET", "")
_HUAWEI_PUSH_TOKEN_URL = "https://oauth-login.cloud.huawei.com/oauth2/v3/token"
_HUAWEI_PUSH_SEND_URL = "https://push-api.cloud.huawei.com/v3/{{appid}}/messages:send"
_push_access_token: str | None = None
_push_token_expires: float = 0

async def _get_push_token() -> str | None:
    """Get Huawei Push Kit OAuth access token."""
    global _push_access_token, _push_token_expires
    if _push_access_token and time.time() < _push_token_expires:
        return _push_access_token
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": _HUAWEI_PUSH_CLIENT_ID,
            "client_secret": _HUAWEI_PUSH_CLIENT_SECRET,
        }).encode()
        req = urllib.request.Request(_HUAWEI_PUSH_TOKEN_URL, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosemgrep: Huawei push API with fixed URL
            body = json.loads(resp.read())
            _push_access_token = body.get("access_token")
            _push_token_expires = time.time() + body.get("expires_in", 3600) - 300
            return _push_access_token
    except Exception as e:
        app_logger.warning(f"Push token fetch failed: {e}")
    return None

async def _send_push(title: str, body: str):
    """Send push notification via Huawei Push Kit (non-blocking, best-effort)."""
    if not _push_tokens:
        return  # No registered devices
    token = await _get_push_token()
    if not token or not _HUAWEI_PUSH_CLIENT_ID:
        return
    url = _HUAWEI_PUSH_SEND_URL.replace("{{appid}}", _HUAWEI_PUSH_CLIENT_ID)
    payload = json.dumps({
        "message": {
            "notification": {"title": title, "body": body},
            "token": list(_push_tokens)[:500],
        }
    }).encode()
    # Run blocking HTTP in thread pool — non-blocking for async event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_push_request, url, token, payload)

def _do_push_request(url: str, token: str, payload: bytes):
    """Blocking HTTP request for push notification (runs in thread pool)."""
    try:
        import urllib.request
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)  # nosemgrep: Huawei push delivery API
    except Exception:
        app_logger.debug("Push notification delivery failed")  # Best-effort, never block

def _verify_pw(password: str, hash_value: str) -> bool:
    if not hash_value:
        return False
    # bcrypt
    if hash_value.startswith("$2b$") or hash_value.startswith("$2a$"):
        if bcrypt.checkpw(password.encode(), hash_value.encode()):
            return True
        return False
    # argon2 legacy -- verify then auto-migrate to bcrypt
    try:
        if ph.verify(hash_value, password):
            return True
        return False
    except VerifyMismatchError:
        return False

async def auto_process_activities():
    """后台任务：每分钟检查过期活动，自动结束+抽签"""
    while True:
        await asyncio.sleep(60)
        try:
            pool = await database.get_pool()
            expired = await pool.fetch(
                "SELECT a.id, a.title, a.signup_mode, a.max_participants, a.created_by, u.student_id as creator_sid FROM activities a JOIN users u ON a.created_by=u.id WHERE a.status='published' AND a.deadline IS NOT NULL AND a.deadline != '' AND a.deadline::timestamptz < NOW()"
            )
            for act in expired:
                aid = act["id"]; title = act["title"]
                # 抽签或直接结束
                if act["signup_mode"] == "lottery":
                    max_sel = act["max_participants"] or 0
                    selected = await database.draw_lottery(aid, max_sel)
                else:
                    await pool.execute("UPDATE activities SET status='ended' WHERE id=$1", aid)
                # 通知发布者（待办）
                await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'todo','🔔 待办：发放时长',$2)", act["created_by"], f"[aid:{aid}]「{title}」报名已截止，请尽快发放时长")
                # 通知协助者（待办）- batch
                assistants = await pool.fetch("SELECT user_id FROM assist_members WHERE activity_id=$1", aid)
                if assistants:
                    asst_values = []
                    asst_params = []
                    asst_idx = 0
                    for a in assistants:
                        asst_values.append(f"(${asst_idx+1},'todo','🔔 待办：发放时长',${asst_idx+2})")
                        asst_params.extend([a["user_id"], f"「{title}」报名已截止，协助者请关注"])
                        asst_idx += 2
                    await pool.execute(f"INSERT INTO notifications(user_id,type,title,content) VALUES {','.join(asst_values)}", *asst_params)
                # 通知所有报名者 - batch
                signups = await pool.fetch("SELECT user_id, status FROM signups WHERE activity_id=$1", aid)
                if signups:
                    notif_values = []
                    notif_params = []
                    notif_idx = 0
                    for s in signups:
                        st = "已中签" if s["status"] in ("selected","checked_in") else "已报名"
                        notif_values.append(f"(${notif_idx+1},'activity_end','活动结果通知',${notif_idx+2})")
                        notif_params.extend([s["user_id"], f"「{title}」{st}，等待发布者完结发放学时"])
                        notif_idx += 2
                    await pool.execute(f"INSERT INTO notifications(user_id,type,title,content) VALUES {','.join(notif_values)}", *notif_params)
            # 清理7天前的已读通知 + 过期签到token（每10分钟执行一次）
            _cleanup_cycle = getattr(auto_process_activities, '_cleanup_cycle', 0) + 1
            if _cleanup_cycle >= 10:
                await pool.execute("DELETE FROM notifications WHERE is_read=1 AND created_at < NOW() - INTERVAL '7 days'")
                await pool.execute("DELETE FROM checkin_tokens WHERE expires_at < NOW() - INTERVAL '1 hour'")
                auto_process_activities._cleanup_cycle = 0
            else:
                auto_process_activities._cleanup_cycle = _cleanup_cycle
        except Exception as e:
            logger.error(f"auto_process error: {e}")

@asynccontextmanager
async def lifespan(application: FastAPI):
    # Wire root logger to JSON file handler
    root = logging.getLogger()
    if not root.handlers:
        fh = logging.FileHandler(_LOG_DIR / "app.log", encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)
        root.setLevel(logging.INFO)
        logger.info("Logging initialized, writing to %s", _LOG_DIR)
    await database.get_pool()
    pool = await database.get_pool()
    # 确保表存在(新表由应用用户创建, 列迁移需DBA手动执行)
    # 角色变更冷却期表
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS role_changes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            old_role VARCHAR(20),
            new_role VARCHAR(20),
            changed_by INTEGER,
            reason TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS convert_applications (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL,
            requested_hours NUMERIC(4,1) DEFAULT 0, reason TEXT DEFAULT '',
            teacher_id INTEGER, status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS org_hours_applications (
            id SERIAL PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            mode VARCHAR(10) DEFAULT 'apply',
            requested_hours NUMERIC(4,1) DEFAULT 0,
            message TEXT DEFAULT '',
            teacher_id INTEGER,
            status VARCHAR(20) DEFAULT 'pending',
            approved_hours NUMERIC(4,1) DEFAULT 0,
            reason TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    # Refresh token columns (v1.0.5 migration)
    try:
        await pool.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token_hash VARCHAR(128)")
        await pool.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token_exp TIMESTAMP")
    except Exception as e:
        logger.warning(f"Non-critical error in migration column add: {e}")
    # Token version for single-device enforcement (v1.0.8)
    try:
        await pool.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0")
    except Exception as e:
        logger.warning(f"Non-critical error: token_version migration: {e}")
    # 迁移已移至 migrations/ 目录，部署前运行: python migrate.py
    # 此处仅做安全校验，不修改数据库结构
    try:
        # 验证关键列存在（只读检查，无锁）
        cols = await pool.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name IN ('users','activities')
            AND column_name IN ('refresh_token_hash','refresh_token_exp','latitude','longitude','lottery_drawn_at','is_active')
        """)
        existing = {r['column_name'] for r in cols}
        missing = {'refresh_token_hash','refresh_token_exp','latitude','longitude','lottery_drawn_at','is_active'} - existing
        if missing:
            logger.warning(f"Missing columns: {missing}. Run: python migrate.py")
    except Exception as e:
        logger.error(f"Migration check failed: {e}")
    # Init Redis cache
    global _redis
    try:
        redis_password = os.getenv("REDIS_PASSWORD", "")
        _redis = aioredis.Redis(host="127.0.0.1", port=6379, db=0, password=redis_password or None, decode_responses=False)
        await _redis.ping()
    except Exception:
        _redis = None
    task = asyncio.create_task(auto_process_activities())
    yield
    task.cancel()
    if _redis: await _redis.close()
    await database.close_pool()

app = FastAPI(title="校园即时通", version="3.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# Hide validation error details in production
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "请求参数格式错误"})

# Rate limiter (slowapi)
limiter = Limiter(key_func=get_remote_address, default_limits=["500/day", "120/hour"], headers_enabled=False)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9500", "http://127.0.0.1:9500", "http://139.196.50.134", "capacitor://localhost", "app://localhost"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def add_api_version(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = "3.0"
    return response

# Static files mount — dev mode: no cache
from fastapi.staticfiles import StaticFiles
import mimetypes
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
app.mount("/static", NoCacheStaticFiles(directory=str(BASE_DIR / "static")), name="static")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required. Set it before starting the server.")


# ====== Models ======

class LoginRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=5, max_length=128)

class RegisterRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=5, max_length=128)
    class_name: str = Field(default="", max_length=50)
    college: str = Field(default="", max_length=50)
    reg_code: str = Field(default="", max_length=50)
    gender: str = Field(default="", max_length=10)
    grade: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=20)
    qq: str = Field(default="", max_length=20)

def _sanitize_html(text: str) -> str:
    """Strip all HTML tags and escape special chars from user input."""
    import re as _re
    text = _re.sub(r'<[^>]*>', '', text)  # strip HTML tags
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    return text

class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    category: str = Field(default="volunteer")
    scope_type: str = Field(default="all")
    scope_value: str = Field(default="")
    max_participants: int = Field(default=0, ge=0)
    deadline: str | None = None
    staff_hours: float | None = Field(default=None, ge=0, le=999)
    participant_hours: float | None = Field(default=None, ge=0, le=999)
    checkin_enabled: bool = False
    assist_enabled: bool = False
    # Additional fields from Flutter app
    hours: float = Field(default=0, ge=0, le=999)
    activity_date: str = Field(default="")
    location: str = Field(default="", max_length=300)
    creator_override: str = Field(default="", max_length=100)
    contact_qq: str = Field(default="", max_length=20)
    contact_phone: str = Field(default="", max_length=20)
    qq_group: str = Field(default="", max_length=20)
    gender_limit: str = Field(default="any")
    checkin_type: str = Field(default="")
    signup_mode: str = Field(default="direct")
    cancel_policy: str = Field(default="anytime")
    cancel_deadline_lock: bool = False
    form_link: str = Field(default="", max_length=500)
    contact_mode: str = Field(default="personal")
    pu_type: str = Field(default="offline")
    pu_qq: str = Field(default="", max_length=20)
    signup_start: str = Field(default="")
    image_url: str = Field(default="", max_length=2000)
    reward_type: str = Field(default="volunteer")

class ActivityUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    scope_type: str | None = None
    scope_value: str | None = None
    max_participants: int | None = None
    deadline: str | None = None
    activity_date: str | None = None
    location: str | None = None
    checkin_enabled: bool | None = None

class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    scope_type: str = Field(default="all", max_length=20)
    scope_value: str = Field(default="", max_length=500)
    scheduled_at: str = Field(default="", max_length=30)
    is_pinned: bool = False
    pin_days: int = Field(default=1, ge=1, le=365)
    image_url: str = Field(default="", max_length=500)

class ActivityModify(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    hours: float | None = Field(default=None, ge=0, le=999)
    participant_hours: float | None = Field(default=None, ge=0, le=999)
    staff_hours: float | None = Field(default=None, ge=0, le=999)
    location: str | None = Field(default=None, max_length=200)
    activity_date: str | None = Field(default=None, max_length=20)
    max_participants: int | None = Field(default=None, ge=0)
    deadline: str | None = Field(default=None, max_length=20)
    signup_mode: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=20)
    scope_type: str | None = Field(default=None, max_length=20)
    scope_value: str | None = Field(default=None, max_length=200)
    start_time: str | None = Field(default=None, max_length=20)
    end_time: str | None = Field(default=None, max_length=20)
    checkin_enabled: bool | None = None
    checkin_deadline: str | None = Field(default=None, max_length=20)

class ManualAddRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=30)
    name: str | None = Field(default=None, max_length=50)

class NotifyAllRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

class InfoChangeRequest(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    new_value: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)

class ApproveRejectBody(BaseModel):
    student_id: str | None = Field(default=None, max_length=30)

class BatchImportRequest(BaseModel):
    student_ids: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=5, max_length=128)

class SetRoleRequest(BaseModel):
    student_id: str
    role: str
    reason: str = Field(default="", max_length=500)

class ConfigCodesUpdate(BaseModel):
    teacher_code: str | None = None
    student_code: str | None = None

class PublishCodeCreate(BaseModel):
    days: int = Field(default=30, ge=1, le=365)

class ActivateCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)

class MessageCreate(BaseModel):
    to: int
    content: str = Field(min_length=1, max_length=5000)


# ====== Config helpers ======

def load_config() -> dict:
    import json as _json
    cfg_path = BASE_DIR / "config.json"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            cfg = _json.load(f)
            # Ensure both codes exist (backward compat)
            if "teacher_code" not in cfg or "student_code" not in cfg:
                import secrets as _s
                cfg.setdefault("teacher_code", "tzxy" + _s.token_hex(6))
                cfg.setdefault("student_code", _s.token_hex(8))
                save_config(cfg)
            return cfg
    import secrets as _secrets
    cfg = {
        "teacher_code": "tzxy" + _secrets.token_hex(6),
        "student_code": _secrets.token_hex(8)
    }
    save_config(cfg)
    return cfg

def save_config(cfg: dict):
    import json as _json
    with open(BASE_DIR / "config.json", "w", encoding="utf-8") as f:
        _json.dump(cfg, f, ensure_ascii=False, indent=2)


# ====== Auth ======

def create_token(user_id: int, role: str = "", token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role": role,
        "ver": token_version,
        "iat": now,
        "iss": "campus-instant-messenger",
        "jti": secrets.token_hex(8),
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_refresh_token() -> str:
    return secrets.token_hex(32)

def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except InvalidTokenError:
        return None

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    payload = verify_token(auth[7:])
    if not payload:
        raise HTTPException(401, "Token过期，请重新登录")
    user = await database.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(401, "用户不存在")
    if not user.get("is_active", True):
        raise HTTPException(401, "账户已被禁用，请联系管理员")
    # Single-device enforcement: if another device logged in, token version won't match
    token_ver = payload.get("ver", 0)
    db_ver = user.get("token_version", 0)
    if token_ver != db_ver:
        raise HTTPException(401, "您的账号已在其他设备登录，请重新登录")
    return user

def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "权限不足")
        return user
    return Depends(checker)


# ====== App Update ======

APP_VERSION = "1.0.12"

@app.get("/api/version")
async def get_version():
    return {
        "version": APP_VERSION,
        "version_code": 29,
        "min_version_code": 22,
        "apk_url": "/static/app-release.apk",
        "release_notes": "v1.0.12: 免登持久化+AuthGate启动页+RefreshToken续期+监控修复+pete优化"
    }

_START_TIME = datetime.now()

@app.get("/api/health")
async def health_check():
    """健康检查 — 公开只读，用于监控"""
    try:
        pool = await database.get_pool()
        await pool.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = False
    if _redis is not None:
        try:
            await _redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
    disk = shutil.disk_usage("/")
    disk_pct = round(disk.used / disk.total * 100, 1)
    mem_info = None
    try:
        import psutil
        m = psutil.virtual_memory()
        mem_info = {"total_mb": round(m.total / 1024 / 1024, 1), "available_mb": round(m.available / 1024 / 1024, 1), "used_pct": m.percent}
    except ImportError:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "uptime_seconds": int((datetime.now() - _START_TIME).total_seconds()),
        "version": APP_VERSION,
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "disconnected",
        "pool": await _get_db_pool_stats(),
        "disk": {"total_gb": round(disk.total / 1024 ** 3, 1), "used_gb": round(disk.used / 1024 ** 3, 1), "free_gb": round(disk.free / 1024 ** 3, 1), "used_pct": disk_pct},
        "memory": mem_info,
    }


async def _get_db_pool_stats() -> dict:
    """Get database connection pool stats (best-effort)."""
    try:
        pool = await database.get_pool()
        stats = {"connected_connections": 0, "idle_connections": 0, "current_size": 0, "min_size": 2, "max_size": 20}
        try:
            stats["connected_connections"] = pool.get_connected_connections()
            stats["idle_connections"] = pool.get_idle_connections()
            stats["current_size"] = pool.get_size()
        except AttributeError:
            pass
        return stats
    except Exception:
        return {"error": "pool not available"}


@app.get("/api/health/detailed")
async def health_detailed(user: dict = Depends(get_current_user)):
    """Detailed health -- admin only. Returns table row counts, env info."""
    if user["role"] not in ("college_admin", "school_admin"):
        raise HTTPException(403, "仅管理员可查看详细状态")
    base = await health_check()
    try:
        pool = await database.get_pool()
        counts = await pool.fetch("SELECT relname AS table_name, n_live_tup AS row_estimate FROM pg_stat_user_tables ORDER BY n_live_tup DESC")
        base["table_row_estimates"] = [dict(r) for r in counts]
    except Exception:
        base["table_row_estimates"] = []
    base["environment"] = {
        "python_version": __import__("sys").version,
        "platform": __import__("sys").platform,
        "cwd": str(__import__("pathlib").Path.cwd()),
    }
    return base

# ====== Auth endpoints ======

@app.post("/api/login")
async def login(req: LoginRequest, request: Request):
    try:
        # Check if account is locked
        remaining, locked = await _check_login_attempts(req.student_id)
        if locked:
            raise HTTPException(429, "账户已锁定，请15分钟后再试")
        pool = await database.get_pool()
        import bcrypt
        # Timing-safe: always run bcrypt even if user doesn't exist — prevents user enumeration via timing
        _DUMMY_HASH = "$2b$12$LJ3m4ys3GZfnYMz8kVsKaOMmBKsURkHNBKkYCoGf2HPWLzFJDrK1e"
        user = await pool.fetchrow(
            "SELECT id, student_id, name, class, college, class_name, role, can_publish, publish_expires_at, "
            "is_poor, is_superadmin, qq, phone, gender, volunteer_hours, show_phone, show_qq, publisher_org_id, "
            "grade, is_active, password_hash, temp_password_hash, temp_password_exp, "
            "COALESCE(must_change_password,FALSE) as must_change_password "
            "FROM users WHERE student_id=$1", req.student_id)
        if not user:
            bcrypt.checkpw(req.password.encode(), _DUMMY_HASH)  # timing constant
            raise HTTPException(401, "学号或密码错误")
        if not user.get("is_active", True):
            raise HTTPException(401, "账户已被禁用")
        ok = bcrypt.checkpw(req.password.encode(), user["password_hash"].encode())
        # 正常密码不对 → 尝试临时密码
        using_temp = False
        if not ok and user.get("temp_password_hash"):
            if user.get("temp_password_exp") and user["temp_password_exp"] < datetime.now():
                ok = False  # temp password expired
            else:
                ok = bcrypt.checkpw(req.password.encode(), user["temp_password_hash"].encode())
                if ok:
                    using_temp = True
        if not ok:
            await _incr_login_attempts(req.student_id)
            raise HTTPException(401, "学号或密码错误")
        user = dict(user)
        # success — clear lockout, clear temp password if used
        await _clear_login_attempts(req.student_id)
        if using_temp:
            await pool.execute("UPDATE users SET temp_password_hash=NULL, temp_password_exp=NULL WHERE id=$1", user["id"])
        audit_logger.info(f"AUDIT: login_success user_id={user['id']} student_id={req.student_id} role={user.get('role','')} ip={request.client.host} temp={using_temp}")
        pool = await database.get_pool()
        pw_hash = user.get("password_hash","")
        if pw_hash.startswith("$argon2"):
            try:
                new_hash = _hash_pw(req.password)
                await pool.execute("UPDATE users SET password_hash=$1 WHERE id=$2", new_hash, user["id"])
            except Exception:
                pass  # non-critical, will retry next login
        refresh_token = create_refresh_token()
        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        # Bump token version → kicks out other devices (single-device enforcement)
        await pool.execute("UPDATE users SET token_version = COALESCE(token_version, 0) + 1 WHERE id=$1", user["id"])
        new_version = await pool.fetchval("SELECT token_version FROM users WHERE id=$1", user["id"])
        await pool.execute("UPDATE users SET refresh_token_hash=$1, refresh_token_exp=$2 WHERE id=$3",
            refresh_hash, datetime.now() + timedelta(days=30), user["id"])
        must_change = using_temp or user.get("must_change_password", False)
        return {
            "token": create_token(user["id"], role=user.get("role",""), token_version=new_version or 1),
            "refresh_token": refresh_token,
            "must_change_password": must_change,
            "user": {
                "id": user["id"], "student_id": user["student_id"],
                "name": user["name"], "class": user["class"],
                "college": user["college"], "role": user["role"]
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "学号或密码错误")

@app.post("/api/token/refresh")
async def refresh_token_endpoint(req: dict = Body(...)):
    """用refresh_token换新的access_token。轮换制：每次换新token也给新refresh_token。"""
    refresh = (req.get("refresh_token") or "").strip()
    if not refresh or len(refresh) < 32:
        raise HTTPException(400, "无效的refresh_token")
    refresh_hash = hashlib.sha256(refresh.encode()).hexdigest()
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                "SELECT id, role, token_version FROM users WHERE refresh_token_hash=$1 AND refresh_token_exp > NOW() FOR UPDATE",
                refresh_hash)
            if not user:
                raise HTTPException(401, "refresh_token无效或已过期，请重新登录")
            new_token = create_token(user["id"], role=user.get("role",""), token_version=user.get("token_version") or 1)
            new_refresh = create_refresh_token()
            new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
            await conn.execute("UPDATE users SET refresh_token_hash=$1, refresh_token_exp=$2 WHERE id=$3",
                new_hash, datetime.now() + timedelta(days=30), user["id"])
    return {"token": new_token, "refresh_token": new_refresh}

@app.post("/api/register")
@limiter.limit("5/hour")
async def register(req: RegisterRequest, request: Request):
    cfg = load_config()
    super_code = os.getenv("REG_SUPER_CODE", cfg.get("super_code", os.urandom(16).hex()))
    college_admin_code = os.getenv("REG_COLLEGE_ADMIN_CODE", cfg.get("college_admin_code", os.urandom(16).hex()))
    teacher_code = os.getenv("REG_TEACHER_CODE", cfg.get("teacher_code", os.urandom(16).hex()))
    student_code = os.getenv("REG_STUDENT_CODE", cfg.get("student_code", ""))
    if not student_code:
        raise HTTPException(400, "学生自主注册已关闭，请联系管理员")
    if not req.reg_code or req.reg_code == student_code:
        role = "student"
    elif req.reg_code == super_code:
        role = "school_admin"
    elif req.reg_code == college_admin_code:
        role = "college_admin"
    elif req.reg_code == teacher_code:
        role = "teacher"
    else:
        raise HTTPException(400, "注册码无效")

    if role == "student":
        if not req.student_id.isdigit() or len(req.student_id) != 9:
            raise HTTPException(400, "学生请使用9位学号注册")
        pw_err = _validate_password(req.password)
        if pw_err:
            raise HTTPException(400, pw_err)
    try:
        pwd = _hash_pw(req.password)
    except Exception:
        raise HTTPException(400, "密码格式错误")

    uid = await database.create_user(
        req.student_id, req.name, pwd, req.class_name, req.college, role,
        getattr(req, 'qq', ''), getattr(req, 'phone', ''), getattr(req, 'gender', '')
    )
    if uid is None:
        raise HTTPException(400, "该学号已注册")
    audit_logger.info(f"AUDIT: user_registered student_id={req.student_id} name={req.name} role={role}")
    return {"token": create_token(uid, role), "user_id": uid}

@app.get("/api/me")
async def get_me(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    full = await pool.fetchrow(
        "SELECT u.id, u.student_id, u.name, u.class, u.college, u.role, u.is_poor, u.can_publish, "
        "u.show_phone, u.show_qq, u.qq, u.phone, u.gender, u.publisher_org_id, u.created_at, "
        "u.grade, u.is_active, "
        "(SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id=$1) as volunteer_hours "
        "FROM users u WHERE u.id=$1", user["id"]
    )
    u = dict(full) if full else user
    u["id"] = user["id"]
    u["role"] = user["role"]
    # 计算发布权到期日 (来自最早到期的有效发布码)
    if u.get("can_publish") and u["role"] == "student":
        code = await pool.fetchrow(
            "SELECT created_at, duration_days FROM publish_codes WHERE used_by=$1 AND revoked=false ORDER BY created_at DESC LIMIT 1",
            user["id"]
        )
        if code and code["created_at"]:
            from datetime import timedelta
            exp = code["created_at"] + timedelta(days=code["duration_days"] or 30)
            u["publish_expires_at"] = exp.isoformat()
    return u

@app.post("/api/me/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    # Rate limit: 5 attempts per 15 minutes per user
    # Rate limited globally by slowapi
    full = await database.get_user_with_password(user["student_id"])
    if not full or not _verify_pw(req.old_password, full["password_hash"]):
        raise HTTPException(400, "原密码错误")
    new_hash = _hash_pw(req.new_password)
    pool = await database.get_pool()
    await pool.execute(
        "UPDATE users SET password_hash=$1, temp_password_hash=NULL, temp_password_exp=NULL, must_change_password=FALSE WHERE id=$2",
        new_hash, user["id"]
    )
    audit_logger.info(f"AUDIT: password_changed user_id={user['id']} time={datetime.now().isoformat()}")
    return {"ok": True}

@app.post("/api/me/activate-publisher")
async def activate_publisher(code: str = "", user: dict = Depends(get_current_user)):
    org = await database.get_org_by_code(code)
    if not org:
        raise HTTPException(400, "发布码无效或已失效")
    await database.activate_publisher(user["id"], org["id"], code)
    return {"ok": True, "org_name": org["name"]}

@app.post("/api/me/privacy")
async def update_privacy(req: dict = Body(...), user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    if "show_phone" in req:
        await pool.execute("UPDATE users SET show_phone=$1 WHERE id=$2", 1 if req.get("show_phone", False) else 0, user["id"])
    if "show_qq" in req:
        await pool.execute("UPDATE users SET show_qq=$1 WHERE id=$2", 1 if req["show_qq"] else 0, user["id"])
    return {"ok": True}


# ====== Activities ======

@app.get("/api/activities")
async def list_activities(user: dict = Depends(get_current_user), page: int = 1, limit: int = 20):
    """活动列表，支持分页。高频接口，Redis缓存30秒。"""
    if page < 1: page = 1
    if limit < 1 or limit > 100: limit = 20
    cache_key = f"acts:{user['id']}:{user.get('college','')}:{user.get('role','')}:{page}:{limit}"
    cached = await cache_get(cache_key)
    if cached: return cached
    offset = max(0, (page - 1) * limit)
    items = await database.list_activities(limit=limit, offset=offset, user_college=user.get("college",""),
                                           user_role=user.get("role","student"), user_id=user["id"])
    result = {"items": items, "page": page, "limit": limit}
    await cache_set(cache_key, result, CACHE_TTL["activities"])
    return result

@app.get("/api/activities/{activity_id}")
async def get_activity(activity_id: int, user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act:
        raise HTTPException(404, "活动不存在")
    if act["scope_type"] == "internal":
        pool = await database.get_pool()
        staff = await pool.fetchrow(
            "SELECT 1 FROM signups WHERE activity_id=$1 AND user_id=$2 AND role='staff'",
            activity_id, user["id"]
        )
        if not staff and user["role"] not in ("teacher", "college_admin", "school_admin"):
            raise HTTPException(403, "内部活动，仅工作人员可见")
    return act

@app.post("/api/activities")
@limiter.limit("30/hour")
async def create_activity(req: ActivityCreate, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher", "college_admin", "school_admin") and not user.get("publisher_org_id") and not user.get("can_publish"):
        raise HTTPException(400, "请先使用发布码激活发布者身份")
    # 防冒充检查
    _impersonate = ('【系统', '【官方', '【教务', '【学工', '【学校通知', '【紧急通知')
    for pfx in _impersonate:
        if pfx in req.title:
            raise HTTPException(400, "活动标题禁止使用官方前缀")
    data = req.model_dump()
    data["title"] = _sanitize_html(data["title"])
    data["description"] = _sanitize_html(data.get("description", ""))
    data["created_by"] = user["id"]
    data["organization_id"] = user.get("publisher_org_id")
    data.setdefault("status", "published")
    aid = await database.create_activity(data)
    audit_logger.info(f"AUDIT: activity_created id={aid} title={req.title} by={user['id']}")
    pool = await database.get_pool()
    assist_code = ""
    if data.get("assist_enabled"):
        assist_code = "HLP" + secrets.token_hex(4).upper()
        await pool.execute("INSERT INTO assist_codes(activity_id,code) VALUES($1,$2) ON CONFLICT DO NOTHING", aid, assist_code)
    # 通知发布者
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','活动发布成功',$2)", user["id"], f"[aid:{aid}]「{data['title']}」已成功发布")
    # 通知发布者所在学院的授权老师
    authorizers = await pool.fetch("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1 AND id != $2", user.get("college",""), user["id"])
    for a in authorizers:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','学生发布新活动',$2)", a["id"], f"[aid:{aid}]{user['name']} 发布了「{data['title']}」")
    # 通知相关学生
    scope = data.get("scope_type","all")
    if scope == "all":
        students = await pool.fetch("SELECT id FROM users WHERE role='student'")
    elif scope == "college":
        sv = data.get("scope_value","")
        if sv:
            cols = sv.split(",")
            students = await pool.fetch(f"SELECT id FROM users WHERE role='student' AND college IN ({','.join('$'+str(i+1) for i in range(len(cols)))})", *cols)
        else:
            students = []
    else:
        students = []
    for s in students:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','新活动发布',$2)", s["id"], f"[aid:{aid}]「{data['title']}」新活动已发布，快去看看吧")
    await cache_delete("acts:*")
    return {"id": aid, "assist_code": assist_code}

def _can_manage_act(act: dict, user: dict) -> bool:
    if user["role"] == "school_admin" or user.get("is_owner"): return True
    if act["created_by"] == user["id"]: return True
    if user["role"] == "college_admin":
        uc = user.get("college","")
        sv = act.get("scope_value","")
        if sv and uc in sv.split(","): return True
    return False

@app.put("/api/activities/{activity_id}")
async def update_activity(activity_id: int, req: ActivityUpdate,
                          user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if not _can_manage_act(act, user): raise HTTPException(403, "无权限修改此活动")
    pool = await database.get_pool()
    ALLOWED = {"title","description","status","scope_type","scope_value",
               "max_participants","deadline","activity_date","location",
               "checkin_enabled","start_time","end_time","signup_mode"}
    updates = {k: v for k, v in req.model_dump().items() if v is not None and k in ALLOWED}
    if updates:
        if "title" in updates:
            updates["title"] = _sanitize_html(updates["title"])
        if "description" in updates:
            updates["description"] = _sanitize_html(updates["description"])
        sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
        await pool.execute(
            f"UPDATE activities SET {sets} WHERE id=$1", activity_id, *updates.values()
        )
    await cache_delete("acts:*")
    return {"ok": True}

@app.delete("/api/activities/{activity_id}")
async def delete_activity(activity_id: int, reason: str = "", user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if not _can_manage_act(act, user): raise HTTPException(403, "无权限取消此活动")
    pool = await database.get_pool()
    await pool.execute("UPDATE activities SET status='ended' WHERE id=$1", activity_id)
    canceller = f"{user['name']}({user['student_id']})"
    msg = f"「{act['title']}」被{canceller}取消"
    if reason: msg += f"\n原因：{reason}"
    # 通知所有报名者
    signups = await pool.fetch("SELECT user_id FROM signups WHERE activity_id=$1", activity_id)
    for s in signups:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_cancel','活动已取消',$2)", s["user_id"], f"[aid:{activity_id}]{msg}")
    # 通知协助者
    assistants = await pool.fetch("SELECT user_id FROM assist_members WHERE activity_id=$1", activity_id)
    for a in assistants:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_cancel','活动已取消',$2)", a["user_id"], f"[aid:{activity_id}]{msg}")
    # 通知发布者（如果不是同一个人）
    if act["created_by"] != user["id"]:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_cancel','活动被取消',$2)", act["created_by"], f"[aid:{activity_id}]{msg}")
    await cache_delete("acts:*")
    return {"ok": True}

@app.post("/api/activities/{activity_id}/complete")
async def complete_activity(activity_id: int, user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if not _can_manage_act(act, user): raise HTTPException(403)
    if act["status"] != "ended":
        raise HTTPException(400, "只能完结已结束的活动")
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE activities SET status='completed' WHERE id=$1", activity_id)
            audit_logger.info(f"AUDIT: activity_completed by={user['id']} aid={activity_id} title={act.get('title','')}")
            # 自动生成学时证书 — 原子操作: 证书+积分+通知在同一事务
            signups = await conn.fetch("SELECT user_id, status, role FROM signups WHERE activity_id=$1 AND status IN ('selected','checked_in')", activity_id)
            certs_generated = 0
            failed_users = []
            for s in signups:
                uid = s["user_id"]
                role = s.get("role", "participant")
                if role == "staff":
                    sh = act.get("staff_hours")
                    hours = sh if sh not in (None, 0) else (act.get("hours") or 0)
                else:
                    ph = act.get("participant_hours")
                    hours = ph if ph not in (None, 0) else (act.get("hours") or 0)
                try:
                    cert_no = f"CERT-{act['created_at'].strftime('%Y%m%d')}-{activity_id}-{uid:04d}"
                    await conn.execute(
                        "INSERT INTO certificates(activity_id,user_id,hours,certificate_no,created_at) VALUES($1,$2,$3,$4,NOW()) ON CONFLICT DO NOTHING",
                        activity_id, uid, hours, cert_no
                    )
                    # 同步更新 users.volunteer_hours 聚合字段（从certificates表重新计算）
                    await conn.execute(
                        "UPDATE users SET volunteer_hours = (SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id = $1) WHERE id = $1",
                        uid
                    )
                    await conn.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_done','学时已发放',$2)",
                        uid, f"[aid:{activity_id}]「{act['title']}」已完结，请查看你的学时记录")
                    certs_generated += 1
                except Exception as e:
                    logger.error(f"Certificate generation failed for user {uid} in activity {activity_id}: {e}")
                    failed_users.append(uid)
            await conn.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_done','活动已完结',$2)",
                act["created_by"], f"[aid:{activity_id}]「{act['title']}」已完结发分（{certs_generated}人）")
            if failed_users:
                logger.warning(f"Certificate generation partially failed for activity {activity_id}: {len(failed_users)} users affected: {failed_users}")
    audit_logger.info(f"AUDIT: certs_auto_generated aid={activity_id} count={certs_generated} failed={len(failed_users)}")
    await cache_delete("acts:*")
    result = {"ok": True, "certificates_generated": certs_generated}
    if failed_users:
        result["failed_users"] = failed_users
    return result

@app.post("/api/activities/{activity_id}/signup")
async def signup(activity_id: int, user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act:
        raise HTTPException(404, "活动不存在")
    if act["created_by"] == user["id"]:
        raise HTTPException(400, "发布者不能报名自己的活动")
    result = await database.signup_activity(activity_id, user["id"])
    if result == "closed":
        raise HTTPException(400, "活动已结束或未发布")
    if result == "duplicate":
        raise HTTPException(400, "已报名，请勿重复提交")
    if result is None:
        raise HTTPException(404, "活动不存在")
    await cache_delete("acts:*")
    return {"ok": True}

@app.get("/api/activities/{activity_id}/signups")
async def get_signups(activity_id: int, user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if act["created_by"] != user["id"] and user["role"] not in ("teacher","college_admin","school_admin"):
        raise HTTPException(403)
    return await database.get_signups(activity_id)

@app.get("/api/activities/{activity_id}/export")
async def export_signups(activity_id: int, user: dict = Depends(get_current_user)):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if act["created_by"] != user["id"] and user["role"] not in ("teacher","college_admin","school_admin"):
        raise HTTPException(403)
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT s.*, u.name, u.student_id, u.class, u.college, u.phone FROM signups s JOIN users u ON s.user_id=u.id WHERE s.activity_id=$1 ORDER BY s.signed_at", activity_id)
    # Mask phone numbers in CSV export (PII protection)
    def _mask_phone(phone):
        p = str(phone or "").strip()
        if len(p) >= 11:
            return p[:3] + "****" + p[-4:]
        return p[:3] + "****" if len(p) > 3 else "****"
    def _csv_escape(val):
        s = str(val or "").strip()
        if s and s[0] in '=+-@!\\\x00':
            s = "'" + s
        if '"' in s or '\n' in s or '\r' in s or ',' in s:
            s = '"' + s.replace('"', '""') + '"'
        return s
    csv = "姓名,学号,班级,学院,手机,状态,签到时间\n"
    for r in rows:
        csv += f"{_csv_escape(r['name'])},{_csv_escape(r['student_id'])},{_csv_escape(r['class'])},{_csv_escape(r['college'])},{_csv_escape(_mask_phone(r['phone']))},{_csv_escape(r['status'])},{_csv_escape(r['checked_in_at'] or '')}\n"
    return {"csv": csv, "count": len(rows)}

@app.post("/api/apply-publisher")
async def apply_publisher(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    l3_users = await pool.fetch("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1", user.get("college",""))
    for u in l3_users:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'publisher_apply',$2,$3)", u["id"], "发布权限申请", f"{user['name']}({user['student_id']})申请发布权限")
    return {"ok": True}

@app.get("/api/publisher-applications")
async def list_pub_apps(status: str = "pending", user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    if status == "approved":
        rows = await pool.fetch("SELECT * FROM notifications WHERE type='publisher_approved' ORDER BY created_at DESC LIMIT 50")
    elif status == "all":
        rows = await pool.fetch("SELECT * FROM notifications WHERE type IN ('publisher_apply','publisher_approved') ORDER BY created_at DESC LIMIT 50")
    else:
        rows = await pool.fetch("SELECT * FROM notifications WHERE type='publisher_apply' ORDER BY created_at DESC LIMIT 50")
    return [dict(r) for r in rows]

@app.post("/api/publisher-applications/{nid}/approve")
async def approve_publisher(nid: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    notif = await pool.fetchrow("SELECT * FROM notifications WHERE id=$1", nid)
    if not notif: raise HTTPException(404)
    uid = notif["user_id"]
    days = int(req.get("days", 7))
    hours = float(req.get("hours", 0) or 0)

    # 两级审批: ≥15h且当前是老师初审→转为院超管终审
    if hours >= 15 and user["role"] == "teacher":
        import json
        await pool.execute("UPDATE notifications SET extra_data=$1 WHERE id=$2", json.dumps({"hours": hours, "days": days, "review_stage": "teacher_approved", "teacher_id": user["id"]}), nid)
        # 通知院超管
        admins = await pool.fetch("SELECT id FROM users WHERE role IN ('college_admin','school_admin') LIMIT 3")
        for a in admins:
            await pool.execute(
                "INSERT INTO notifications(user_id,type,title,content,extra_data) VALUES($1,'publisher_apply','🔴 需院超管终审',$2,$3)",
                a["id"],
                f"老师已初审通过 {notif['content']}，请终审",
                json.dumps({"hours": hours, "days": days, "review_stage": "pending_college", "original_nid": nid, "applicant_uid": uid})
            )
        return {"ok": True, "review_stage": "pending_college", "message": "已提交院超管终审"}

    # 直接批准（老师<15h 或 院超管终审）
    await pool.execute("UPDATE users SET can_publish=1 WHERE id=$1", uid)
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'approval','发布权限已批准', $2)", uid, f"你的发布权限申请已通过，有效期{days}天")
    await pool.execute("UPDATE notifications SET type='publisher_approved' WHERE id=$1", nid)
    return {"ok": True}

@app.post("/api/publisher-applications/{nid}/reject")
async def reject_publisher(nid: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    notif = await pool.fetchrow("SELECT * FROM notifications WHERE id=$1", nid)
    if not notif: raise HTTPException(404)
    reason = str(req.get("reason", "申请未通过"))
    uid = notif["user_id"]
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'rejection','发布权限申请未通过',$2)", uid, reason)
    await pool.execute("UPDATE notifications SET type='publisher_rejected' WHERE id=$1", nid)
    return {"ok": True}

# ── 发布权管理 ──

@app.post("/api/publish-codes")
async def create_publish_code(req: PublishCodeCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    days = req.days
    code = "PUB" + secrets.token_hex(4).upper()
    pool = await database.get_pool()
    await pool.execute("INSERT INTO publish_codes(code,created_by,duration_days) VALUES($1,$2,$3)", code, user["id"], days)
    return {"code": code, "days": days}

@app.get("/api/publish-codes")
async def list_publish_codes(user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    # 取该老师生成的所有码(含raw rows + JOIN users获取使用者信息)
    rows = await pool.fetch(
        "SELECT pc.*, u.name as used_name, u.student_id as used_sid FROM publish_codes pc LEFT JOIN users u ON pc.used_by=u.id WHERE pc.created_by=$1 ORDER BY pc.created_at DESC LIMIT 200", user["id"]
    )
    # 按code聚合: 同一个code多行→users列表
    codes = {}
    for r in rows:
        d = dict(r)
        c = d["code"]
        if c not in codes:
            codes[c] = {"id": d["id"], "code": c, "created_by": d["created_by"],
                        "duration_days": d["duration_days"], "revoked": d["revoked"],
                        "created_at": str(d.get("created_at", "")),
                        "users": [], "used_count": 0}
        if d.get("used_name"):
            codes[c]["users"].append({"name": d["used_name"], "student_id": d.get("used_sid", "")})
            codes[c]["used_count"] += 1
    return list(codes.values())

@app.post("/api/publish-codes/{cid}/revoke")
async def revoke_publish_code(cid: int, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    c = await pool.fetchrow("SELECT code, created_by FROM publish_codes WHERE id=$1 AND created_by=$2", cid, user["id"])
    if not c: raise HTTPException(404,"授权码不存在")
    # 收回该code的所有行
    used_rows = await pool.fetch("SELECT used_by FROM publish_codes WHERE code=$1 AND used_by IS NOT NULL", c["code"])
    await pool.execute("UPDATE publish_codes SET revoked=true WHERE code=$1", c["code"])
    for u in used_rows:
        await pool.execute("UPDATE users SET can_publish=0 WHERE id=$1", u["used_by"])
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'system','发布权已收回','你的发布权限已被收回')", u["used_by"])
    return {"ok": True, "affected": len(used_rows)}

@app.post("/api/publish-codes/{cid}/extend")
async def extend_publish_code(cid: int, days: int = 30, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    await pool.execute("UPDATE publish_codes SET duration_days=duration_days+$1 WHERE id=$2 AND created_by=$3", days, cid, user["id"])
    return {"ok": True}

@app.post("/api/activate-code")
async def activate_code(req: ActivateCodeRequest, user: dict = Depends(get_current_user)):
    code = req.code.strip().upper()
    if not code.startswith("PUB") or len(code) != 11:
        raise HTTPException(400, "授权码格式错误，应为 PUB-XXXXXXXX")
    pool = await database.get_pool()
    # 检查码是否有效(未被收回)
    c = await pool.fetchrow("SELECT * FROM publish_codes WHERE code=$1 AND revoked=false LIMIT 1", code)
    if not c: raise HTTPException(400, "授权码无效或已被收回")
    # 检查该用户是否已激活过此码
    exist = await pool.fetchrow("SELECT id FROM publish_codes WHERE code=$1 AND used_by=$2", code, user["id"])
    if exist: raise HTTPException(400, "你已经激活过此授权码")
    # 一码多人: INSERT新行(不UPDATE原行)
    await pool.execute(
        "INSERT INTO publish_codes(code, created_by, duration_days, used_by, used_at) VALUES($1,$2,$3,$4,NOW())",
        code, c["created_by"], c["duration_days"], user["id"]
    )
    await pool.execute("UPDATE users SET can_publish=1 WHERE id=$1", user["id"])
    # 通知老师
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'code_used','授权码已激活', $2)", c["created_by"], f"[aid:0]{user['name']}({user['student_id']})使用授权码获得了发布权限")
    return {"ok": True}

# ── 发布权申请 ──

@app.post("/api/publish-requests")
async def create_publish_request(req: dict = Body(...), user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    teachers = req.get("teacher_ids", [])
    if not teachers:
        # 自动找本院老师
        trs = await pool.fetch("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1 LIMIT 3", user.get("college",""))
        teachers = [t["id"] for t in trs]
    if not teachers: raise HTTPException(400, "本院暂无老师可审批")
    if len(teachers) > 3: raise HTTPException(400, "最多选择3位老师")
    rid = await pool.fetchval(
        "INSERT INTO publish_requests(user_id,req_type,duration_days,content_json,target_teacher_ids) VALUES($1,$2,$3,$4,$5) RETURNING id",
        user["id"], req.get("type","direct"), req.get("days",30), str(req.get("content",{})), ",".join(str(t) for t in teachers)
    )
    for tid in teachers:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'publish_request',$2,$3)",
            tid, "发布权限申请", f"{user['name']}({user['student_id']})申请发布权限（{req.get('days',30)}天）\n申请ID: {rid}")
    return {"ok": True, "id": rid}

@app.get("/api/publish-requests")
async def list_publish_requests(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    if user["role"] in ("teacher","college_admin","school_admin"):
        rows = await pool.fetch("SELECT pr.*, u.name as applicant_name, u.student_id as applicant_sid FROM publish_requests pr JOIN users u ON pr.user_id=u.id WHERE $1=ANY(string_to_array(pr.target_teacher_ids,',')) ORDER BY pr.created_at DESC LIMIT 50", str(user["id"]))
    else:
        rows = await pool.fetch("SELECT * FROM publish_requests WHERE user_id=$1 ORDER BY created_at DESC LIMIT 20", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/publish-requests/{rid}")
async def get_publish_request(rid: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    r = await pool.fetchrow("SELECT pr.*, u.name as applicant_name, u.student_id as applicant_sid, u.class, u.college as applicant_college FROM publish_requests pr JOIN users u ON pr.user_id=u.id WHERE pr.id=$1", rid)
    if not r: raise HTTPException(404)
    if user["role"] not in ("teacher","college_admin","school_admin") and r["user_id"] != user["id"]:
        raise HTTPException(403)
    if user["role"] in ("teacher","college_admin") and str(user["id"]) not in (r["target_teacher_ids"] or "").split(",") and r["user_id"] != user["id"]:
        raise HTTPException(403)
    return dict(r)

@app.post("/api/publish-requests/{rid}/approve")
async def approve_publish_request(rid: int, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    r = await pool.fetchrow("SELECT * FROM publish_requests WHERE id=$1", rid)
    if not r: raise HTTPException(404)
    await pool.execute("UPDATE users SET can_publish=1 WHERE id=$1", r["user_id"])
    await pool.execute("UPDATE publish_requests SET status='approved', resolved_by=$1, resolved_at=NOW() WHERE id=$2", user["id"], rid)
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'approval','🎉 发布权限申请已通过', $2)", r["user_id"], "你的发布权限申请已被批准！现在可以发布活动和公告了。")
    return {"ok": True}

@app.post("/api/publish-requests/{rid}/reject")
async def reject_publish_request(rid: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    r = await pool.fetchrow("SELECT * FROM publish_requests WHERE id=$1", rid)
    if not r: raise HTTPException(404)
    reply = req.get("reply", "")
    await pool.execute("UPDATE publish_requests SET status='rejected', teacher_reply=$1, resolved_by=$2, resolved_at=NOW() WHERE id=$3", reply, user["id"], rid)
    msg = "⚠️ 你的发布权限申请被拒绝"
    if reply: msg += "\n老师留言：" + reply
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'rejection', $2, $3)", r["user_id"], "发布权限申请被拒绝", msg)
    return {"ok": True}

# ── 通知 ──
@app.get("/api/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50", user["id"])
    result = []
    import re
    for r in rows:
        d = dict(r)
        d["is_read"] = bool(d.get("is_read", 0))  # Convert int to bool for Dart compatibility
        # 从content中提取 [aid:数字] 或 [nid:数字]
        content = d.get("content", "") or ""
        m = re.search(r'\[aid:(\d+)\]', content)
        if m: d["activity_id"] = int(m.group(1))
        m = re.search(r'\[nid:(\d+)\]', content)
        if m: d["notice_id"] = int(m.group(1))
        result.append(d)
    return result

@app.post("/api/notifications/{nid}/read")
async def read_notification(nid: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    await pool.execute("UPDATE notifications SET is_read=1 WHERE id=$1 AND user_id=$2", nid, user["id"])
    return {"ok": True}

# ── 我的报名 ──
@app.get("/api/my-signups")
async def my_signups(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    rows = await pool.fetch("""
        SELECT s.*, a.title as activity_title, a.reward_type, a.hours, a.activity_date, a.location, a.status as act_status
        FROM signups s JOIN activities a ON s.activity_id=a.id
        WHERE s.user_id=$1 ORDER BY s.signed_at DESC
    """, user["id"])
    return [dict(r) for r in rows]

# ── 消息 ──
@app.get("/api/messages")
async def list_conversations(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    rows = await pool.fetch("""
        SELECT DISTINCT ON (CASE WHEN sender_id=$1 THEN receiver_id ELSE sender_id END)
            CASE WHEN sender_id=$1 THEN receiver_id ELSE sender_id END as uid,
            u.name, u.student_id, u.id
        FROM messages m JOIN users u ON (CASE WHEN m.sender_id=$1 THEN m.receiver_id ELSE m.sender_id END)=u.id
        WHERE m.sender_id=$1 OR m.receiver_id=$1
        ORDER BY CASE WHEN sender_id=$1 THEN receiver_id ELSE sender_id END, m.created_at DESC
    """, user["id"])
    return [dict(r) for r in rows]

@app.get("/api/messages/{uid}")
async def get_messages(uid: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    rows = await pool.fetch("""
        SELECT m.*, u.name as sender_name FROM messages m
        LEFT JOIN users u ON m.sender_id=u.id
        WHERE (m.sender_id=$1 AND m.receiver_id=$2) OR (m.sender_id=$2 AND m.receiver_id=$1)
        ORDER BY m.created_at LIMIT 100
    """, user["id"], uid)
    return [dict(r) for r in rows]

@app.post("/api/messages")
@limiter.limit("60/hour")
async def send_message(req: MessageCreate, request: Request = None, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    await pool.execute("INSERT INTO messages(sender_id,receiver_id,content) VALUES($1,$2,$3)",
        user["id"], req.to, req.content)
    return {"ok": True}

@app.post("/api/activities/{activity_id}/lottery")
async def draw_lottery(activity_id: int, count: int = 0,
                       user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    act = await database.get_activity(activity_id)
    if not act:
        raise HTTPException(404)
    if not _can_manage_act(act, user):
        raise HTTPException(403, "无权操作此活动")
    if act.get("signup_mode", "lottery") != "lottery":
        raise HTTPException(400, "仅抽签模式可进行抽签操作")
    if act["status"] != "published":
        raise HTTPException(400, "活动已结束，无法抽签")
    max_select = count if count > 0 else (act["max_participants"] or 0)
    if max_select <= 0:
        raise HTTPException(400, "请指定抽签人数")
    return {"selected": await database.draw_lottery(activity_id, max_select)}


# ====== 协助 ======

@app.post("/api/activities/join-assist")
async def join_assist(req: dict, user: dict = Depends(get_current_user)):
    code = (req.get("code") or "").strip().upper()
    if not code.startswith("HLP"): raise HTTPException(400, "无效的协助码")
    pool = await database.get_pool()
    ac = await pool.fetchrow("SELECT ac.*, a.title, a.created_by FROM assist_codes ac JOIN activities a ON ac.activity_id=a.id WHERE ac.code=$1", code)
    if not ac: raise HTTPException(400, "协助码不存在或已失效")
    aid = ac["activity_id"]
    if ac["created_by"] == user["id"]: raise HTTPException(400, "不能协助自己发布的活动")
    existing = await pool.fetchrow("SELECT id FROM assist_members WHERE activity_id=$1 AND user_id=$2", aid, user["id"])
    if existing: raise HTTPException(400, "你已经是该活动的协助者")
    await pool.execute("INSERT INTO assist_members(activity_id,user_id,code) VALUES($1,$2,$3)", aid, user["id"], code)
    return {"ok": True, "activity_id": aid, "title": ac["title"]}

@app.get("/api/activities/{aid}/assistants")
async def list_assistants(aid: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT am.*, u.name as user_name, u.student_id FROM assist_members am JOIN users u ON am.user_id=u.id WHERE am.activity_id=$1 ORDER BY am.joined_at", aid)
    return [dict(r) for r in rows]

# ====== Photo Upload ======
import shutil, uuid as uuid_mod

@app.post("/api/upload")
@limiter.limit("30/hour")
async def upload_photo(request: Request, user: dict = Depends(get_current_user)):
    """上传活动图片。返回图片URL。"""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(400, "请使用multipart/form-data上传")
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(400, "未选择文件")
    # 限制类型和大小
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(400, "仅支持JPG/PNG/WebP/GIF")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(400, "图片最大10MB")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in ("jpg","jpeg","png","webp","gif"): ext = "jpg"
    fname = f"{uuid_mod.uuid4().hex}.jpg"
    path = BASE_DIR / "static" / "uploads" / fname
    # Compress: resize to max 1920px, JPEG quality 85
    try:
        from PIL import Image
        import io as pil_io
        img = Image.open(pil_io.BytesIO(content))
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        w, h = img.size
        if w > 1920 or h > 1920:
            ratio = 1920 / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        img.save(path, "JPEG", quality=85, optimize=True)
    except Exception:
        with open(path, "wb") as f:
            f.write(content)
    return {"url": f"/api/uploads/{fname}"}


@app.get("/api/uploads/{filename}")
async def serve_upload(filename: str, user: dict = Depends(get_current_user)):
    """Serve uploaded files with auth check. Only allow images."""
    safe = os.path.basename(filename)
    path = BASE_DIR / "static" / "uploads" / safe
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(ext, "application/octet-stream")
    return FileResponse(path, media_type=media_type)


# ====== Review-based Approval ======

@app.post("/api/activities/{activity_id}/approve/{student_id}")
async def approve_signup(activity_id: int, student_id: str,
                         user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if not _can_manage_act(act, user): raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    u = await pool.fetchrow("SELECT id FROM users WHERE student_id=$1", student_id)
    if not u: raise HTTPException(404, "学生不存在")
    ok = await database.approve_signup(activity_id, u["id"])
    if not ok: raise HTTPException(400, "审批失败")
    await database.create_notification(u["id"], "approve", "报名通过", "你的报名申请已被通过")
    return {"ok": True}

@app.post("/api/activities/{activity_id}/reject/{student_id}")
async def reject_signup(activity_id: int, student_id: str,
                        user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if not _can_manage_act(act, user): raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    u = await pool.fetchrow("SELECT id FROM users WHERE student_id=$1", student_id)
    if not u: raise HTTPException(404, "学生不存在")
    ok = await database.reject_signup(activity_id, u["id"])
    if not ok: raise HTTPException(400, "操作失败")
    return {"ok": True}

@app.post("/api/activities/{activity_id}/approve")
async def approve_signup_body(activity_id: int, req: ApproveRejectBody,
                              user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """Alternative approve — student_id from body instead of path. Used by Flutter."""
    sid = req.student_id
    if not sid:
        raise HTTPException(400, "请提供学生学号")
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if not _can_manage_act(act, user): raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    u = await pool.fetchrow("SELECT id FROM users WHERE student_id=$1", sid)
    if not u: raise HTTPException(404, "学生不存在")
    ok = await database.approve_signup(activity_id, u["id"])
    if not ok: raise HTTPException(400, "审批失败")
    await database.create_notification(u["id"], "approve", "报名通过", "你的报名申请已被通过")
    audit_logger.info(f"AUDIT: approve_signup_body activity={activity_id} student={sid} by={user['id']}")
    return {"ok": True}

@app.post("/api/activities/{activity_id}/reject")
async def reject_signup_body(activity_id: int, req: ApproveRejectBody,
                             user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """Alternative reject — student_id from body instead of path. Used by Flutter."""
    sid = req.student_id
    if not sid:
        raise HTTPException(400, "请提供学生学号")
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404)
    if not _can_manage_act(act, user): raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    u = await pool.fetchrow("SELECT id FROM users WHERE student_id=$1", sid)
    if not u: raise HTTPException(404, "学生不存在")
    ok = await database.reject_signup(activity_id, u["id"])
    if not ok: raise HTTPException(400, "操作失败")
    audit_logger.info(f"AUDIT: reject_signup_body activity={activity_id} student={sid} by={user['id']}")
    return {"ok": True}


# ====== Substitute Student ======

@app.post("/api/activities/{activity_id}/substitute")
async def substitute_student(activity_id: int, req: dict,
                             user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """替换中签学生：旧学生取消→候补学生中签"""
    old_id = req.get("old_student_id", "")
    new_id = req.get("new_student_id", "")
    if not old_id or not new_id:
        raise HTTPException(400, "请提供旧学号和新学号")
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 找到旧用户
            old_user = await conn.fetchrow("SELECT id FROM users WHERE student_id=$1", old_id)
            if not old_user:
                raise HTTPException(400, f"旧学号 {old_id} 不存在")
            # 找到新用户
            new_user = await conn.fetchrow("SELECT id FROM users WHERE student_id=$1", new_id)
            if not new_user:
                raise HTTPException(400, f"新学号 {new_id} 不存在")
            # 确认旧用户已中签（加锁防竞态）
            old_signup = await conn.fetchrow(
                "SELECT id FROM signups WHERE activity_id=$1 AND user_id=$2 AND status='selected' FOR UPDATE",
                activity_id, old_user["id"]
            )
            if not old_signup:
                raise HTTPException(400, f"该学生不是中签状态")
            # 确认新用户在候补或未报名（加锁防竞态）
            new_signup = await conn.fetchrow(
                "SELECT id,status FROM signups WHERE activity_id=$1 AND user_id=$2 FOR UPDATE",
                activity_id, new_user["id"]
            )
            # 取消旧用户
            await conn.execute(
                "UPDATE signups SET status='cancelled' WHERE id=$1",
                old_signup["id"]
            )
            if new_signup:
                # 更新新用户状态
                await conn.execute(
                    "UPDATE signups SET status='selected' WHERE id=$1",
                    new_signup["id"]
                )
            else:
                # 新用户直接插入为selected
                await conn.execute(
                    "INSERT INTO signups (activity_id,user_id,role,status) VALUES ($1,$2,'participant','selected')",
                    activity_id, new_user["id"]
                )
            # 通知双方
            await conn.execute("INSERT INTO notifications (user_id, type, title, content) VALUES ($1,$2,$3,$4)",
                old_user["id"], "substitute", "人员替换", f"你已被替换，由 {new_id} 接替")
            await conn.execute("INSERT INTO notifications (user_id, type, title, content) VALUES ($1,$2,$3,$4)",
                new_user["id"], "substitute", "替补中签", f"你已替补中签活动")
    return {"ok": True, "message": f"{old_id} → {new_id} 替换成功"}


# ====== Anonymous Feedback ======

@app.post("/api/feedback")
async def submit_feedback(req: dict, user: dict = Depends(get_current_user)):
    """匿名建议投诉——用户端显示匿名，后端记录真实ID防滥用"""
    content = req.get("content", "").strip()
    if not content or len(content) < 5:
        raise HTTPException(400, "内容至少5个字")
    if len(content) > 2000:
        raise HTTPException(400, "内容不超过2000字")
    pool = await database.get_pool()
    await pool.execute(
        "INSERT INTO feedbacks (user_id, content, display_name) VALUES ($1,$2,'匿名用户')",
        user["id"], content
    )
    return {"ok": True, "message": "反馈已匿名提交"}

@app.get("/api/feedback")
async def list_feedback(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    if user["role"] in ("teacher","college_admin","school_admin"):
        rows = await pool.fetch("SELECT id, display_name, content, created_at FROM feedbacks ORDER BY created_at DESC LIMIT 100")
    else:
        rows = await pool.fetch("SELECT id, display_name, content, created_at FROM feedbacks WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50", user["id"])
    return [dict(r) for r in rows]

@app.delete("/api/feedback/{fid}")
async def delete_feedback(fid: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    await pool.execute("DELETE FROM feedbacks WHERE id=$1 AND user_id=$2", fid, user["id"])
    return {"ok": True}


# ====== Cancel Signup ======

@app.post("/api/activities/{activity_id}/cancel-signup")
@app.delete("/api/activities/{activity_id}/signup")
async def cancel_signup(activity_id: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    uid = user["id"]

    # Get activity + signup info
    act = await pool.fetchrow(
        "SELECT a.signup_mode, a.status, a.deadline, a.cancel_deadline_lock, a.lottery_drawn_at, s.status as signup_status "
        "FROM activities a JOIN signups s ON s.activity_id=a.id AND s.user_id=$2 WHERE a.id=$1",
        activity_id, uid
    )
    if not act:
        raise HTTPException(400, "未报名或活动不存在")

    signup_status = act["signup_status"]
    is_lottery = act["signup_mode"] == "lottery"
    is_ended = act["status"] in ("ended", "completed")

    # === LOTTERY ACTIVITY: post-lottery cancel logic ===
    if is_lottery and is_ended and signup_status == "selected":
        lottery_at = act.get("lottery_drawn_at")
        if lottery_at:
            elapsed = (datetime.now() - lottery_at).total_seconds()
            if elapsed > 300:  # 5 minutes
                raise HTTPException(400, "抽签结束已超过5分钟，中签名额已锁定，无法取消。请联系发布者处理")
            # Within 5 min: cancel + auto-promote waitlist
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Mark current as cancelled
                    await conn.execute(
                        "UPDATE signups SET status='cancelled' WHERE activity_id=$1 AND user_id=$2",
                        activity_id, uid
                    )
                    # Auto-promote first waitlist to selected
                    next_wl = await conn.fetchrow(
                        "SELECT id, user_id FROM signups WHERE activity_id=$1 AND status='waitlist' ORDER BY created_at ASC LIMIT 1",
                        activity_id
                    )
                    if next_wl:
                        await conn.execute(
                            "UPDATE signups SET status='selected' WHERE id=$1",
                            next_wl["id"]
                        )
                        # Notify promoted student
                        act_title = await conn.fetchval("SELECT title FROM activities WHERE id=$1", activity_id)
                        await conn.execute(
                            "INSERT INTO notifications (user_id, type, title, content) VALUES ($1,'lottery','候补中签', $2)",
                            next_wl["user_id"], f"你已候补中签活动「{act_title}」，请等待发布者完结发放学时"
                        )
                        return {"ok": True, "message": "已取消报名，候补已自动递补", "promoted": True}
                    return {"ok": True, "message": "已取消报名", "promoted": False}
        else:
            # No lottery_drawn_at set (shouldn't happen), allow cancel
            pass

    # === Non-lottery or pre-lottery: standard cancel ===
    # Check deadline lock
    if act.get("deadline") and act["deadline"].strip():
        try:
            if datetime.strptime((act["deadline"]+':00')[:19], "%Y-%m-%d %H:%M:%S") < datetime.now():
                if act.get("cancel_deadline_lock"):
                    raise HTTPException(400, "报名已截止且开启截止锁定，取消需发布者审批")
                elif not is_lottery:
                    raise HTTPException(400, "报名已截止，无法取消")
        except HTTPException: raise
        except Exception as e:
            logger.warning(f"Non-critical error in cancel_signup deadline parsing: {e}")

    # Execute cancel (DELETE for non-lottery or pre-lottery)
    result = await pool.execute(
        "DELETE FROM signups WHERE activity_id=$1 AND user_id=$2",
        activity_id, uid
    )
    if result == "DELETE 0":
        raise HTTPException(400, "取消失败：未报名")
    return {"ok": True}


# ====== Invites & Import ======

@app.post("/api/activities/{activity_id}/invite-code")
async def create_invite(activity_id: int, user: dict = Depends(get_current_user)):
    # 检查是否已报名（任何已报名学生都可生成邀请码）
    pool = await database.get_pool()
    signup = await pool.fetchrow("SELECT id FROM signups WHERE activity_id=$1 AND user_id=$2", activity_id, user["id"])
    if not signup and user["role"] not in ("teacher","college_admin","school_admin"):
        raise HTTPException(400, "请先报名活动")
    # TODO: 每人每活动限3个(需加created_by列到staff_invites表)
    return {"code": await database.create_invite_code(activity_id)}

@app.post("/api/invite/join")
async def join_by_invite(code: str = "", user: dict = Depends(get_current_user)):
    aid = await database.use_invite_code(code, user["id"])
    if not aid:
        raise HTTPException(400, "邀请码无效、已过期或已被使用")
    return {"activity_id": aid}

@app.post("/api/activities/{activity_id}/import-staff")
async def import_staff(activity_id: int, req: BatchImportRequest,
                       user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    import re
    ids = re.split(r'[,，\s\n]+', req.student_ids.strip())
    ids = [s.strip() for s in ids if s.strip()]
    if not ids:
        raise HTTPException(400, "请提供学号列表")
    if len(ids) > 500:
        raise HTTPException(400, "单次最多导入500人")
    pool = await database.get_pool()
    added, not_found = [], []
    for sid in ids:
        u = await database.get_user(sid)
        if not u:
            not_found.append(sid)
            continue
        if await database.signup_activity(activity_id, u["id"], role="staff") == "ok":
            added.append(sid)
    return {"added": len(added), "not_found": not_found}


# ====== Notices ======

@app.get("/api/notices")
async def list_notices(user: dict = Depends(get_current_user)):
    cache_key = f"notices:{user.get('college','')}"
    cached = await cache_get(cache_key)
    if cached: return cached
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT n.*, u.name as creator_name FROM notifications n LEFT JOIN users u ON n.created_by=u.id WHERE n.type='notice' ORDER BY n.created_at DESC LIMIT 50"
    )
    result = [dict(r) for r in rows]
    await cache_set(cache_key, result, CACHE_TTL["notices"])
    return result

@app.get("/api/notices/{nid}")
async def get_notice(nid: int, user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    n = await pool.fetchrow("SELECT n.*, u.name as creator_name FROM notifications n LEFT JOIN users u ON n.created_by=u.id WHERE n.id=$1 AND n.type='notice'", nid)
    if not n: raise HTTPException(404, "公告不存在")
    return dict(n)

@app.post("/api/notices")
@limiter.limit("10/hour")
async def create_notice(req: NoticeCreate, request: Request, user: dict = require_role("teacher", "college_admin", "school_admin")):
    # 防钓鱼/防冒充 — 屏蔽所有行政单位前缀
    _impersonate_prefixes = ('【系统', '【官方', '【教务', '【学工', '【学生', '【财务', '【学校', '【校园通知', '【紧急通知', '【重要通知')
    for pfx in _impersonate_prefixes:
        if pfx in req.title:
            raise HTTPException(400, "禁止冒充系统通知")
    # URL检测 — 需有关键词佐证是合法校内链接
    if re.search(r'https?://|intent://|market://|tel://|sms://|data:', req.content):
        if not any(keyword in req.content for keyword in ('校内', '活动', '报名', '通知', '附件', '详情', '查看', '链接')):
            raise HTTPException(400, "公告内容包含可疑链接")
    pool = await database.get_pool()
    extra = {}
    if req.is_pinned:
        extra["is_pinned"] = True
        extra["pin_days"] = req.pin_days
    if req.image_url:
        extra["image_url"] = req.image_url
    if req.scope_type:
        extra["scope_type"] = req.scope_type
        extra["scope_value"] = req.scope_value
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else "{}"
    # Scope filtering
    if req.scope_type == "internal" and req.scope_value:
        colleges = [c.strip() for c in req.scope_value.split(",") if c.strip()]
        if colleges:
            placeholders = ",".join(f"${i+1}" for i in range(len(colleges)))
            users = await pool.fetch(f"SELECT id FROM users WHERE college IN ({placeholders})", *colleges)
        else:
            users = await pool.fetch("SELECT id FROM users")
    else:
        users = await pool.fetch("SELECT id FROM users")
    for u in users:
        await database.create_notification(u["id"], "notice", req.title, req.content, created_by=user["id"])
        if extra:
            await pool.execute(
                "UPDATE notifications SET extra_data=$1 WHERE id=(SELECT id FROM notifications WHERE user_id=$2 AND type='notice' AND created_by=$3 ORDER BY id DESC LIMIT 1)",
                extra_json, u["id"], user["id"]
            )
    await cache_delete("notices:*")
    # Trigger push notification
    asyncio.create_task(_send_push(req.title, req.content[:100] if req.content else "新公告已发布"))
    return {"sent_to": len(users)}

@app.put("/api/notices/{nid}")
async def edit_notice(nid: int, req: dict = Body(...), user: dict = require_role("teacher", "college_admin", "school_admin")):
    """编辑公告"""
    pool = await database.get_pool()
    # Ownership check: only the creator or school_admin can edit
    notice = await pool.fetchrow("SELECT created_by FROM notifications WHERE id=$1 AND type='notice'", nid)
    if not notice:
        raise HTTPException(404, "公告不存在")
    if notice["created_by"] != user["id"] and user["role"] != "school_admin":
        raise HTTPException(403, "只能编辑自己发布的公告")
    # 防钓鱼过滤器（编辑时也需检查）
    title = req.get("title", "")
    content = req.get("content", "")
    _impersonate_prefixes = ('【系统', '【官方', '【教务', '【学工', '【学生', '【财务', '【学校')
    for pfx in _impersonate_prefixes:
        if pfx in title:
            raise HTTPException(400, "禁止冒充系统通知")
    title = _sanitize_html(title)
    content = _sanitize_html(content)
    if re.search(r'https?://|intent://|market://|data:', content):
        if not any(kw in content for kw in ('校内', '活动', '报名', '通知', '附件', '详情', '查看')):
            raise HTTPException(400, "公告内容包含可疑链接")
    await pool.execute(
        "UPDATE notifications SET title=$1, content=$2, edited_at=NOW() WHERE id=$3 AND type='notice'",
        title, content, nid
    )
    await cache_delete("notices:*")
    return {"ok": True}

@app.post("/api/notices/{nid}/delete")
async def delete_notice(nid: int, user: dict = require_role("teacher", "college_admin", "school_admin")):
    """撤回公告"""
    pool = await database.get_pool()
    notice = await pool.fetchrow("SELECT created_by FROM notifications WHERE id=$1 AND type='notice'", nid)
    if not notice:
        raise HTTPException(404, "公告不存在")
    if notice["created_by"] != user["id"] and user["role"] != "school_admin":
        raise HTTPException(403, "只能删除自己发布的公告")
    await pool.execute("DELETE FROM notifications WHERE id=$1 AND type='notice'", nid)
    await cache_delete("notices:*")
    return {"ok": True}

@app.post("/api/notices/{nid}/pin")
async def pin_notice(nid: int, user: dict = require_role("teacher", "college_admin", "school_admin")):
    """置顶/取消置顶公告"""
    pool = await database.get_pool()
    notice = await pool.fetchrow("SELECT created_by FROM notifications WHERE id=$1 AND type='notice'", nid)
    if not notice:
        raise HTTPException(404, "公告不存在")
    if notice["created_by"] != user["id"] and user["role"] != "school_admin":
        raise HTTPException(403, "只能操作自己发布的公告")
    await pool.execute(
        "UPDATE notifications SET is_pinned = NOT is_pinned WHERE id=$1 AND type='notice'", nid
    )
    await cache_delete("notices:*")
    return {"ok": True}


# ====== Users (admin) ======

@app.get("/api/users")
async def list_users(user: dict = require_role("teacher", "college_admin", "school_admin")):
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT id, student_id, name, class, college, role, created_at FROM users ORDER BY id"
    )
    return [dict(r) for r in rows]

@app.post("/api/auth/reset-password")
@limiter.limit("3/minute")
async def auth_reset_password(request: Request, req: dict = Body(...)):
    """学生自助密码找回——通过手机号+姓名+学号验证"""
    name = (req.get("name") or "").strip()
    phone = (req.get("phone") or "").strip()
    student_id = (req.get("student_id") or "").strip()
    new_pw = (req.get("new_password") or "").strip()
    if not name or not phone or not student_id:
        raise HTTPException(400, "请填写姓名、手机号和学号")
    if len(new_pw) < 6:
        raise HTTPException(400, "新密码至少6位")
    pool = await database.get_pool()
    user = await pool.fetchrow("SELECT id FROM users WHERE name=$1 AND phone=$2 AND student_id=$3", name, phone, student_id)
    if not user: raise HTTPException(400, "手机号、姓名或学号不正确")
    # 5-minute cooldown per phone number
    last_reset = _pw_reset_cooldowns.get(phone, 0)
    if time.time() - last_reset < 300:
        raise HTTPException(429, "请等待5分钟后再试")
    new_hash = _hash_pw(new_pw)
    await pool.execute("UPDATE users SET password_hash=$1 WHERE id=$2", new_hash, user["id"])
    _pw_reset_cooldowns[phone] = time.time()
    # Log the reset
    client_ip = request.client.host if request else "unknown"
    audit_logger.info(f"AUDIT: password_reset user_id={user['id']} ip={client_ip} time={datetime.now().isoformat()}")
    return {"ok": True}

@app.post("/api/users/reset-password")
async def reset_password(request: Request, req: dict, user: dict = require_role("teacher", "college_admin", "school_admin")):
    sid = req.get("student_id")
    mode = req.get("mode", "direct")  # "direct"=管理员直接设, "auto"=生成6位临时密码
    pool = await database.get_pool()
    target = await pool.fetchrow("SELECT id FROM users WHERE student_id=$1", sid)
    if not target:
        raise HTTPException(404, "学生不存在")

    if mode == "auto":
        import random
        temp_code = f"{random.randint(100000, 999999)}"
        temp_hash = bcrypt.hashpw(temp_code.encode(), bcrypt.gensalt()).decode()
        await pool.execute(
            "UPDATE users SET temp_password_hash=$1, temp_password_exp=NOW() + INTERVAL '10 minutes', must_change_password=TRUE WHERE student_id=$2",
            temp_hash, sid
        )
        await database.create_notification(target["id"], "todo",
            "密码已重置", "管理员已为您重置密码，请使用临时密码登录（10分钟内有效，登录后请修改）")
        audit_logger.info(f"AUDIT: temp_password by={user['id']} target={sid} code_hidden")
        return {"ok": True, "temp_password": temp_code, "expires_in": 600}
    else:
        new_pwd = req.get("new_password")
        if not new_pwd:
            raise HTTPException(400, "请提供新密码")
        if len(new_pwd) < 1:
            raise HTTPException(400, "密码不能为空")
        new_hash = _hash_pw(new_pwd)
        await pool.execute(
            "UPDATE users SET password_hash=$1, temp_password_hash=NULL, temp_password_exp=NULL, must_change_password=FALSE WHERE student_id=$2",
            new_hash, sid
        )
        await database.create_notification(target["id"], "todo",
            "密码已重置", "你的密码已被管理员重置，如非本人操作请联系管理员")
        audit_logger.info(f"AUDIT: password_reset by={user['id']} target={sid} ip={request.client.host}")
        return {"ok": True}

@app.post("/api/users/set-role")
async def set_role(req: SetRoleRequest, user: dict = require_role("college_admin", "school_admin")):
    """任命/撤销角色。撤销时检查30天冷却期。"""
    # college_admin can only set student/teacher/publisher roles
    if user["role"] == "college_admin" and req.role not in ("student", "teacher", "publisher"):
        raise HTTPException(403, "学院管理员无权设置此角色")
    # Only school_admin can set college_admin or school_admin
    if req.role in ("college_admin", "school_admin") and user["role"] != "school_admin":
        raise HTTPException(403, "仅超级管理员可设置此角色")
    pool = await database.get_pool()
    target = await pool.fetchrow("SELECT id, role FROM users WHERE student_id=$1", req.student_id)
    if not target: raise HTTPException(404, "用户不存在")

    # 撤销操作检查冷却期
    if req.role == "student" and target["role"] in ("teacher", "college_admin"):
        last = await pool.fetchrow(
            "SELECT created_at FROM role_changes WHERE user_id=$1 AND new_role='student' ORDER BY created_at DESC LIMIT 1",
            target["id"]
        )
        if last:
            cooldown = last["created_at"] + timedelta(days=30)
            if datetime.now() < cooldown:
                remaining = (cooldown - datetime.now()).days
                raise HTTPException(400, f"撤销冷却期还剩{remaining}天，30天内不能重复撤销")

    old_role = target["role"]
    action = "任命" if req.role != "student" else "撤销"
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE users SET role=$1 WHERE student_id=$2", req.role, req.student_id)
            await conn.execute(
                "INSERT INTO role_changes(user_id, old_role, new_role, changed_by, reason) VALUES($1,$2,$3,$4,$5)",
                target["id"], old_role, req.role, user["id"], req.reason or ""
            )
            await conn.execute(
                "INSERT INTO notifications(user_id,type,title,content) VALUES($1,'system',$2,$3)",
                target["id"],
                f"角色被{action}",
                f"你的角色已从{old_role}变为{req.role}" + (f"，原因: {req.reason}" if req.reason else "")
            )
    audit_logger.info(f"AUDIT: role_change by={user['id']} target={req.student_id} old={old_role} new={req.role}")
    return {"ok": True}


# ====== 可转义工→义工时长转换 (线13) ======

@app.post("/api/me/convert-hours")
async def apply_convert_hours(req: dict = Body(...), user: dict = Depends(get_current_user)):
    """学生申请将可转义工时长转为义工时长"""
    pool = await database.get_pool()
    # 查可转义工时长（跟/api/my-stats逻辑一致）
    total = await pool.fetchval("SELECT COALESCE(SUM(c.hours),0) FROM certificates c JOIN activities a ON c.activity_id=a.id WHERE c.user_id=$1 AND a.category IN ('volunteer_convertible')", user["id"]) or 0
    convertible = float(total)
    hours = float(req.get("hours", 0) or 0)
    if hours <= 0: raise HTTPException(400, "请填写转换小时数")
    if hours > convertible: raise HTTPException(400, f"转换数不能超过可转义工时长({convertible}h)")
    reason = (req.get("reason") or "").strip()
    if len(reason) < 10: raise HTTPException(400, "申请理由至少10字")

    tr = await pool.fetchrow("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1 LIMIT 1", user.get("college",""))
    if not tr: raise HTTPException(400, "本院暂无老师")

    await pool.execute(
        "INSERT INTO convert_applications(user_id, requested_hours, reason, teacher_id) VALUES($1,$2,$3,$4)",
        user["id"], hours, reason, tr["id"]
    )
    await pool.execute(
        "INSERT INTO notifications(user_id,type,title,content) VALUES($1,'publish_request','🔄 义工转换申请',$2)",
        tr["id"], f"{user['name']}申请将{hours}h可转义工转为义工时长 | {reason[:60]}"
    )
    return {"ok": True, "message": f"已提交{hours}h转换申请，等待老师审批"}

@app.get("/api/convert-applications")
async def list_convert_apps(user: dict = Depends(get_current_user)):
    """老师查看待审批的转换申请"""
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT c.*, u.name as applicant_name, u.student_id FROM convert_applications c JOIN users u ON c.user_id=u.id WHERE c.teacher_id=$1 AND c.status='pending' ORDER BY c.created_at DESC LIMIT 50",
        user["id"]
    )
    return [dict(r) for r in rows]

@app.post("/api/convert-applications/{app_id}/approve")
async def approve_convert(app_id: int, user: dict = Depends(get_current_user)):
    """老师批准转换→可转义工减Xh,义工时长加Xh"""
    pool = await database.get_pool()
    app = await pool.fetchrow("SELECT * FROM convert_applications WHERE id=$1 AND teacher_id=$2", app_id, user["id"])
    if not app: raise HTTPException(404, "申请不存在")
    if app["status"] != "pending": raise HTTPException(400, "已处理")
    hours = app["requested_hours"]
    await pool.execute("UPDATE convert_applications SET status='approved' WHERE id=$1", app_id)
    # 注: 实际时长转移需后端统计数据表支持, 此处记录状态
    await pool.execute(
        "INSERT INTO notifications(user_id,type,title,content) VALUES($1,'approval','✅ 义工转换已批准','')",
        app["user_id"], f"你的{hours}h可转义工已转为义工时长"
    )
    return {"ok": True, "hours": hours}

@app.post("/api/convert-applications/{app_id}/reject")
async def reject_convert(app_id: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """老师拒绝转换申请"""
    pool = await database.get_pool()
    app = await pool.fetchrow("SELECT * FROM convert_applications WHERE id=$1 AND teacher_id=$2", app_id, user["id"])
    if not app: raise HTTPException(404)
    reason = (req.get("reason") or "").strip()
    if len(reason) < 5: raise HTTPException(400, "拒绝原因至少5字")
    await pool.execute("UPDATE convert_applications SET status='rejected', reason=$1 WHERE id=$2", reason, app_id)
    await pool.execute(
        "INSERT INTO notifications(user_id,type,title,content) VALUES($1,'rejection','❌ 义工转换被拒','')",
        app["user_id"], f"义工转换申请被拒绝，原因: {reason}"
    )
    return {"ok": True}

# ====== 内部活动 INT码 (线12) ======

@app.post("/api/activities/internal")
async def create_internal_activity(req: dict = Body(...), user: dict = Depends(get_current_user)):
    """发布内部活动。简化表单: 标题+时间+时长。生成INT-XXXX码。"""
    if user["role"] not in ("teacher","college_admin","school_admin") and not user.get("can_publish"):
        raise HTTPException(400, "请先获取发布权限")
    title = (req.get("title") or "").strip()
    if not title or len(title) > 30: raise HTTPException(400, "标题1-30字")
    activity_date = (req.get("activity_date") or "").strip()
    if not activity_date: raise HTTPException(400, "请填写活动时间")
    hours = float(req.get("hours", 0) or 0)
    if hours <= 0: raise HTTPException(400, "请填写时长")

    pool = await database.get_pool()
    # 生成唯一INT码 4位数字
    import random
    for _ in range(10):
        int_code = f"INT-{secrets.token_hex(4).upper()}"
        exist = await pool.fetchval("SELECT id FROM activities WHERE internal_code=$1", int_code)
        if not exist: break
    else:
        raise HTTPException(500, "生成内部码失败，请重试")

    aid = await pool.fetchval(
        "INSERT INTO activities(title,description,category,scope_type,created_by,status,participant_hours,activity_date,internal_code) VALUES($1,$2,'internal','internal',$3,'published',$4,$5,$6) RETURNING id",
        title, req.get("description",""), user["id"], hours, activity_date, int_code
    )
    # 通知本院老师
    teachers = await pool.fetch("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1", user.get("college",""))
    for t in teachers:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','🏠 新的内部活动',$2)",
            t["id"], f"[aid:{aid}]{user['name']}发布了内部活动「{title}」，内部码:{int_code}")
    # 通知发布者自己
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','✅ 内部活动已发布',$2)",
        user["id"], f"[aid:{aid}]内部活动「{title}」已发布，内部码:{int_code}，时长{hours}h")
    return {"ok": True, "id": aid, "internal_code": int_code}

@app.get("/api/activities/internal")
async def list_internal_activities(user: dict = Depends(get_current_user)):
    """老师查看本院内部活动"""
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT a.*, u.name as creator_name FROM activities a JOIN users u ON a.created_by=u.id WHERE a.scope_type='internal' AND u.college=$1 ORDER BY a.created_at DESC LIMIT 50",
        user.get("college","")
    )
    return [dict(r) for r in rows]

@app.post("/api/activities/internal/join")
@limiter.limit("10/minute")
async def join_internal(request: Request, code: str = "", user: dict = Depends(get_current_user)):
    """学生通过INT码加入内部活动"""
    # Per-user cooldown: 3 failed attempts = 60s lockout
    sid = user.get("student_id", "")
    now = time.time()
    fails = [t for t in _int_cooldown.get(sid, []) if now - t < 60]
    if len(fails) >= 3:
        raise HTTPException(429, "尝试次数过多，请60秒后再试")

    code = code.strip().upper()
    if not code.startswith("INT-") or len(code) != 10:
        _int_cooldown.setdefault(sid, []).append(time.time())
        raise HTTPException(400, "内部码格式错误")

    pool = await database.get_pool()
    act = await pool.fetchrow("SELECT * FROM activities WHERE internal_code=$1 AND status='published'", code)
    if not act:
        _int_cooldown.setdefault(sid, []).append(time.time())
        raise HTTPException(400, "内部码无效或活动已结束")

    # 检查是否已加入
    exist = await pool.fetchrow("SELECT id FROM signups WHERE activity_id=$1 AND user_id=$2", act["id"], user["id"])
    if exist: raise HTTPException(400, "你已经加入过这个活动")

    await pool.execute("INSERT INTO signups(activity_id,user_id,status) VALUES($1,$2,'checked_in')", act["id"], user["id"])
    # 成功后清除失败记录
    _int_cooldown.pop(sid, None)
    # 通知发布者
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','👤 新成员加入',$2)",
        act["created_by"], f"[aid:{act['id']}]{user['name']}({user['student_id']})通过内部码加入了「{act['title']}」")
    # 通知本院老师
    teachers = await pool.fetch("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1", user.get("college",""))
    for t in teachers:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','👤 新成员加入内部活动',$2)",
            t["id"], f"[aid:{act['id']}]{user['name']}加入了「{act['title']}」")
    return {"ok": True, "activity_id": act["id"], "title": act["title"], "hours": act.get("participant_hours",0)}

# ── 内部活动-手动拉人 ──
@app.get("/api/users/search")
async def search_user(q: str = "", user: dict = require_role("teacher", "college_admin", "school_admin")):
    """按学号搜索用户"""
    if len(q.strip()) < 4:
        raise HTTPException(400, "请至少输入4位学号进行搜索")
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT id, student_id, name, class, college FROM users WHERE student_id LIKE $1 LIMIT 5", f"%{q}%")
    return [dict(r) for r in rows]

@app.post("/api/activities/{activity_id}/add-member")
async def add_member(activity_id: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """手动添加成员到内部活动"""
    act = await database.get_activity(activity_id)
    if not act or act["created_by"] != user["id"]: raise HTTPException(403)
    student_id = (req.get("student_id") or "").strip()
    if not student_id: raise HTTPException(400, "请输入学号")
    pool = await database.get_pool()
    target = await pool.fetchrow("SELECT id, name FROM users WHERE student_id=$1", student_id)
    if not target: raise HTTPException(400, "未找到该学生")
    exist = await pool.fetchrow("SELECT id FROM signups WHERE activity_id=$1 AND user_id=$2", activity_id, target["id"])
    if exist: raise HTTPException(400, "该学生已在活动中")
    await pool.execute("INSERT INTO signups(activity_id,user_id,status) VALUES($1,$2,'checked_in')", activity_id, target["id"])
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','🏠 你被加入内部活动',$2)",
        target["id"], f"[aid:{activity_id}]你被{user['name']}加入「{act['title']}」，获得{act.get('participant_hours',0)}h学时")
    return {"ok": True, "name": target["name"]}

# ====== Organizations ======

@app.post("/api/organizations")
async def create_org(req: dict, user: dict = require_role("teacher", "college_admin", "school_admin")):
    code = secrets.token_hex(4).upper()[:8]
    oid = await database.create_organization(req["name"], req.get("type", "club"), code, user["id"])
    return {"id": oid, "publish_code": code}

@app.get("/api/organizations")
async def list_orgs(user: dict = require_role("teacher", "college_admin", "school_admin")):
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT * FROM organizations ORDER BY id")
    return [dict(r) for r in rows]

@app.post("/api/organizations/{org_id}/revoke-code")
async def revoke_code(org_id: int, user: dict = require_role("teacher", "college_admin", "school_admin")):
    pool = await database.get_pool()
    org = await pool.fetchrow("SELECT * FROM organizations WHERE id=$1", org_id)
    if not org:
        raise HTTPException(404, "组织不存在")
    await database.revoke_publish_code(org["publish_code"])
    return {"ok": True}


# ====== Certificates ======

@app.get("/api/certificates")
async def my_certificates(user: dict = Depends(get_current_user)):
    return await database.get_certificates(user["id"])

@app.post("/api/activities/{activity_id}/certificates")
async def generate_certificates(activity_id: int,
                                user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    act = await database.get_activity(activity_id)
    if not act:
        raise HTTPException(404, "活动不存在")
    signups = await database.get_signups(activity_id)
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            generated = 0
            failed_users = []
            for s in signups:
                if s["status"] not in ("selected", "checked_in") and s["role"] != "staff":
                    continue
                # Use participant_hours/staff_hours; fall back to COALESCE-computed hours if specific column is NULL or 0
                if s["role"] == "staff":
                    sh = act.get("staff_hours")
                    hours = sh if sh not in (None, 0) else (act.get("hours") or 0)
                else:
                    ph = act.get("participant_hours")
                    hours = ph if ph not in (None, 0) else (act.get("hours") or 0)
                try:
                    cert_no = f"CERT-{act['created_at'].strftime('%Y%m%d')}-{activity_id}-{s['user_id']:04d}"
                    await database.create_certificate(activity_id, s["user_id"], hours, cert_no)
                    await conn.execute(
                        "UPDATE users SET volunteer_hours = (SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id = $1) WHERE id = $1",
                        s["user_id"]
                    )
                    generated += 1
                except Exception as e:
                    logger.error(f"Certificate generation failed for user {s['user_id']} in activity {activity_id}: {e}")
                    failed_users.append(s["user_id"])
            if failed_users:
                logger.warning(f"Certificate generation partially failed for activity {activity_id}: {len(failed_users)} users affected: {failed_users}")
    audit_logger.info(f"AUDIT: certs_generated by={user['id']} aid={activity_id} count={generated} failed={len(failed_users)}")
    return {"generated": generated, "failed_users": failed_users if failed_users else None}


# ====== 组织者学时申请 (线11) ======

@app.post("/api/activities/{activity_id}/org-hours-apply")
async def apply_org_hours(activity_id: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """发布者为自己+协助者申请学时。mode: self(自填,老师可改)/apply(让老师定)"""
    pool = await database.get_pool()
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if act["status"] not in ("published", "ended"): raise HTTPException(400, "活动已完结")
    if act["created_by"] != user["id"]: raise HTTPException(400, "仅发布者可申请")

    exist = await pool.fetchrow("SELECT id FROM org_hours_applications WHERE activity_id=$1", activity_id)
    if exist: raise HTTPException(400, "已申请过")

    mode = req.get("mode", "apply")
    message = (req.get("message") or "").strip()
    if len(message) < 10: raise HTTPException(400, "留言至少10字")
    requested_hours = float(req.get("hours", 0) or 0)
    if mode == "self" and requested_hours <= 0: raise HTTPException(400, "请填写时长")

    tr = await pool.fetchrow("SELECT id FROM users WHERE role IN ('teacher','college_admin','school_admin') AND college=$1 LIMIT 1", user.get("college",""))
    if not tr: raise HTTPException(400, "本院暂无老师")

    asst_count = await pool.fetchval("SELECT COUNT(*) FROM assist_members WHERE activity_id=$1", activity_id) or 0

    await pool.execute("INSERT INTO org_hours_applications(activity_id,user_id,mode,requested_hours,message,teacher_id) VALUES($1,$2,$3,$4,$5,$6)",
        activity_id, user["id"], mode, requested_hours, message, tr["id"])
    act_title = act.get("title", "")
    # 通知: 老师
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'publish_request','📝 组织学时申请',$2)",
        tr["id"],
        f"[aid:{activity_id}]{user['name']}申请「{act_title}」组织学时" +
        (f"{requested_hours}h" if mode == "self" else "(让老师决定时长)") +
        f"→发布者+{asst_count}位协助者 | {message[:80]}")
    return {"ok": True, "assistant_count": asst_count}

@app.get("/api/org-hours-applications")
async def list_org_hours_apps(user: dict = Depends(get_current_user)):
    """老师查看待审批的组织学时申请"""
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT a.*, u.name as applicant_name, u.student_id, act.title as activity_title, act.participant_hours as act_hours FROM org_hours_applications a JOIN users u ON a.user_id=u.id JOIN activities act ON a.activity_id=act.id WHERE a.teacher_id=$1 AND a.status='pending' ORDER BY a.created_at DESC LIMIT 50",
        user["id"]
    )
    return [dict(r) for r in rows]

@app.post("/api/org-hours-applications/{app_id}/approve")
async def approve_org_hours(app_id: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """老师批准→发放给发布者+所有协助者。可修改时长。"""
    pool = await database.get_pool()
    app = await pool.fetchrow("SELECT * FROM org_hours_applications WHERE id=$1 AND teacher_id=$2", app_id, user["id"])
    if not app: raise HTTPException(404, "申请不存在")
    if app["status"] != "pending": raise HTTPException(400, "申请已处理")

    hours = float(req.get("hours", app["requested_hours"] or 0))
    if hours <= 0: raise HTTPException(400, "时长必须大于0")
    changed = hours != (app["requested_hours"] or 0)
    aid = app["activity_id"]

    # 获取发布者
    act = await pool.fetchrow("SELECT created_by, title FROM activities WHERE id=$1", aid)
    publisher_id = act["created_by"]
    act_title = act.get("title","")

    # 获取所有协助者
    assistants = await pool.fetch("SELECT user_id FROM assist_members WHERE activity_id=$1", aid)

    # 更新申请状态
    await pool.execute("UPDATE org_hours_applications SET status='approved', approved_hours=$1 WHERE id=$2", hours, app_id)

    # 发放证书给发布者
    cert_pub = f"ORG-{datetime.now().strftime('%Y%m%d')}-{aid}-{publisher_id:04d}"
    await pool.execute("INSERT INTO certificates(activity_id,user_id,hours,certificate_no,created_at) VALUES($1,$2,$3,$4,NOW()) ON CONFLICT DO NOTHING",
        aid, publisher_id, hours, cert_pub)
    await pool.execute(
        "UPDATE users SET volunteer_hours = (SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id = $1) WHERE id = $1",
        publisher_id
    )
    # 通知发布者
    changed_note = f"（老师将{app['requested_hours']}h改为{hours}h）" if changed else ""
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'approval','✅ 组织学时已发放',$2)",
        publisher_id, f"[aid:{aid}]你获得{hours}h「{act_title}」组织学时{changed_note}，证书:{cert_pub}")

    # 发放证书+通知每位协助者
    notified = 1
    for a in assistants:
        uid = a["user_id"]
        cert_a = f"ORG-{datetime.now().strftime('%Y%m%d')}-{aid}-{uid:04d}"
        await pool.execute("INSERT INTO certificates(activity_id,user_id,hours,certificate_no,created_at) VALUES($1,$2,$3,$4,NOW()) ON CONFLICT DO NOTHING",
            aid, uid, hours, cert_a)
        await pool.execute(
            "UPDATE users SET volunteer_hours = (SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id = $1) WHERE id = $1",
            uid
        )
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'approval','✅ 组织学时已发放',$2)",
            uid, f"[aid:{aid}]你获得{hours}h「{act_title}」组织学时，证书:{cert_a}")
        notified += 1
    return {"ok": True, "hours": hours, "notified": notified, "changed": changed}

@app.post("/api/org-hours-applications/{app_id}/reject")
async def reject_org_hours(app_id: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """老师拒绝→通知发布者"""
    pool = await database.get_pool()
    app = await pool.fetchrow("SELECT * FROM org_hours_applications WHERE id=$1 AND teacher_id=$2", app_id, user["id"])
    if not app: raise HTTPException(404, "申请不存在")
    if app["status"] != "pending": raise HTTPException(400, "申请已处理")
    reason = (req.get("reason") or "").strip()
    if len(reason) < 5: raise HTTPException(400, "拒绝原因至少5字")
    await pool.execute("UPDATE org_hours_applications SET status='rejected', reason=$1 WHERE id=$2", reason, app_id)
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'rejection','❌ 组织学时申请被拒',$2)",
        app["user_id"], f"[aid:{app['activity_id']}]组织学时申请被拒绝，原因: {reason}")
    return {"ok": True}

# ── 签到截止时间 ──
@app.post("/api/activities/{activity_id}/checkin-deadline")
async def set_checkin_deadline(activity_id: int, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """发布者设定签到截止时间"""
    act = await database.get_activity(activity_id)
    if not act or act["created_by"] != user["id"]:
        raise HTTPException(403)
    deadline = req.get("deadline")
    pool = await database.get_pool()
    await pool.execute("UPDATE activities SET checkin_deadline=$1 WHERE id=$2", deadline, activity_id)
    return {"ok": True}

# ====== GPS Distance ======

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine公式计算两点球面距离（米）"""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def _validate_gps_range(activity_id: int, lat: float | None, lng: float | None) -> str | None:
    """验证GPS是否在活动50米范围内。返回错误消息或None。"""
    if lat is None or lng is None:
        return "缺少定位信息，请开启GPS后重试"
    if lat == 0 and lng == 0:
        return "定位未就绪，请到开阔区域重试"
    pool = await database.get_pool()
    act = await pool.fetchrow("SELECT latitude, longitude, checkin_enabled FROM activities WHERE id=$1", activity_id)
    if not act:
        return "活动不存在"
    if act["checkin_enabled"] and (not act["latitude"] or not act["longitude"]):
        return "活动未配置签到坐标，请联系发布者"
    if act["latitude"] and act["longitude"]:
        d = _haversine_m(lat, lng, float(act["latitude"]), float(act["longitude"]))
        if d > 50:
            return f"超出签到范围（需在50米以内，当前{d:.0f}米）"
    return None


# ====== QR Check-in ======

import qrcode, io, base64, hashlib

@app.post("/api/activities/{activity_id}/checkin-qr")
async def generate_checkin_qr(activity_id: int, request: Request, user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """为活动生成签到二维码。返回base64图片，前端直接显示。"""
    act = await database.get_activity(activity_id)
    if not act:
        raise HTTPException(404, "活动不存在")
    # 生成签到token
    token_str = f"{activity_id}:{secrets.token_hex(16)}:{int(time.time())}"
    token_hash = hashlib.sha256(token_str.encode()).hexdigest()[:16]
    # 签到URL — 使用可信基URL
    base_url = os.getenv("APP_BASE_URL", "")
    if not base_url:
        raise HTTPException(500, "服务器未配置APP_BASE_URL，无法生成签到二维码")
    checkin_url = f"{base_url}/api/checkin/{activity_id}/{token_hash}"
    # 生成二维码
    img = qrcode.make(checkin_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    # 保存token — 5秒后过期（动态码防截图）
    pool = await database.get_pool()
    expires = datetime.now() + timedelta(seconds=5)
    await pool.execute(
        "INSERT INTO checkin_tokens(activity_id, token_hash, expires_at) VALUES($1,$2,$3)",
        activity_id, token_hash, expires
    )
    return {"qr_base64": f"data:image/png;base64,{b64}", "token": token_hash, "url": checkin_url, "expires_in": 5}

@app.post("/api/checkin/{activity_id}/{token}")
async def do_checkin(activity_id: int, token: str, user: dict = Depends(get_current_user),
                     body: dict = Body(None)):
    """学生扫码签到 — 支持可选GPS定位验证"""
    lat = (body or {}).get("lat") if body else None
    lng = (body or {}).get("lng") if body else None
    pool = await database.get_pool()

    # GPS验证（二层）
    err = await _validate_gps_range(activity_id, lat, lng)
    if err:
        raise HTTPException(400, err)

    # 验证token
    tok = await pool.fetchrow(
        "SELECT * FROM checkin_tokens WHERE activity_id=$1 AND token_hash=$2 AND used_at IS NULL AND expires_at > NOW()",
        activity_id, token
    )
    if not tok:
        raise HTTPException(400, "签到码无效或已过期")
    # 标记token已使用
    await pool.execute("UPDATE checkin_tokens SET used_at=NOW(), used_by=$1 WHERE id=$2", user["id"], tok["id"])
    # 查找报名记录
    row = await pool.fetchrow(
        "UPDATE signups SET status='checked_in', checked_in_at=NOW() "
        "WHERE activity_id=$1 AND user_id=$2 AND status IN ('selected','pending') "
        "RETURNING id",
        activity_id, user["id"]
    )
    if not row:
        raise HTTPException(400, "签到失败：未报名或未中签")
    await database.create_notification(user["id"], "checkin", "签到成功", f"活动签到确认")
    return {"ok": True, "message": "签到成功"}

@app.post("/api/checkin/gps/{activity_id}")
async def gps_checkin(activity_id: int, body: dict = Body(None), user: dict = Depends(get_current_user)):
    """GPS定位签到 — 需在活动地点50米范围内"""
    lat = (body or {}).get("lat")
    lng = (body or {}).get("lng")
    pool = await database.get_pool()

    # GPS验证（二层）
    err = await _validate_gps_range(activity_id, lat, lng)
    if err:
        raise HTTPException(400, err)

    row = await pool.fetchrow(
        "UPDATE signups SET status='checked_in', checked_in_at=NOW() "
        "WHERE activity_id=$1 AND user_id=$2 AND status IN ('selected','pending') "
        "RETURNING id",
        activity_id, user["id"]
    )
    if not row:
        raise HTTPException(400, "签到失败：未报名或未中签")
    await database.create_notification(user["id"], "checkin", "GPS签到成功", f"位置: {lat},{lng}")
    return {"ok": True, "message": "GPS签到成功"}

@app.post("/api/checkin/manual/{signup_id}")
async def manual_checkin(signup_id: int, user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """管理员手动签到"""
    pool = await database.get_pool()
    row = await pool.fetchrow(
        "UPDATE signups SET status='checked_in', checked_in_at=NOW() "
        "WHERE id=$1 AND status IN ('selected','pending') "
        "RETURNING user_id, activity_id",
        signup_id
    )
    if not row:
        raise HTTPException(400, "签到失败：记录不存在或已签到")
    await database.create_notification(row["user_id"], "checkin", "手动签到确认", f"管理员已确认你的到场")
    return {"ok": True, "message": "已签到"}

@app.post("/api/checkin/undo/{signup_id}")
async def undo_checkin(signup_id: int, user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """撤销签到"""
    pool = await database.get_pool()
    row = await pool.fetchrow(
        "UPDATE signups SET status='selected', checked_in_at=NULL "
        "WHERE id=$1 AND status='checked_in' "
        "RETURNING user_id",
        signup_id
    )
    if not row:
        raise HTTPException(400, "撤销失败：记录不存在或未签到")
    await database.create_notification(row["user_id"], "checkin", "签到已撤销", f"管理员已撤销你的签到记录")
    return {"ok": True, "message": "已撤销签到"}


# ====== Appeal System (申诉) ======

@app.post("/api/appeal")
async def submit_appeal(req: dict, user: dict = Depends(get_current_user)):
    """学生提交申诉——支持文字+图片"""
    activity_id = req.get("activity_id", 0)
    reason = req.get("reason", "").strip()
    image_url = req.get("image_url", "")
    if not reason or len(reason) < 10:
        raise HTTPException(400, "申诉原因至少10个字")
    pool = await database.get_pool()
    # 检查是否已报名
    signup = await pool.fetchrow(
        "SELECT id FROM signups WHERE activity_id=$1 AND user_id=$2",
        activity_id, user["id"]
    )
    if not signup: raise HTTPException(400, "未报名该活动")
    await pool.execute(
        "INSERT INTO appeals (activity_id,user_id,reason,image_url) VALUES ($1,$2,$3,$4)",
        activity_id, user["id"], reason, image_url
    )
    return {"ok": True, "message": "申诉已提交"}

@app.get("/api/appeals")
async def list_all_appeals(user: dict = Depends(get_current_user)):
    """老师/管理员查看所有待处理的申诉"""
    if user["role"] not in ("teacher","college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT a.*, u.name as user_name, u.student_id, act.title as activity_title FROM appeals a JOIN users u ON a.user_id=u.id JOIN activities act ON a.activity_id=act.id ORDER BY a.created_at DESC LIMIT 50")
    return [dict(r) for r in rows]

@app.get("/api/appeals/{activity_id}")
async def list_appeals(activity_id: int,
                       user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """管理员查看活动申诉列表"""
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT a.*, u.name, u.student_id FROM appeals a JOIN users u ON a.user_id=u.id WHERE a.activity_id=$1 ORDER BY a.created_at DESC",
        activity_id
    )
    return [dict(r) for r in rows]

@app.post("/api/appeals/{appeal_id}/resolve")
async def resolve_appeal(appeal_id: int, req: dict,
                         user: dict = require_role("teacher", "publisher", "college_admin", "school_admin")):
    """管理员处理申诉——approve/reject"""
    action = req.get("action", "approve")
    pool = await database.get_pool()
    await pool.execute("UPDATE appeals SET status=$1 WHERE id=$2", action, appeal_id)
    return {"ok": True}


# ====== 成绩单 / 统计 ======

@app.get("/api/stats")
async def get_stats(user: dict = require_role("teacher", "college_admin", "school_admin")):
    pool = await database.get_pool()
    users = await pool.fetchval("SELECT count(*) FROM users")
    acts = await pool.fetchval("SELECT count(*) FROM activities")
    signups = await pool.fetchval("SELECT count(*) FROM signups")
    return {"users": users, "activities": acts, "signups": signups}

# ── 数据看板 ──
def _period_dates(period: str):
    """Return (start_date, end_date) or (None, None) for 'all'."""
    now = datetime.now()
    if period == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == 'semester':
        start = datetime(2026, 2, 23)
        return start, now
    return None, None  # 'all'

@app.get("/api/college/dashboard")
async def college_dashboard(period: str = 'all', user: dict = require_role("teacher", "college_admin", "school_admin")):
    pool = await database.get_pool()
    college = user.get("college","")
    start, _ = _period_dates(period)
    if start:
        signups = await pool.fetchval("SELECT count(*) FROM users WHERE college=$1 AND role='student' AND created_at>=$2", college, start) or 0
        activities = await pool.fetchval("SELECT count(*) FROM activities WHERE created_at>=$1", start) or 0
        hours = await pool.fetchval("SELECT COALESCE(SUM(c.hours),0) FROM certificates c JOIN users u ON c.user_id=u.id WHERE u.college=$1 AND c.generated_at>=$2", college, start) or 0
    else:
        signups = await pool.fetchval("SELECT count(*) FROM users WHERE college=$1 AND role='student'", college) or 0
        activities = await pool.fetchval("SELECT count(*) FROM activities") or 0
        hours = await pool.fetchval("SELECT COALESCE(SUM(c.hours),0) FROM certificates c JOIN users u ON c.user_id=u.id WHERE u.college=$1", college) or 0
    return {"activities": activities, "signups": signups, "hours": float(hours), "colleges": []}

@app.get("/api/school/dashboard")
async def school_dashboard(period: str = 'all', user: dict = Depends(get_current_user)):
    if user.get("role") != "school_admin": raise HTTPException(403)
    pool = await database.get_pool()
    start, _ = _period_dates(period)
    if start:
        activities = await pool.fetchval("SELECT count(*) FROM activities WHERE created_at>=$1", start) or 0
        signups = await pool.fetchval("SELECT count(*) FROM users WHERE role='student' AND created_at>=$1", start) or 0
        hours = await pool.fetchval("SELECT COALESCE(SUM(hours),0) FROM certificates WHERE generated_at>=$1", start) or 0
        cols = await pool.fetch("SELECT college, count(*) as signups FROM users WHERE role='student' AND created_at>=$1 GROUP BY college ORDER BY signups DESC", start)
    else:
        activities = await pool.fetchval("SELECT count(*) FROM activities") or 0
        signups = await pool.fetchval("SELECT count(*) FROM users WHERE role='student'") or 0
        hours = await pool.fetchval("SELECT COALESCE(SUM(hours),0) FROM certificates") or 0
        cols = await pool.fetch("SELECT college, count(*) as signups FROM users WHERE role='student' GROUP BY college ORDER BY signups DESC")
    colleges = [{"college": r["college"], "signups": r["signups"]} for r in cols if r["college"]]
    return {"activities": activities, "signups": signups, "hours": float(hours), "colleges": colleges}

@app.get("/api/college/stats")
async def college_stats(user: dict = Depends(get_current_user)):
    if user["role"] not in ("college_admin","school_admin"): raise HTTPException(403)
    pool = await database.get_pool()
    college = user.get("college","")
    rows = await pool.fetch("SELECT role, count(*) as cnt FROM users WHERE college=$1 GROUP BY role ORDER BY cnt DESC", college)
    return [dict(r) for r in rows]

@app.get("/api/college/students")
async def college_students(user: dict = require_role("teacher", "college_admin", "school_admin")):
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT id,name,student_id,class,college,role FROM users WHERE college=$1 ORDER BY role,id", user.get("college",""))
    return [dict(r) for r in rows]

@app.get("/api/my-stats")
async def my_stats(user: dict = Depends(get_current_user)):
    pool = await database.get_pool()
    total_hours = await pool.fetchval(
        "SELECT COALESCE(SUM(c.hours),0) FROM certificates c WHERE c.user_id=$1", user["id"]
    )
    total_acts = await pool.fetchval("SELECT count(*) FROM signups WHERE user_id=$1", user["id"])
    selected = await pool.fetchval(
        "SELECT count(*) FROM signups WHERE user_id=$1 AND status IN ('selected','checked_in')", user["id"]
    )
    cm_hours = 0
    if user.get("is_poor"):
        try:
            cm_hours = await pool.fetchval("SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id=$1", user["id"]) or 0
        except Exception:
            cm_hours = 0
    return {
        "volunteer": float(total_hours) or 0,
        "volunteer_convertible": 0,
        "community": cm_hours,
        "total_hours": float(total_hours) or 0,
        "total_signups": total_acts or 0,
        "total_selected": selected or 0,
        "select_rate": f"{(selected/total_acts*100):.1f}%" if total_acts > 0 else "0%"
    }

@app.get("/api/statistics")
async def global_stats(user: dict = require_role("teacher", "college_admin", "school_admin")):
    """管理员数据看板"""
    pool = await database.get_pool()
    total_users = await pool.fetchval("SELECT count(*) FROM users")
    total_acts = await pool.fetchval("SELECT count(*) FROM activities")
    total_hours = await pool.fetchval("SELECT COALESCE(SUM(hours),0) FROM certificates")
    published = await pool.fetchval("SELECT count(*) FROM activities WHERE status='published'")
    ended = await pool.fetchval("SELECT count(*) FROM activities WHERE status='ended'")
    draft = await pool.fetchval("SELECT count(*) FROM activities WHERE status='draft'")
    return {
        "total_users": total_users, "total_activities": total_acts,
        "total_hours": float(total_hours),
        "published": published, "ended": ended, "draft": draft
    }


# ====== Colleges & Stats & Config ======

@app.get("/api/colleges")
async def get_colleges():
    cached = await cache_get("colleges")
    if cached: return cached
    result = await database.list_colleges()
    await cache_set("colleges", result, CACHE_TTL["colleges"])
    return result

@app.get("/api/config/codes")
async def get_codes(user: dict = require_role("school_admin")):
    cfg = load_config()
    return {"teacher_code": cfg.get("teacher_code", "tzxy2026"),
            "student_code": cfg.get("student_code", cfg.get("teacher_code", "tzxy2026"))}

@app.post("/api/config/codes")
async def update_codes(req: ConfigCodesUpdate, user: dict = require_role("superadmin")):
    cfg = load_config()
    if req.teacher_code: cfg["teacher_code"] = req.teacher_code
    if req.student_code: cfg["student_code"] = req.student_code
    save_config(cfg)
    return {"ok": True}


# ====== Static HTML pages ======

@app.get("/admin.html")
async def serve_admin():
    from fastapi.responses import FileResponse
    return FileResponse(str(BASE_DIR / "static" / "admin.html"))

@app.get("/privacy.html")
async def serve_privacy():
    from fastapi.responses import FileResponse
    return FileResponse(str(BASE_DIR / "static" / "privacy.html"))

@app.get("/terms.html")
async def serve_terms():
    from fastapi.responses import FileResponse
    return FileResponse(str(BASE_DIR / "static" / "terms.html"))


# ====== Code & Audit Management ======

@app.get("/api/codes")
async def list_all_codes(user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"):
        raise HTTPException(403,"权限不足")
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT * FROM publish_codes ORDER BY created_at DESC")
    return [dict(r) for r in rows]

@app.post("/api/codes/generate")
async def generate_code(req: dict, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"):
        raise HTTPException(403,"权限不足")
    import secrets
    pool = await database.get_pool()
    code = "PUB-" + secrets.token_hex(4).upper()[:6]
    await pool.execute("INSERT INTO publish_codes(code,created_by,duration_days,max_uses,college) VALUES($1,$2,$3,$4,$5)",
        code, user["id"], req.get("duration_days",30), req.get("max_uses",10), req.get("college",""))
    return {"code": code, "ok": True}

@app.post("/api/codes/{code_id}/revoke")
async def revoke_code(code_id: int, req: dict, user: dict = Depends(get_current_user)):
    if user["role"] not in ("teacher","college_admin","school_admin"):
        raise HTTPException(403,"权限不足")
    pool = await database.get_pool()
    await pool.execute("UPDATE publish_codes SET revoked=true WHERE id=$1", code_id)
    return {"ok": True}

@app.get("/api/audit-logs")
async def get_audit_logs(user: dict = Depends(get_current_user)):
    if user["role"] not in ("college_admin","school_admin"):
        raise HTTPException(403,"权限不足")
    pool = await database.get_pool()
    rows = await pool.fetch("SELECT * FROM role_changes ORDER BY created_at DESC LIMIT 200")
    logs = []
    for r in rows:
        op = await pool.fetchrow("SELECT name FROM users WHERE id=$1", r["changed_by"])
        target = await pool.fetchrow("SELECT name FROM users WHERE id=$1", r["user_id"])
        logs.append({"id":r["id"],"action":f'{r.get("old_role","")} -> {r.get("new_role","")}',"operator_name":op["name"] if op else "","detail":f'{target["name"] if target else ""} {r.get("reason","")}',"created_at":str(r["created_at"])})
    return logs


# ====== Crash Report Viewer ======

CRASH_DIR = Path("/app/crashes")
CRASH_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/api/crash-report")
async def receive_crash(req: Request, user: dict = Depends(get_current_user)):
    """Receive crash reports from Flutter SentryReporter."""
    try:
        body = await req.json()
        crash_id = f"crash_{datetime.now():%Y%m%d_%H%M%S_%f}"
        body["_id"] = crash_id
        body["_received_at"] = datetime.now().isoformat()
        (CRASH_DIR / f"{crash_id}.json").write_text(
            json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"ok": True, "id": crash_id}
    except Exception as e:
        error_logger.error("crash save failed: %s", e)
        return {"ok": False}

@app.get("/api/crashes")
async def list_crashes(user: dict = require_role("college_admin", "school_admin")):
    """Return crash list as JSON."""
    if not CRASH_DIR.is_dir():
        return []
    crashes = []
    for f in sorted(CRASH_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix == ".json":
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                crashes.append(data)
            except Exception:
                crashes.append({"file": f.name, "error": "parse failed"})
    return crashes

@app.get("/api/crash-report/")
async def crash_report_page(request: Request):
    """Render crash reports as HTML page."""
    import html as _html
    if not CRASH_DIR.is_dir():
        CRASH_DIR.mkdir(parents=True, exist_ok=True)
    crashes = []
    for f in sorted(CRASH_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix == ".json":
            try:
                crashes.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                crashes.append({"file": f.name, "error": "parse failed"})

    rows = ""
    for c in crashes:
        err = _html.escape(str(c.get("error", "N/A"))[:120])
        typ = _html.escape(str(c.get("type", "")))
        ts = _html.escape(str(c.get("timestamp") or c.get("_received_at", "")))
        plat = _html.escape(str(c.get("platform", "")))
        ver = _html.escape(str(c.get("version", "")))
        cid = _html.escape(str(c.get("_id", c.get("file", ""))))
        stack = _html.escape(str(c.get("stack", ""))[:300])
        rows += f"""<tr>
<td><small>{cid}</small></td>
<td>{ts}</td>
<td><span class="badge">{typ}</span></td>
<td>{plat}</td>
<td>{ver}</td>
<td><code>{err}</code></td>
<td><details><summary>堆栈</summary><pre>{stack}</pre></details></td>
</tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>崩溃报告 - 校园即时通</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #333; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }}
th {{ background: #7C3AED; color: #fff; }}
tr:hover {{ background: #f0ecff; }}
pre {{ max-height: 200px; overflow: auto; font-size: 11px; background: #f8f8f8; padding: 8px; border-radius: 4px; }}
details {{ cursor: pointer; }}
.badge {{ display: inline-block; padding: 2px 6px; border-radius: 3px; background: #e0d4f7; color: #5b21b6; font-size: 11px; }}
code {{ word-break: break-all; color: #c0392b; }}
.meta {{ color: #888; font-size: 12px; margin-top: 10px; }}
</style></head>
<body>
<h1>💥 崩溃报告</h1>
<p class="meta">共 {len(crashes)} 条崩溃 · <a href="?">刷新</a></p>
<table><thead><tr>
<th>ID</th><th>时间</th><th>类型</th><th>平台</th><th>版本</th><th>错误</th><th>堆栈</th>
</tr></thead><tbody>{rows}</tbody></table>
</body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


# ====== Missing Endpoints (Flutter v2.1 compatibility) ======

@app.post("/api/activities/{activity_id}/close-signup")
@limiter.limit("30/hour")
async def close_signup(activity_id: int, request: Request, user: dict = Depends(get_current_user)):
    """关闭活动报名入口"""
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if user["role"] not in ("teacher", "college_admin", "school_admin") and act["created_by"] != user["id"]:
        raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    await pool.execute("UPDATE activities SET signup_mode='closed' WHERE id=$1", activity_id)
    audit_logger.info(f"AUDIT: close_signup activity={activity_id} by={user['id']}")
    return {"ok": True}

@app.post("/api/activities/{activity_id}/modify")
@limiter.limit("30/hour")
async def modify_activity(activity_id: int, req: ActivityModify, request: Request,
                          user: dict = Depends(get_current_user)):
    """修改活动字段（管理员用）"""
    if user["role"] not in ("college_admin", "school_admin"):
        raise HTTPException(403, "仅管理员可修改活动")
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    pool = await database.get_pool()
    ALLOWED = {"title","description","status","scope_type","scope_value",
               "max_participants","deadline","activity_date","location",
               "checkin_enabled","start_time","end_time","signup_mode",
               "hours","participant_hours","staff_hours"}
    updates = {k: v for k, v in req.model_dump().items() if v is not None and k in ALLOWED}
    if not updates:
        raise HTTPException(400, "没有需要修改的字段")
    set_clause = ", ".join(f"{k}=${i+1}" for i, k in enumerate(updates.keys()))
    values = list(updates.values()) + [activity_id]
    await pool.execute(f"UPDATE activities SET {set_clause} WHERE id=${len(values)}", *values)
    audit_logger.info(f"AUDIT: modify_activity activity={activity_id} fields={list(updates.keys())} by={user['id']}")
    return {"ok": True}

@app.post("/api/activities/{activity_id}/manual-add")
@limiter.limit("30/hour")
async def manual_add_signup(activity_id: int, req: ManualAddRequest, request: Request,
                            user: dict = Depends(get_current_user)):
    """手动添加学生到活动"""
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if user["role"] not in ("teacher", "college_admin", "school_admin") and act["created_by"] != user["id"]:
        raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    target = await pool.fetchrow("SELECT id, name FROM users WHERE student_id=$1", req.student_id)
    if not target:
        raise HTTPException(404, f"学生 {req.student_id} 不存在")
    exist = await pool.fetchrow("SELECT id FROM signups WHERE activity_id=$1 AND user_id=$2", activity_id, target["id"])
    if exist:
        raise HTTPException(400, "该学生已在活动中")
    await pool.execute("INSERT INTO signups(activity_id,user_id,status) VALUES($1,$2,'checked_in')",
                       activity_id, target["id"])
    await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_new','你被手动加入活动',$2)",
                       target["id"], f"[aid:{activity_id}]你被{user['name']}加入「{act['title']}」")
    audit_logger.info(f"AUDIT: manual_add_signup activity={activity_id} student={req.student_id} by={user['id']}")
    return {"ok": True, "name": target["name"]}

@app.post("/api/activities/{activity_id}/notify-all")
@limiter.limit("10/hour")
async def notify_all_signups(activity_id: int, req: NotifyAllRequest, request: Request,
                             user: dict = Depends(get_current_user)):
    """通知该活动所有已报名学生"""
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if user["role"] not in ("teacher", "college_admin", "school_admin") and act["created_by"] != user["id"]:
        raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    signups = await pool.fetch("SELECT DISTINCT user_id FROM signups WHERE activity_id=$1", activity_id)
    msg = req.message
    count = 0
    for s in signups:
        await pool.execute("INSERT INTO notifications(user_id,type,title,content) VALUES($1,'activity_msg','活动消息',$2)",
                           s["user_id"], f"[aid:{activity_id}]{msg}")
        count += 1
    audit_logger.info(f"AUDIT: notify_all_signups activity={activity_id} count={count} by={user['id']}")
    return {"ok": True, "count": count}

@app.post("/api/activities/{activity_id}/assist-members/{user_id}/remove")
@limiter.limit("30/hour")
async def remove_assist_member(activity_id: int, user_id: int, request: Request,
                               user: dict = Depends(get_current_user)):
    """移除活动协助者"""
    act = await database.get_activity(activity_id)
    if not act: raise HTTPException(404, "活动不存在")
    if user["role"] not in ("teacher", "college_admin", "school_admin") and act["created_by"] != user["id"]:
        raise HTTPException(403, "无权操作此活动")
    pool = await database.get_pool()
    await pool.execute("DELETE FROM assist_members WHERE activity_id=$1 AND user_id=$2", activity_id, user_id)
    audit_logger.info(f"AUDIT: remove_assist_member activity={activity_id} target_user={user_id} by={user['id']}")
    return {"ok": True}

@app.post("/api/info-change")
@limiter.limit("10/hour")
async def request_info_change(req: InfoChangeRequest, request: Request, user: dict = Depends(get_current_user)):
    """提交信息修改申请（供管理员审核）"""
    pool = await database.get_pool()
    admins = await pool.fetch("SELECT id FROM users WHERE role IN ('college_admin','school_admin') LIMIT 5")
    content = f"用户 {user['name']}({user.get('student_id','')}) 请求修改 {req.field}: {req.new_value}\n理由: {req.reason}"
    sent_to = 0
    for a in admins:
        await database.create_notification(a["id"], "info_change", "信息修改申请", content)
        sent_to += 1
    audit_logger.info(f"AUDIT: info_change_request user={user['id']} field={req.field} by={user['id']}")
    return {"ok": True, "sent_to": sent_to}

@app.get("/api/activities/pending-approvals")
async def list_pending_approvals(user: dict = Depends(get_current_user)):
    """获取待审批的活动列表"""
    if user["role"] not in ("teacher", "college_admin", "school_admin"):
        raise HTTPException(403, "权限不足")
    pool = await database.get_pool()
    rows = await pool.fetch(
        "SELECT a.*, u.name as creator_name FROM activities a JOIN users u ON a.created_by=u.id WHERE a.status IN ('pending_approval','draft') ORDER BY a.updated_at DESC LIMIT 100"
    )
    return [dict(r) for r in rows]


# ====== Serve SPA frontend ======

@app.get("/")
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str = ""):
    """Serve the PWA frontend for any non-API route."""
    index_path = BASE_DIR / "static" / "index.html"
    if index_path.exists():
        from fastapi.responses import FileResponse
        resp = FileResponse(str(index_path))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return {"message": "校园即时通 API v3.0", "docs": "/docs"}


# ====== Push Notification Device Registry ======
_push_tokens: set[str] = set()

@app.post("/api/push/register")
@limiter.limit("5/minute")
async def register_push_device(request: Request, req: dict = Body(...), user: dict = Depends(get_current_user)):
    """Register a HarmonyOS device token for push notifications."""
    token = req.get("token", "").strip()
    if token:
        _push_tokens.add(token)
        return {"ok": True, "devices": len(_push_tokens)}
    return {"ok": False, "detail": "缺少设备令牌"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("DEV_PORT","3001")), limit_max_request_size=10*1024*1024)
