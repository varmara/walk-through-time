"""Shared helpers: city settings, work files, the log, and reading dates.

The rest is in its own module: web.py (requests and the cache), geo.py (geometry), names.py (naming rules),
texts.py (words stored once).
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_YEAR = datetime.now(timezone.utc).year


# ---------------------------------------------------------------- city and work files
def city(city_id):
    return json.loads(Path(f"cities/{city_id}.json").read_text())


def sources(c, kind):
    """A city's council map services of a kind (cities/<city>.json "sources"), leaving out those switched off
    ("off": why, e.g. until their terms are confirmed)."""
    return [x for x in c.get("sources", {}).get(kind, []) if not x.get("off")]


def work(city_id, name):
    """Intermediate files live in work/<city>/ (not committed)."""
    p = Path("work") / city_id
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{name}.json"


def save(city_id, name, obj):
    work(city_id, name).write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def load(city_id, name):
    return json.loads(work(city_id, name).read_text())


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- dates
# Flags describe how precise a building's year is. The page draws less precise dates paler.
EXACT, APPROX, CENTURY = "exact", "approx", "century"
AREA = "area"   # not a date for the building: the build period most homes in its small area share (Council Tax)


def parse_year(raw):
    """Free-text date (OpenStreetMap start_date and similar) -> (year, flag) or None.

    1890 -> exact; c1890, ~1890, 1885..1895, 1890s -> approx; C19, mid 19th century -> century.
    """
    if raw is None:
        return None
    s = str(raw).strip().lower()
    m = re.search(r"(\d{4})\s*(?:\.\.|–|-|to)\s*(\d{4})", s)
    if m:
        a, b = int(m[1]), int(m[2])
        return round((a + b) / 2), (APPROX if b - a <= 30 else CENTURY)
    m = re.search(r"\b(\d{3})0s\b", s)
    if m:
        return int(m[1] + "5"), APPROX
    if not re.search(r"\d{4}", s):
        m = re.search(r"\bc\s?(\d{1,2})\b", s) or re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*c(?:entury)?\b", s)
        if m:
            base = (int(m[1]) - 1) * 100
            off = 20 if re.search(r"early|first half", s) else 80 if re.search(r"late|second half", s) else 50
            return base + off, CENTURY
        return None
    y = int(re.search(r"(\d{4})", s)[1])
    if y < 1000 or y > MAX_YEAR:
        return None
    approx = re.match(r"^(c|ca|circa|about|~|before|after|early|mid|late|pre)", s) or re.search(r"[?~]", s)
    return y, (APPROX if approx else EXACT)
