import os
import logging
import json
import sqlite3
import secrets
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, Depends, Response
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.db import get_db, init_db
from app.auth_manager import get_current_user
from app.templates_config import render
from app.routers import auth, categories, items, admin, users

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)

with open("app/locales/uk.json", encoding="utf-8") as f: _uk = json.load(f)
with open("app/locales/en.json", encoding="utf-8") as f: _en = json.load(f)
with open("app/locales/de.json", encoding="utf-8") as f: _de = json.load(f)
LOCALES = {"uk": _uk, "en": _en, "de": _de}

log_handler = RotatingFileHandler("data/app.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log_handler, logging.StreamHandler()]
)

def apply_log_level():
    try:
        conn = sqlite3.connect("data/catalog.db")
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'log_level'")
        row = c.fetchone()
        level_str = row[0] if row else "INFO"
        conn.close()
        
        level = getattr(logging, level_str, logging.INFO)
        logging.getLogger().setLevel(level)
    except Exception:
        logging.getLogger().setLevel(logging.INFO)

init_db()
apply_log_level()

app = FastAPI(docs_url=None, redoc_url=None)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "SAMEORIGIN"
        response.headers["X-XSS-Protection"]       = "1; mode=block"
        return response

class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        lang = request.session.get("lang", "en")
        locale_dict = LOCALES.get(lang, _en)
        request.state.lang = lang       
        request.state.t = lambda key: locale_dict.get(key, key)
        response = await call_next(request)
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)

app.mount("/icons", StaticFiles(directory="data/icons"), name="icons")
app.mount("/screenshots", StaticFiles(directory="data/screenshots"), name="screenshots")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

init_db()

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(items.router)
app.include_router(admin.router)
app.include_router(users.router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    icon_path = "app/static/favicon.ico"
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    return Response(status_code=204)

@app.get("/lang/{lang_code}")
def set_lang(request: Request, lang_code: str, active_tab: str = None):
    if lang_code in LOCALES:
        request.session["lang"] = lang_code
    url = f"/?active_tab={active_tab}" if active_tab else "/"
    return RedirectResponse(url=url, status_code=303)

@app.get("/")
def read_root(
    request:    Request,
    active_tab: str = None,
    db:         sqlite3.Connection = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")

    is_admin   = user["role"] == "admin"
    user_perms = json.loads(user["permissions"]) if user["permissions"] else {}

    c = db.cursor()
    c.execute("SELECT category FROM tab_order ORDER BY sort_index")
    ordered = [r[0] for r in c.fetchall()]

    c.execute("SELECT * FROM item_screenshots")
    all_screenshots = c.fetchall()
    screenshots_by_item = {}
    for s in all_screenshots:
        screenshots_by_item.setdefault(s["item_id"], []).append(s["filename"])

    c.execute("SELECT * FROM items ORDER BY name")
    categorized = {}
    all_metrics  = set()

    for row in c.fetchall():
        d   = dict(row)
        cat = d["category"] or "Загальне"

        if not is_admin and cat not in user_perms:
            continue

        d["links"]       = json.loads(d["links"])   if d["links"]   else []
        d["ratings"]     = json.loads(d["ratings"]) if d["ratings"] else []
        d["parsed_tags"] = [t.strip() for t in d.get("tags", "").split(",") if t.strip()]
        d["screenshots"] = screenshots_by_item.get(d["id"], [])

        for r in d["ratings"]:
            all_metrics.add(r["metric"])

        categorized.setdefault(cat, []).append(d)

    sorted_cats = {k: categorized[k] for k in ordered if k in categorized}
    sorted_cats.update({k: v for k, v in categorized.items() if k not in sorted_cats})

    tab_roles = {
        cat: ("editor" if is_admin else user_perms.get(cat, "viewer"))
        for cat in sorted_cats
    }

    return render(request, "index.html", {
        "categorized_items": sorted_cats,
        "all_metrics":       sorted(all_metrics),
        "active_tab":        active_tab,
        "role":              user["role"],
        "tab_roles":         tab_roles,
    })