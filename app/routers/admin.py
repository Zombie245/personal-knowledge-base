from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse, FileResponse
import sqlite3
import os
import shutil
import zipfile
import json
import urllib.parse
from datetime import datetime
from app.db import get_db, init_db
from app.auth_manager import require_role

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/backup/full", dependencies=[Depends(require_role(["admin"]))])
def full_backup():
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    path = f"/tmp/{name}"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists("data/catalog.db"):
            zf.write("data/catalog.db", "catalog.db")
        if os.path.exists("data/icons"):
            for root, _, files in os.walk("data/icons"):
                for file in files:
                    zf.write(os.path.join(root, file), os.path.join("icons", file))
    return FileResponse(path, media_type="application/zip", filename=name)

@router.post("/backup/restore_full", dependencies=[Depends(require_role(["admin"]))])
async def restore_full(backup_file: UploadFile = File(...)):
    tmp = f"/tmp/restore_{backup_file.filename}"
    extract = "/tmp/restore_extract"
    with open(tmp, "wb") as buf:
        shutil.copyfileobj(backup_file.file, buf)
    with zipfile.ZipFile(tmp, "r") as zf:
        zf.extractall(extract)
    if os.path.exists(f"{extract}/catalog.db"):
        shutil.copy(f"{extract}/catalog.db", "data/catalog.db")
    if os.path.exists(f"{extract}/icons"):
        shutil.copytree(f"{extract}/icons", "data/icons", dirs_exist_ok=True)
    init_db()
    return RedirectResponse(url="/", status_code=303)

@router.get("/backup/category/{category_name}", dependencies=[Depends(require_role(["admin"]))])
def backup_category(category_name: str, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT * FROM items WHERE category = ?", (category_name,))
    items = [dict(row) for row in c.fetchall()]
    path = f"/tmp/tab_{category_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return FileResponse(path, media_type="application/json", filename=f"tab_{category_name}.json")

@router.post("/tab/move", dependencies=[Depends(require_role(["admin"]))])
def move_tab(
    category:  str = Form(...),
    direction: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    c = db.cursor()
    c.execute("SELECT DISTINCT category FROM items WHERE category != ''")
    cats = [r[0] for r in c.fetchall()]
    c.execute("SELECT category, sort_index FROM tab_order ORDER BY sort_index")
    order = {r[0]: r[1] for r in c.fetchall()}
    cats = sorted(cats, key=lambda x: order.get(x, 9999))

    if category in cats:
        idx = cats.index(category)
        if direction == "left" and idx > 0:
            cats[idx], cats[idx - 1] = cats[idx - 1], cats[idx]
        elif direction == "right" and idx < len(cats) - 1:
            cats[idx], cats[idx + 1] = cats[idx + 1], cats[idx]

    c.execute("DELETE FROM tab_order")
    c.executemany("INSERT INTO tab_order VALUES (?,?)", [(cat, i * 10) for i, cat in enumerate(cats)])
    db.commit()
    return RedirectResponse(url=f"/?active_tab={urllib.parse.quote(category)}", status_code=303)
