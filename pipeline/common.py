"""Shared helpers: city settings, work files, HTTP, geometry, date parsing."""
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "walk-through-time/1.0 (+https://github.com/varmara/walk-through-time)"
MAX_YEAR = datetime.now(timezone.utc).year


# ---------------------------------------------------------------- city and work files
def city(city_id):
    return json.loads(Path(f"cities/{city_id}.json").read_text())


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


# ---------------------------------------------------------------- HTTP
def http(url, data=None, params=None, accept="application/json", tries=4, timeout=180):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data else None
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "User-Agent": UA, "Accept": accept,
                **({"Content-Type": "application/x-www-form-urlencoded"} if body else {}),
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - retry any network or server error
            last = e
            if attempt < tries - 1:
                wait = 10 * (attempt + 1)
                log(f"  {url.split('/')[2]}: {e}; retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"{url.split('?')[0]}: {last}")


# ---------------------------------------------------------------- geometry (lon/lat degrees)
def point_in_ring(x, y, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def bbox(ring):
    xs = [c[0] for c in ring]
    ys = [c[1] for c in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def centroid(ring):
    n = len(ring) - 1 if ring[0] == ring[-1] else len(ring)
    return [sum(c[0] for c in ring[:n]) / n, sum(c[1] for c in ring[:n]) / n]


def metres(a, b):
    """Approximate distance in metres between two lon/lat points (fine at city scale)."""
    kx = 111320 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 110540)


CELL = 0.002   # grid cell in degrees (about 140 x 220 m)
_grids = {}


def _grid(buildings):
    """Spatial index: grid cell -> building indexes whose bounding box touches it. Cached per list."""
    key = id(buildings)
    if key not in _grids or _grids[key][0] is not buildings:
        g = {}
        for i, b in enumerate(buildings):
            bb = b["bb"]
            for cx in range(int(bb[0] // CELL), int(bb[2] // CELL) + 1):
                for cy in range(int(bb[1] // CELL), int(bb[3] // CELL) + 1):
                    g.setdefault((cx, cy), []).append(i)
        _grids[key] = (buildings, g)
    return _grids[key][1]


def building_at(buildings, x, y, near=0):
    """Index of the building containing (x, y); with near > 0, else the closest within `near` metres."""
    pad = near / 70000 if near else 0
    best, best_d = None, None
    g = _grid(buildings)
    cand = set()
    for cx in range(int((x - pad) // CELL), int((x + pad) // CELL) + 1):
        for cy in range(int((y - pad) // CELL), int((y + pad) // CELL) + 1):
            cand.update(g.get((cx, cy), ()))
    for i in sorted(cand):
        b = buildings[i]
        bb = b["bb"]
        if not (bb[0] - pad <= x <= bb[2] + pad and bb[1] - pad <= y <= bb[3] + pad):
            continue
        if any(point_in_ring(x, y, r) for r in b["rings"]):
            return i
        if near:
            d = metres(centroid(b["rings"][0]), [x, y])
            if d <= near and (best_d is None or d < best_d):
                best, best_d = i, d
    return best


def stitch_rings(ways):
    rings, open_ = [], [list(w) for w in ways]
    while open_:
        ring = open_.pop(0)
        guard = 0
        while not (len(ring) > 3 and ring[0] == ring[-1]) and guard < 500:
            guard += 1
            end = ring[-1]
            idx = next((i for i, w in enumerate(open_) if w[0] == end or w[-1] == end), None)
            if idx is None:
                break
            nxt = open_.pop(idx)
            if nxt[0] != end:
                nxt = nxt[::-1]
            ring += nxt[1:]
        if len(ring) > 3:
            rings.append(ring)
    return rings


def rnd(coords):
    return [[round(x, 6), round(y, 6)] for x, y in coords]


# ---------------------------------------------------------------- dates
# Flags describe how precise a building's year is. The page draws less precise dates paler.
EXACT, APPROX, CENTURY = "exact", "approx", "century"


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
