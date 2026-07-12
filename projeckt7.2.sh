#!/bin/bash
# Script-Version: 7.2

cd catalog_app || exit

cat << 'EOF' > app/main.py
# Version: 7.2
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import json
import sqlite3
# FIX: Import von upgrade_db für Kompatibilität mit der bestehenden Datenbank
from app.db import get_db, upgrade_db
from app.routers import auth, categories, items, admin

# Übersetzungen laden
with open("app/locales/uk.json", encoding="utf-8") as f: uk_loc = json.load(f)
with open("app/locales/en.json", encoding="utf-8") as f: en_loc = json.load(f)
LOCALES = {"uk": uk_loc, "en": en_loc}

app = FastAPI()

# Middleware für I18n
class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        lang = request.session.get("lang", "uk")
        def t(key): return LOCALES.get(lang, uk_loc).get(key, key)
        request.state.t = t
        request.state.lang = lang
        response = await call_next(request)
        return response

app.add_middleware(I18nMiddleware)
app.add_middleware(SessionMiddleware, secret_key="super-secret-home-key")

app.mount("/icons", StaticFiles(directory="data/icons"), name="icons")
templates = Jinja2Templates(directory="app/templates")

# DB Update ausführen
upgrade_db()

# Module einbinden
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(items.router)
app.include_router(admin.router)

@app.get("/lang/{lang_code}")
def set_lang(request: Request, lang_code: str):
    if lang_code in LOCALES: request.session["lang"] = lang_code
    return RedirectResponse(url="/", status_code=303)

@app.get("/")
def read_root(request: Request, active_tab: str = None, db: sqlite3.Connection = Depends(get_db)):
    if not request.session.get("authenticated", False): return RedirectResponse(url="/login")

    cursor = db.cursor()
    cursor.execute("SELECT category FROM tab_order ORDER BY sort_index ASC")
    ordered_cats = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM items ORDER BY name ASC")
    all_items = cursor.fetchall()

    categorized_items = {}
    all_metrics = set()

    for item in all_items:
        dict_item = dict(item)
        dict_item['links'] = json.loads(dict_item['links']) if dict_item['links'] else []
        ratings = json.loads(dict_item['ratings']) if dict_item['ratings'] else []
        dict_item['ratings'] = ratings
        for r in ratings: all_metrics.add(r['metric'])

        dict_item['parsed_tags'] = [t.strip() for t in dict_item.get('tags', '').split(',') if t.strip()]
        cat = dict_item['category'] or 'Загальне'
        if cat not in categorized_items: categorized_items[cat] = []
        categorized_items[cat].append(dict_item)

    sorted_categorized = {k: categorized_items[k] for k in ordered_cats if k in categorized_items}
    for k in categorized_items:
        if k not in sorted_categorized: sorted_categorized[k] = categorized_items[k]

    # FIX: TemplateResponse mit expliziten Parametern (request=, name=, context=)
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={
            "request": request,
            "t": request.state.t,
            "lang": request.state.lang,
            "categorized_items": sorted_categorized,
            "all_metrics": sorted(list(all_metrics)),
            "active_tab": active_tab
        }
    )
EOF

# Container neu starten
docker compose restart web > /dev/null 2>&1
