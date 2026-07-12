from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
import sqlite3
import json
from app.db import get_db
from app.auth_manager import require_role, get_password_hash
from app.templates_config import render, get_categories

router = APIRouter(prefix="/admin/users", dependencies=[Depends(require_role(["admin"]))])

def _users(cursor) -> list[dict]:
    cursor.execute("SELECT id, username, role, permissions, default_lang FROM users ORDER BY id")
    return [dict(r) for r in cursor.fetchall()]

@router.get("")
def users_page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    return render(request, "admin_users.html", {
        "users":      _users(c),
        "categories": get_categories(c),
    })

@router.post("/create")
async def create_user(request: Request, db: sqlite3.Connection = Depends(get_db)):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    role     = form.get("role", "viewer")
    lang     = form.get("default_lang", "uk")
    perms    = json.loads(form.get("permissions_json", "{}"))

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    try:
        db.cursor().execute(
            "INSERT INTO users (username, password_hash, role, permissions, default_lang) VALUES (?,?,?,?,?)",
            (username, get_password_hash(password), role, json.dumps(perms), lang)
        )
        db.commit()
    except Exception:
        pass  # дубль username — ігноруємо
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/update/{user_id}")
async def update_user(request: Request, user_id: int, db: sqlite3.Connection = Depends(get_db)):
    form         = await request.form()
    role         = form.get("role", "viewer")
    lang         = form.get("default_lang", "uk")
    new_password = form.get("new_password", "")
    perms        = json.loads(form.get("permissions_json", "{}"))

    c = db.cursor()
    if new_password.strip():
        c.execute(
            "UPDATE users SET role=?,permissions=?,default_lang=?,password_hash=? WHERE id=?",
            (role, json.dumps(perms), lang, get_password_hash(new_password), user_id)
        )
    else:
        c.execute(
            "UPDATE users SET role=?,permissions=?,default_lang=? WHERE id=?",
            (role, json.dumps(perms), lang, user_id)
        )
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/delete/{user_id}")
def delete_user(request: Request, user_id: int, db: sqlite3.Connection = Depends(get_db)):
    if request.session.get("user_id") == user_id:
        return RedirectResponse(url="/admin/users", status_code=303)
    db.cursor().execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)
