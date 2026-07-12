import bcrypt
import sqlite3
import json
from cachetools import TTLCache
from fastapi import Request, HTTPException

# Обмеження спроб входу: макс. 1000 IP-адрес у пам'яті, очищення через 5 хвилин
_login_attempts = TTLCache(maxsize=1000, ttl=300)

def check_rate_limit(ip: str) -> bool:
    attempts = _login_attempts.get(ip, 0)
    if attempts >= 5:
        return False
    _login_attempts[ip] = attempts + 1
    return True

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def get_current_user(request: Request, db: sqlite3.Connection) -> dict | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    return dict(row) if row else None

def require_role(allowed_roles: list):
    def checker(request: Request):
        role = request.session.get("role")
        if not role or role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access Denied")
        return True
    return checker

def get_tab_role(request: Request, db: sqlite3.Connection, category: str) -> str:
    """Повертає 'editor'|'viewer'|'' для поточного користувача та вкладки."""
    role = request.session.get("role")
    if role == "admin":
        return "editor"
    if role == "editor":
        user_id = request.session.get("user_id")
        c = db.cursor()
        c.execute("SELECT permissions FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        perms = json.loads(row[0]) if row and row[0] else {}
        return perms.get(category, "")
    return ""
