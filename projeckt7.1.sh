#!/bin/bash
# Script-Version: 7.1

# Aktualisierung von app/routers/admin.py mit dem Fix fuer Tab-Sortierung
cat << 'EOF' > app/routers/admin.py
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse, FileResponse
import sqlite3
import os
import shutil
import zipfile
import json
import urllib.parse
from datetime import datetime
from app.db import get_db

router = APIRouter()

@router.get("/backup/full")
def full_backup(request: Request):
    if not request.session.get("authenticated"): return RedirectResponse(url="/login")
    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    backup_path = f"/tmp/{backup_filename}"
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists("data/catalog.db"): zipf.write("data/catalog.db", "catalog.db")
        if os.path.exists("data/icons"):
            for root, dirs, files in os.walk("data/icons"):
                for file in files: zipf.write(os.path.join(root, file), os.path.join("icons", file))
    return FileResponse(backup_path, media_type="application/zip", filename=backup_filename)

@router.post("/backup/restore_full")
async def restore_full(request: Request, backup_file: UploadFile = File(...)):
    if not request.session.get("authenticated"): return RedirectResponse(url="/login")
    temp_zip = f"/tmp/uploaded_{backup_file.filename}"
    with open(temp_zip, "wb") as buffer: shutil.copyfileobj(backup_file.file, buffer)
    with zipfile.ZipFile(temp_zip, 'r') as zipf: zipf.extractall("/tmp/restore_extract")
    if os.path.exists("/tmp/restore_extract/catalog.db"): shutil.copy("/tmp/restore_extract/catalog.db", "data/catalog.db")
    if os.path.exists("/tmp/restore_extract/icons"): shutil.copytree("/tmp/restore_extract/icons", "data/icons", dirs_exist_ok=True)
    return RedirectResponse(url="/", status_code=303)

@router.get("/backup/category/{category_name}")
def backup_category(request: Request, category_name: str, db: sqlite3.Connection = Depends(get_db)):
    if not request.session.get("authenticated"): return RedirectResponse(url="/login")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM items WHERE category = ?", (category_name,))
    items = [dict(row) for row in cursor.fetchall()]
    file_path = f"/tmp/backup_{category_name}.json"
    with open(file_path, "w", encoding="utf-8") as f: json.dump(items, f, ensure_ascii=False, indent=4)
    return FileResponse(file_path, media_type="application/json", filename=f"backup_tab_{category_name}.json")

@router.post("/tab/move")
def move_tab(request: Request, category: str = Form(...), direction: str = Form(...), db: sqlite3.Connection = Depends(get_db)):
    if not request.session.get("authenticated"): return RedirectResponse(url="/login")
    cursor = db.cursor()

    cursor.execute("SELECT DISTINCT category FROM items WHERE category != ''")
    existing_cats = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT category, sort_index FROM tab_order ORDER BY sort_index ASC")
    order_map = {r[0]: r[1] for r in cursor.fetchall()}

    ordered_cats = sorted(existing_cats, key=lambda c: order_map.get(c, 9999))

    if category in ordered_cats:
        idx = ordered_cats.index(category)
        if direction == "left" and idx > 0:
            ordered_cats[idx], ordered_cats[idx-1] = ordered_cats[idx-1], ordered_cats[idx]
        elif direction == "right" and idx < len(ordered_cats) - 1:
            ordered_cats[idx], ordered_cats[idx+1] = ordered_cats[idx+1], ordered_cats[idx]

    cursor.execute("DELETE FROM tab_order")
    for i, cat in enumerate(ordered_cats):
        cursor.execute("INSERT INTO tab_order (category, sort_index) VALUES (?, ?)", (cat, i * 10))

    db.commit()
    return RedirectResponse(url=f"/?active_tab={urllib.parse.quote(category)}", status_code=303)
EOF

# Aktualisierung von app/main.py zur Behebung der Middleware-Reihenfolge
cat << 'EOF' > app/main.py
# Version: 7.1
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import json
import sqlite3
from app.db import get_db, init_db
from app.routers import auth, categories, items, admin

with open("app/locales/uk.json", encoding="utf-8") as f: uk_loc = json.load(f)
with open("app/locales/en.json", encoding="utf-8") as f: en_loc = json.load(f)
LOCALES = {"uk": uk_loc, "en": en_loc}

app = FastAPI()

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

init_db()

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

    return templates.TemplateResponse("index.html", {
        "request": request,
        "t": request.state.t,
        "lang": request.state.lang,
        "categorized_items": sorted_categorized,
        "all_metrics": sorted(list(all_metrics)),
        "active_tab": active_tab
    })
EOF

# Container neu starten
docker compose restart > /dev/null 2>&1
