from fastapi import Request
from fastapi.templating import Jinja2Templates
import json

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["fromjson"] = lambda s: json.loads(s) if s else {}

def render(request: Request, name: str, extra: dict = None):
    ctx = {
        "request": request,
        "t":       request.state.t,
        "lang":    request.state.lang,
    }
    if extra:
        ctx.update(extra)
    return templates.TemplateResponse(request=request, name=name, context=ctx)

def get_categories(cursor) -> list[str]:
    cursor.execute("SELECT DISTINCT category FROM items WHERE category != '' ORDER BY category")
    return [r[0] for r in cursor.fetchall()]
