from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
import sqlite3
from app.db import get_db
from app.auth_manager import verify_password, check_rate_limit
from app.templates_config import render

router = APIRouter()

@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/")
    return render(request, "login.html")

@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(ip):
        return render(request, "login.html", {"error": request.state.t("login_too_many")})

    c = db.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    user = c.fetchone()

    if user and verify_password(password, user["password_hash"]):
        request.session["user_id"] = user["id"]
        request.session["role"]    = user["role"]
        request.session["lang"]    = user["default_lang"]
        return RedirectResponse(url="/", status_code=303)

    return render(request, "login.html", {"error": request.state.t("login_error")})

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
