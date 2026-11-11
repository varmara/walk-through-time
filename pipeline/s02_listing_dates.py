"""Dates of listed buildings, from Wikipedia's lists of listed buildings.

Historic England's list entries describe each building and give its date, but their pages cannot be read
automatically. Wikipedia has a list for every ward and parish ("Listed buildings in Nottingham (Clifton North
ward)", "Listed buildings in West Bridgford"), written from those entries, with a date for every building:
"Late 14th century", "c. 1720", "1736". This step reads those lists (CC BY-SA) and ties each row to its list
entry, by the entry's number in the row's reference, or failing that by the row's coordinates (within MAX_M
metres of a listed point of the same grade).

Writes work/<city>/listdates.json: {list entry number: {"text": date as written, "page": Wikipedia title}}.
"""
import re

from .common import load, log, save
from .web import http
from .geo import metres

WIKI = "https://en.wikipedia.org/w/api.php"
# per city: Wikipedia categories holding the lists, and searches that find lists outside them
SOURCES = {
    "nottingham": {"categories": ["Lists of listed buildings in Nottinghamshire"],
                   "searches": ['intitle:"Listed buildings in Nottingham"', 'intitle:"Listed buildings in" Rushcliffe',
                                'intitle:"Listed buildings in West Bridgford"', 'intitle:"Listed buildings in" Nottinghamshire']},
}
MAX_M = 25
ROW_TEMPLATES = ("english heritage listed building row", "eh listed building row", "historic building row")


def list_pages(cfg):
    titles = set()
    for cat in cfg["categories"]:
        todo, seen = ["Category:" + cat], set()
        while todo:
            c = todo.pop()
            if c in seen or len(seen) > 30:
                continue
            seen.add(c)
            cont = {}
            while True:
                r = http(WIKI, params={"action": "query", "list": "categorymembers", "cmtitle": c, "cmlimit": "500",
                                       "cmtype": "page|subcat", "format": "json", **cont})
                for m in r.get("query", {}).get("categorymembers", []):
                    (todo.append(m["title"]) if m["ns"] == 14 else titles.add(m["title"]))
                if "continue" not in r:
                    break
                cont = {"cmcontinue": r["continue"]["cmcontinue"]}
    for q in cfg["searches"]:
        r = http(WIKI, params={"action": "query", "list": "search", "srsearch": q, "srlimit": "500",
                               "srnamespace": "0", "format": "json"})
        titles.update(s["title"] for s in r.get("query", {}).get("search", []))
    return sorted(t for t in titles if t.lower().startswith("listed buildings in") or t.lower().startswith("grade"))


def wikitexts(titles):
    got = {}
    for i in range(0, len(titles), 50):
        r = http(WIKI, params={"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                               "format": "json", "formatversion": "2", "titles": "|".join(titles[i:i + 50])})
        for pg in r.get("query", {}).get("pages", []):
            if pg.get("revisions"):
                got[pg["title"]] = pg["revisions"][0]["slots"]["main"]["content"]
    return got


def templates(text):
    """Top-level {{...}} spans of a text, as (start, end)."""
    out, depth, start = [], 0, None
    for m in re.finditer(r"\{\{|\}\}", text):
        if m[0] == "{{":
            if depth == 0:
                start = m.start()
            depth += 1
        elif depth:
            depth -= 1
            if depth == 0:
                out.append((start, m.end()))
    return out


def params(tpl):
    """'{{name|a=1|b={{x|y}}}}' -> {'_name': 'name', 'a': '1', 'b': '{{x|y}}'} (splits on top-level pipes)."""
    body, parts, depth, cur = tpl[2:-2], [], 0, ""
    for tok in re.split(r"(\{\{|\}\}|\[\[|\]\]|\|)", body):
        if tok in ("{{", "[["):
            depth += 1
        elif tok in ("}}", "]]"):
            depth -= 1
        if tok == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += tok
    parts.append(cur)
    out = {"_name": parts[0].strip().lower()}
    for k, p in enumerate(parts[1:]):
        if "=" in p and re.match(r"^\s*[\w -]+\s*=", p):
            a, b = p.split("=", 1)
            out[a.strip().lower()] = b.strip()
        else:
            out[str(k + 1)] = p.strip()
    return out


def plain(s):
    s = re.sub(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", " ", s or "", flags=re.S)
    for a, b in reversed(templates(s)):
        p = params(s[a:b])
        name = p["_name"]
        keep = (("c. " + p.get("1", "")) if name in ("circa", "c.") else p.get("1", "") if name in ("nowrap", "small")
                else p.get("2", p.get("1", "")) if name in ("sort", "sortname", "hs") else " ")   # {{sort|1650|17th century}}
        s = s[:a] + keep + s[b:]
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>|'{2,}", " ", s)
    return re.sub(r"\s+", " ", s).strip(" ,;")


def numbers(raw):
    return {int(n) for g in re.findall(r"(?:num|entry|list_entry|nhle|hectad)\s*=\s*(\d{7})|list-entry/(\d{7})|"
                                       r"\{\{\s*NHLE\s*\|\s*(\d{7})", raw, re.I) for n in g if n}


def coords(raw):
    m = re.search(r"\{\{\s*coord\s*\|([^{}]*)\}\}", raw, re.I)
    if not m:
        return None
    p = [x.strip() for x in m[1].split("|")]
    try:
        if len(p) >= 2 and re.match(r"^-?\d+\.\d+$", p[0]) and re.match(r"^-?\d+\.\d+$", p[1]):
            return float(p[1]), float(p[0])
        if "N" in p and ("W" in p or "E" in p):
            n = p.index("N")
            lat = sum(float(v) / 60 ** k for k, v in enumerate(p[:n]))
            ew = "W" if "W" in p else "E"
            e = p.index(ew)
            lon = sum(float(v) / 60 ** k for k, v in enumerate(p[n + 1:e]))
            return (-lon if ew == "W" else lon), lat
    except ValueError:
        return None
    return None


def grade_of(s):
    m = re.search(r"(II\*|\bII\b|\bI\b)", plain(s) or "")
    return m[1] if m else None


def rows(text):
    """Every row of every list on a page: {"date", "grade", "nums", "xy"}."""
    out = []
    for a, b in templates(text):
        p = params(text[a:b])
        if p["_name"] in ROW_TEMPLATES:
            date = next((v for k, v in p.items() if "date" in k and "list" not in k), None)
            g = p.get("grade")
            out.append({"date": plain(date), "grade": grade_of(g) if g else None, "nums": numbers(text[a:b]),
                        "xy": coords(text[a:b]) or ((float(p["lon"]), float(p["lat"])) if re.match(r"^-?\d+\.\d+$", p.get("lat", "")) and re.match(r"^-?\d+\.\d+$", p.get("lon", "")) else None)})
    for table in re.findall(r"\{\|.*?\n\|\}", text, re.S):
        head = re.findall(r"^!(.*)$", table, re.M)
        cols = [plain(re.sub(r"^[^|]*\|(?!\|)", "", h) if "=" in h.split("|")[0] else h).lower()
                for line in head for h in line.split("!!")]
        di = next((k for k, h in enumerate(cols) if "date" in h and "list" not in h), None)
        gi = next((k for k, h in enumerate(cols) if h.startswith("grade")), None)
        if di is None:
            continue
        for raw in re.split(r"\n\|-[^\n]*", table)[1:]:
            if raw.lstrip().startswith("!"):
                continue
            nums, xy = numbers(raw), coords(raw)
            clean = re.sub(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", " ", raw, flags=re.S)
            for a, b in reversed(templates(clean)):           # multi-line templates would break the cells
                clean = clean[:a] + plain(clean[a:b]).replace("\n", " ") + clean[b:]
            cells, cur = [], None
            for line in clean.split("\n"):
                if line.startswith("|") and not line.startswith("|}"):
                    if cur is not None:
                        cells.append(cur)
                    bits = line[1:].split("||")
                    cells += bits[:-1]
                    cur = bits[-1]
                elif cur is not None:
                    cur += " " + line
            if cur is not None:
                cells.append(cur)
            cells = [re.sub(r"^\s*[a-z-]+\s*=\s*\"?[^|\"]*\"?\s*\|(?!\|)", "", c) for c in cells]   # cell attributes
            if di >= len(cells):
                continue
            out.append({"date": plain(cells[di]), "grade": grade_of(cells[gi]) if gi is not None and gi < len(cells) else None,
                        "nums": nums, "xy": xy})
    return [r for r in out if r["date"] and re.search(r"\d", r["date"])]


def main(city_id):
    cfg = SOURCES.get(city_id)
    if not cfg:
        save(city_id, "listdates", {})
        return
    listed = load(city_id, "listed")
    by_num = {int(p["ListEntry"]): p for p in listed}
    try:
        pages = list_pages(cfg)
        texts = wikitexts(pages)
    except Exception as e:  # noqa: BLE001 - optional source
        log(f"s02 listing dates: Wikipedia failed, no list dates this run: {e}")
        save(city_id, "listdates", {})
        return
    out, n_rows, by_xy = {}, 0, 0
    for title, text in texts.items():
        for r in rows(text):
            n_rows += 1
            hit = [n for n in r["nums"] if n in by_num]
            if not hit and r["xy"]:
                near = sorted((metres([p["x"], p["y"]], r["xy"]), int(p["ListEntry"])) for p in listed
                              if abs(p["x"] - r["xy"][0]) < 0.0005 and abs(p["y"] - r["xy"][1]) < 0.0004
                              and (not r["grade"] or p.get("Grade") == r["grade"]))
                near = [n for n in near if n[0] <= MAX_M]
                # the nearest listed point, if it is clearly the nearest (a terrace has several entries side by side)
                if near and (len(near) == 1 or near[0][0] <= 8 or near[0][0] * 2 <= near[1][0]):
                    hit = [near[0][1]]
                    by_xy += 1
            for n in hit:
                out.setdefault(str(n), {"text": r["date"][:80], "page": title})
    save(city_id, "listdates", out)
    log(f"s02 listing dates: {len(texts)} Wikipedia lists, {n_rows} rows; dates for {len(out)}/{len(listed)} "
        f"list entries ({by_xy} by coordinates)")
    for k in list(out)[:8]:
        log(f"      {k}: {out[k]['text']} ({out[k]['page']})")
