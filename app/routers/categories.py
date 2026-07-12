from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
import sqlite3
import urllib.parse
from app.db import get_db
from app.auth_manager import require_role

router = APIRouter()

@router.post("/category/rename", dependencies=[Depends(require_role(["admin"]))])
def rename_category(
    old_name: str = Form(...),
    new_name: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    new_name = new_name.strip()
    if new_name:
        c = db.cursor()
        c.execute("UPDATE items    SET category = ? WHERE category = ?", (new_name, old_name))
        c.execute("UPDATE tab_order SET category = ? WHERE category = ?", (new_name, old_name))
        db.commit()
    return RedirectResponse(url=f"/?active_tab={urllib.parse.quote(new_name)}", status_code=303)

@router.post("/category/delete", dependencies=[Depends(require_role(["admin"]))])
def delete_category(
    category_name: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    c = db.cursor()
    c.execute("DELETE FROM items     WHERE category = ?", (category_name,))
    c.execute("DELETE FROM tab_order WHERE category = ?", (category_name,))
    db.commit()
    return RedirectResponse(url="/", status_code=303)
