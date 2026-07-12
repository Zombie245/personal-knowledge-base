import json

def parse_links(text: str) -> str:
    if not text:
        return "[]"
    links = [
        {"name": n.strip(), "url": u.strip()}
        for line in text.replace('\r', '').split('\n')
        if '|' in line
        for n, u in [line.split('|', 1)]
    ]
    return json.dumps(links)

def parse_ratings(text: str) -> str:
    if not text:
        return "[]"
    ratings = []
    for line in text.replace('\r', '').split('\n'):
        if '|' not in line:
            continue
        m, s = line.split('|', 1)
        try:
            ratings.append({"metric": m.strip(), "score": int(s.strip())})
        except ValueError:
            pass
    return json.dumps(ratings)

def unparse_links(json_str: str) -> str:
    if not json_str or json_str == "[]":
        return ""
    return '\n'.join(f"{l['name']} | {l['url']}" for l in json.loads(json_str))

def unparse_ratings(json_str: str) -> str:
    if not json_str or json_str == "[]":
        return ""
    return '\n'.join(f"{r['metric']} | {r['score']}" for r in json.loads(json_str))

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg'}

def safe_icon_filename(original: str, prefix: str) -> str | None:
    import os
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    safe = "".join(c for c in original if c.isalnum() or c in "._-")
    return f"{prefix}_{safe}"
