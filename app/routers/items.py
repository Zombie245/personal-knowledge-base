from fastapi import APIRouter, Request, Form, Depends, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
import sqlite3
import json
import urllib.parse
import requests
import os
import shutil
from app.db import get_db
from app.auth_manager import require_role, get_tab_role
from app.templates_config import render, get_categories
from app.utils import parse_links, parse_ratings, unparse_links, unparse_ratings, safe_icon_filename

router = APIRouter()

def _assert_can_edit(request: Request, db: sqlite3.Connection, category: str):
    """Серверна перевірка: чи має користувач права editor на цю вкладку."""
    if get_tab_role(request, db, category) != "editor":
        raise HTTPException(status_code=403, detail="Access Denied")

@router.get("/add", dependencies=[Depends(require_role(["admin", "editor"]))])
def add_form(request: Request, category: str = "Загальне", db: sqlite3.Connection = Depends(get_db)):
    _assert_can_edit(request, db, category)
    return render(request, "form.html", {
        "item": None,
        "prefill_category": category,
        "categories": get_categories(db.cursor())
    })

@router.get("/edit/{item_id}", dependencies=[Depends(require_role(["admin", "editor"]))])
def edit_form(request: Request, item_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404)
    item = dict(row)
    _assert_can_edit(request, db, item["category"])
    item["links_text"]   = unparse_links(item["links"])
    item["ratings_text"] = unparse_ratings(item["ratings"])
    return render(request, "form.html", {"item": item, "categories": get_categories(c)})

@router.post("/save", dependencies=[Depends(require_role(["admin", "editor"]))])
async def save_item(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    item_id: int          = Form(None),
    category: str         = Form("Загальне"),
    name: str             = Form(...),
    version: str          = Form(""),
    status: str           = Form(""),
    tags: str             = Form(""),
    description: str      = Form(""),
    opinion: str          = Form(""),
    install_instructions: str = Form(""),
    links_text: str       = Form(""),
    ratings_text: str     = Form(""),
    icon_upload: UploadFile = File(None),
    delete_icon: bool     = Form(False)
):
    _assert_can_edit(request, db, category)

    icon_filename = None
    if delete_icon:
        icon_filename = ""
    elif icon_upload and icon_upload.filename:
        safe = safe_icon_filename(icon_upload.filename, f"custom_{item_id or 'new'}")
        if safe:
            icon_filename = safe
            with open(os.path.join("data/icons", icon_filename), "wb") as buf:
                shutil.copyfileobj(icon_upload.file, buf)

    c = db.cursor()
    fields = (category, name, version, status, tags, description,
              parse_links(links_text), parse_ratings(ratings_text), opinion, install_instructions)

    if item_id:
        if icon_filename is not None:
            c.execute(
                "UPDATE items SET category=?,name=?,version=?,status=?,tags=?,description=?,"
                "links=?,ratings=?,opinion=?,install_instructions=?,icon_file=? WHERE id=?",
                (*fields, icon_filename, item_id)
            )
        else:
            c.execute(
                "UPDATE items SET category=?,name=?,version=?,status=?,tags=?,description=?,"
                "links=?,ratings=?,opinion=?,install_instructions=? WHERE id=?",
                (*fields, item_id)
            )
    else:
        c.execute(
            "INSERT INTO items (category,name,version,status,tags,description,"
            "links,ratings,opinion,install_instructions,icon_file) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (*fields, icon_filename or "")
        )

    db.commit()
    return RedirectResponse(url=f"/?active_tab={urllib.parse.quote(category)}", status_code=303)

@router.post("/delete/{item_id}", dependencies=[Depends(require_role(["admin", "editor"]))])
def delete_item(request: Request, item_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT category FROM items WHERE id = ?", (item_id,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404)
    cat = row[0]
    _assert_can_edit(request, db, cat)
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    return RedirectResponse(url=f"/?active_tab={urllib.parse.quote(cat)}", status_code=303)

@router.post("/auto_icons", dependencies=[Depends(require_role(["admin"]))])
def auto_icons(active_tab: str = Form(""), db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT id, links FROM items WHERE icon_file = '' OR icon_file IS NULL")
    rows = c.fetchall()

    for row in rows:
        links = json.loads(row["links"]) if row["links"] else []
        if not links:
            continue
        domain = urllib.parse.urlparse(links[0]["url"]).netloc
        if not domain:
            continue
        filename = f"auto_{row['id']}_{domain}.png"
        filepath = os.path.join("data/icons", filename)
        for url in [
            f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
            f"https://icons.duckduckgo.com/ip3/{domain}.ico",
            f"https://icon.horse/icon/{domain}",
        ]:
            try:
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200 and len(resp.content) > 100:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    c.execute("UPDATE items SET icon_file = ? WHERE id = ?", (filename, row["id"]))
                    break
            except Exception:
                pass

    db.commit()
    return RedirectResponse(url=f"/?active_tab={urllib.parse.quote(active_tab)}", status_code=303)
