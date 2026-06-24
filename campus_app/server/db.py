"""校园即时通 - 数据库模块"""
import asyncio
import asyncpg
import os
import secrets
import json as json_module
from typing import Optional
from datetime import datetime, timedelta

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "campus_admin"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "campus_app"),
}

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """获取数据库连接池（单例）"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            **DB_CONFIG,
            min_size=2,
            max_size=20,
            command_timeout=30,
        )
    return _pool


async def close_pool():
    """关闭连接池"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ====== 用户 ======

async def create_user(student_id: str, name: str, password_hash: str,
                      class_name: str = "", college: str = "",
                      role: str = "student", qq: str = "", phone: str = "",
                      gender: str = "") -> Optional[int]:
    """创建用户。重复学号返回None。"""
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO users (student_id, name, class, college, password_hash, role, qq, phone, gender)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (student_id) DO NOTHING
        RETURNING id
    """, student_id, name, class_name, college, password_hash, role, qq, phone, gender)


async def get_user(student_id: str) -> Optional[dict]:
    """查询用户（不含密码哈希）。"""
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, student_id, name, class, college, role, publisher_org_id, created_at
           FROM users WHERE student_id=$1""", student_id
    )
    return dict(row) if row else None

async def get_user_with_password(student_id: str) -> Optional[dict]:
    """查询用户（含密码哈希，仅登录用）。"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, student_id, name, password_hash, role, can_publish, publish_expires_at, college, class, class_name, gender, phone, is_poor FROM users WHERE student_id=$1", student_id
    )
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, student_id, name, class, college, role, is_poor, can_publish, show_phone, show_qq, qq, phone, gender, publisher_org_id, created_at, is_active,
                  COALESCE(token_version, 0) as token_version
           FROM users WHERE id=$1""", user_id
    )
    return dict(row) if row else None


async def activate_publisher(user_id: int, org_id: int, code: str):
    """用发布码激活发布者身份"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET role='publisher', publisher_org_id=$1 WHERE id=$2",
                org_id, user_id
            )
            await conn.execute(
                "INSERT INTO publish_code_logs (code, organization_id, activated_by) VALUES ($1,$2,$3)",
                code, org_id, user_id
            )


# ====== 组织 ======

async def create_organization(name: str, org_type: str, code: str, created_by: int) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO organizations (name, type, publish_code, created_by)
        VALUES ($1, $2, $3, $4) RETURNING id
    """, name, org_type, code, created_by)


async def get_org_by_code(code: str) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, code, created_by FROM organizations WHERE publish_code=$1 AND publish_code_active=TRUE", code
    )
    return dict(row) if row else None


async def revoke_publish_code(code: str):
    pool = await get_pool()
    await pool.execute(
        "UPDATE organizations SET publish_code_active=FALSE WHERE publish_code=$1", code
    )


# ====== 活动 ======

async def create_activity(data: dict) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO activities (title, description, category, reward_type, scope_type, scope_value,
            max_participants, deadline, organization_id, created_by, status,
            staff_hours, participant_hours, hours, creator_override, signup_start, activity_date, location,
            auto_publish_at, signup_mode, checkin_enabled,
            contact_qq, contact_phone, qq_group, pu_type, pu_qq, checkin_type, image_urls, gender_limit, cancel_policy, cancel_deadline_lock)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31)
        RETURNING id
    """, data["title"], data.get("description", ""),
        data.get("reward_type", data.get("category", "volunteer")),
        data.get("reward_type", data.get("category", "volunteer")),
        data.get("scope_type", "all"), data.get("scope_value"),
        data.get("max_participants", 0), data.get("deadline"),
        data.get("organization_id"), data["created_by"],
        data.get("status", "published"),
        data.get("staff_hours") or data.get("hours", 0), data.get("participant_hours") or data.get("hours", 0), data.get("hours", 0),
        data.get("creator_override", ""),
        data.get("signup_start", ""), data.get("activity_date", ""), data.get("location", ""),
        data.get("auto_publish_at", ""), data.get("signup_mode", "lottery"),
        data.get("checkin_enabled", False),
        data.get("contact_qq", ""), data.get("contact_phone", ""), data.get("qq_group", ""),
        data.get("pu_type", ""), data.get("pu_qq", ""), data.get("checkin_type", ""),
        data.get("image_urls", ""), data.get("gender_limit", ""), data.get("cancel_policy", "free"), data.get("cancel_deadline_lock", False))


async def list_activities(limit: int = 100, offset: int = 0,
                          user_college: str = "", user_role: str = "student",
                          user_id: int = 0) -> list:
    """列出用户可见的活动。学生只能看全校+自己学院的+内部参与的活动。"""
    pool = await get_pool()
    # Common computed columns
    extra = """
        COALESCE(a.hours, a.staff_hours, a.participant_hours, 0) as hours,
        (SELECT COUNT(*) FROM signups WHERE activity_id=a.id) as signup_count
    """
    base_query = f"""
        SELECT a.*, o.name as org_name, u.name as creator_name, {extra}
        FROM activities a
        LEFT JOIN organizations o ON a.organization_id = o.id
        LEFT JOIN users u ON a.created_by = u.id
    """
    if user_role == "school_admin":
        # school_admin sees all activities (no college filter)
        query = base_query + "WHERE a.status != 'draft' ORDER BY a.created_at DESC LIMIT $1 OFFSET $2"
        rows = await pool.fetch(query, limit, offset)
    elif user_role in ("teacher", "college_admin", "school_teacher"):
        # college_admin/teacher: only see own college's activities + all-scope
        query = base_query + """
            WHERE a.status != 'draft'
              AND (a.college = $3 OR a.scope_type = 'all')
            ORDER BY a.created_at DESC LIMIT $1 OFFSET $2
        """
        rows = await pool.fetch(query, limit, offset, user_college)
    else:
        # student: see all-scope + own college's activities (via scope_value or college field)
        query = f"""
            SELECT DISTINCT a.*, o.name as org_name, u.name as creator_name, {extra}
            FROM activities a
            LEFT JOIN organizations o ON a.organization_id = o.id
            LEFT JOIN users u ON a.created_by = u.id
            LEFT JOIN signups s ON a.id = s.activity_id AND s.user_id = $3
            WHERE a.status != 'draft'
            AND (
                a.scope_type = 'all'
                OR (a.scope_type = 'college' AND (a.scope_value = $4 OR a.college = $4))
                OR (a.scope_type = 'internal' AND s.id IS NOT NULL)
            )
            ORDER BY a.created_at DESC LIMIT $1 OFFSET $2
        """
        rows = await pool.fetch(query, limit, offset, user_id, user_college)
    return [dict(r) for r in rows]


async def get_activity(activity_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow("""
        SELECT a.*, o.name as org_name, u.name as creator_name,
            COALESCE(a.hours, a.staff_hours, a.participant_hours, 0) as hours,
            (SELECT COUNT(*) FROM signups WHERE activity_id=a.id) as signup_count
        FROM activities a
        LEFT JOIN organizations o ON a.organization_id = o.id
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.id=$1
    """, activity_id)
    return dict(row) if row else None


async def draw_lottery(activity_id: int, max_select: int) -> int:
    """抽签：在报名者中随机选取"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 随机选中
            await conn.execute("""
                WITH picked AS (
                    SELECT id FROM signups
                    WHERE activity_id=$1 AND role='participant' AND status='pending'
                    ORDER BY random() LIMIT $2
                    FOR UPDATE
                )
                UPDATE signups SET status='selected'
                FROM picked
                WHERE signups.id = picked.id
            """, activity_id, max_select)
            # 其余标记为waitlist
            await conn.execute("""
                UPDATE signups SET status='waitlist'
                WHERE activity_id=$1 AND role='participant' AND status='pending'
            """, activity_id)
            # 更新活动状态
            await conn.execute(
                "UPDATE activities SET status='ended' WHERE id=$1", activity_id
            )
            await conn.execute(
                "UPDATE activities SET lottery_drawn_at=NOW() WHERE id=$1", activity_id
            )
            # 通知所有中签者
            selected_users = await conn.fetch(
                "SELECT user_id FROM signups WHERE activity_id=$1 AND status='selected'",
                activity_id
            )
            act_title = await conn.fetchval("SELECT title FROM activities WHERE id=$1", activity_id)
            for su in selected_users:
                await conn.execute(
                    "INSERT INTO notifications (user_id, type, title, content) VALUES ($1,'lottery','中签通知',$2)",
                    su["user_id"], f"恭喜！你已中签活动「{act_title}」"
                )
            # 通知未中签者
            waitlisted_users = await conn.fetch(
                "SELECT user_id FROM signups WHERE activity_id=$1 AND status='waitlist'", activity_id
            )
            for wu in waitlisted_users:
                await conn.execute(
                    "INSERT INTO notifications (user_id, type, title, content) VALUES ($1,'lottery','抽签结果', $2)",
                    wu["user_id"], f"很遗憾，你未中签活动「{act_title}」，已进入候补队列"
                )
            return len(selected_users)


# ====== 报名 ======

async def signup_activity(activity_id: int, user_id: int, role: str = "participant") -> Optional[str]:
    """报名活动。返回'ok'=成功, 'duplicate'=重复, 'closed'=关闭, 'full'=已满。"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            act = await conn.fetchrow(
                """SELECT status, signup_mode, max_participants, deadline,
                   (SELECT count(*) FROM signups WHERE activity_id=$1 AND role='participant') as signup_count
                   FROM activities WHERE id=$1 FOR UPDATE""", activity_id
            )
            if not act: return None
            if act["status"] != "published": return "closed"
            dl = act.get("deadline")
            if dl and dl.strip():
                try:
                    if datetime.strptime((dl+':00')[:19], "%Y-%m-%d %H:%M:%S") < datetime.now():
                        return "closed"
                except Exception:
                    import logging
                    logging.getLogger("campus").warning("Invalid deadline format: %s", dl)
            mode = act.get("signup_mode", "lottery")
            # Check max participants for 报名制
            # Re-count after FOR UPDATE lock — the subquery's snapshot is stale
            # in READ COMMITTED. A fresh statement gets the latest committed count.
            if mode == "first_come" and act["max_participants"] > 0:
                fresh_count = await conn.fetchval(
                    "SELECT count(*) FROM signups WHERE activity_id=$1 AND role='participant'", activity_id
                )
                if fresh_count >= act["max_participants"]:
                    return "full"
            # 报名制→直接通过, 其他→pending
            initial_status = "selected" if mode == "first_come" else "pending"
            try:
                await conn.execute(
                    "INSERT INTO signups (activity_id, user_id, role, status) VALUES ($1,$2,$3,$4)",
                    activity_id, user_id, role, initial_status
                )
                return "ok"
            except asyncpg.UniqueViolationError:
                return "duplicate"

async def approve_signup(activity_id: int, user_id: int) -> bool:
    """评审制：管理员通过报名申请"""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE signups SET status='selected' WHERE activity_id=$1 AND user_id=$2 AND status='pending'",
        activity_id, user_id
    )
    return result != "UPDATE 0"

async def reject_signup(activity_id: int, user_id: int) -> bool:
    """评审制：管理员拒绝报名申请"""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE signups SET status='waitlist' WHERE activity_id=$1 AND user_id=$2 AND status='pending'",
        activity_id, user_id
    )
    return result != "UPDATE 0"


async def get_signups(activity_id: int) -> list:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT s.*, u.name, u.student_id, u.class, u.college
        FROM signups s JOIN users u ON s.user_id = u.id
        WHERE s.activity_id=$1 ORDER BY s.signed_at
    """, activity_id)
    return [dict(r) for r in rows]


# ====== 邀请码 ======

INVITE_CODE_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 chars, no confusing ones

async def create_invite_code(activity_id: int) -> str:
    """为活动生成8位字母数字邀请码（68亿组合，防暴力破解）。"""
    code = ''.join(secrets.choice(INVITE_CODE_CHARS) for _ in range(8))
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO staff_invites (activity_id, invite_code, expires_at) VALUES ($1,$2,$3)",
        activity_id, code, datetime.now() + timedelta(hours=72)
    )
    return code


async def use_invite_code(code: str, user_id: int) -> Optional[int]:
    """使用邀请码加入活动（原子操作，防竞态）。返回activity_id或None。"""
    pool = await get_pool()
    return await pool.fetchval("""
        UPDATE staff_invites SET used_by = $2, used_at = NOW()
        WHERE invite_code = $1
          AND used_by IS NULL
          AND (expires_at IS NULL OR expires_at > NOW())
        RETURNING activity_id
    """, code, user_id)


# ====== 通知 ======

async def create_notification(user_id: int, notif_type: str, title: str, content: str, created_by: int = None):
    pool = await get_pool()
    # 频率限制：同类型通知1分钟内不超过3条，总计不超过10条
    recent_same = await pool.fetchval(
        "SELECT count(*) FROM notifications WHERE user_id=$1 AND type=$2 AND created_at > NOW() - INTERVAL '1 minute'",
        user_id, notif_type
    )
    if recent_same >= 3:
        return  # 跳过，防止同类型刷屏
    recent_all = await pool.fetchval(
        "SELECT count(*) FROM notifications WHERE user_id=$1 AND created_at > NOW() - INTERVAL '1 minute'",
        user_id
    )
    if recent_all >= 10:
        return  # 跳过，防止刷屏
    await pool.execute(
        "INSERT INTO notifications (user_id, type, title, content, created_by) VALUES ($1,$2,$3,$4,$5)",
        user_id, notif_type, title, content, created_by
    )


async def get_notifications(user_id: int, limit: int = 50) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, user_id, type, title, content, is_read, activity_id, notice_id, created_at FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
        user_id, limit
    )
    return [dict(r) for r in rows]


# ====== 学院 ======

async def list_colleges() -> list:
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, name FROM colleges ORDER BY id")
    return [dict(r) for r in rows]


# ====== 证明 ======

async def create_certificate(activity_id: int, user_id: int,
                              hours: float, cert_no: str, template_data: dict = None) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO certificates (activity_id, user_id, certificate_no, hours, template_data)
        VALUES ($1,$2,$3,$4,$5) RETURNING id
    """, activity_id, user_id, cert_no, hours, json_module.dumps(template_data or {}))


async def get_certificates(user_id: int) -> list:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT c.*, a.title as activity_title
        FROM certificates c JOIN activities a ON c.activity_id = a.id
        WHERE c.user_id=$1 ORDER BY c.generated_at DESC
    """, user_id)
    return [dict(r) for r in rows]


# ====== Token ======

async def save_refresh_token(user_id: int, token_hash: str, expires_at):
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1,$2,$3)",
        user_id, token_hash, expires_at
    )


async def verify_refresh_token(token_hash: str) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM refresh_tokens WHERE token_hash=$1 AND expires_at > NOW()",
        token_hash
    )
    return dict(row) if row else None


# ====== Check-in Tokens ======

async def save_checkin_token(activity_id: int, token_hash: str, expires_at) -> bool:
    """Store a check-in token. Returns True on success."""
    pool = await get_pool()
    try:
        await pool.execute(
            "INSERT INTO checkin_tokens (activity_id, token_hash, expires_at) VALUES ($1, $2, $3)",
            activity_id, token_hash, expires_at
        )
        return True
    except Exception:
        return False


async def get_checkin_token(token_hash: str) -> Optional[dict]:
    """Retrieve a valid (non-expired) check-in token by hash."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM checkin_tokens WHERE token_hash=$1 AND expires_at > NOW()",
        token_hash
    )
    return dict(row) if row else None


async def mark_checkin_token_used(token_hash: str, user_id: int) -> None:
    """Mark a check-in token as used."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE checkin_tokens SET used_at=NOW(), used_by=$1 WHERE token_hash=$2",
        user_id, token_hash
    )
