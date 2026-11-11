"""Shared helpers: city settings, work files, HTTP, geometry, date parsing."""
import gzip
import hashlib
import json
import math
import os
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
# ---------------------------------------------------------------- saved answers from web services
# With $WTT_CACHE set to a folder, every successful answer from a web service (Wikipedia, Wikidata, Commons,
# Historic England's and Natural England's map services, Overpass…) is saved there, and the same request later
# is answered from the folder instead of the network. GitHub Actions keeps the folder between builds, so a build
# after a code or story change asks only for what is new; the scheduled builds start with an empty folder and
# so fetch everything fresh. Without $WTT_CACHE (e.g. on a laptop) nothing is saved.
def _cache_file(*parts):
    root = os.environ.get("WTT_CACHE")
    if not root:
        return None
    key = hashlib.sha1("\n".join(str(p) for p in parts).encode()).hexdigest()
    d = Path(root) / key[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / (key + ".gz")


def cached(kind, url, body=None):
    f = _cache_file(kind, url, body)
    if f and f.exists():
        try:
            return gzip.decompress(f.read_bytes())
        except (OSError, EOFError):
            f.unlink(missing_ok=True)
    return None


def keep(kind, url, body, raw):
    f = _cache_file(kind, url, body)
    if f:
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(raw, 6))
        tmp.replace(f)


def http(url, data=None, params=None, accept="application/json", tries=4, timeout=180):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data else None
    hit = cached(accept, url, body)
    if hit is not None:
        return json.loads(hit.decode("utf-8"))
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "User-Agent": UA, "Accept": accept,
                **({"Content-Type": "application/x-www-form-urlencoded"} if body else {}),
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            out = json.loads(raw.decode("utf-8"))
            failed = isinstance(out, dict) and ("error" in out or "error" in str(out.get("remark", "")).lower())
            if not failed:              # an API's error or Overpass's timeout remark is not worth keeping
                keep(accept, url, body, raw)
            return out
        except Exception as e:  # noqa: BLE001 - retry any network or server error
            last = e
            if attempt < tries - 1:
                wait = 10 * (attempt + 1)
                log(f"  {url.split('/')[2]}: {e}; retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"{url.split('?')[0]}: {last}")


def http_text(url, tries=3, timeout=60):
    """A web page as plain text (tags removed), for checking facts against it."""
    import html as _html
    last = None
    for attempt in range(tries):
        try:
            hit = cached("text/html", url)
            if hit is None:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    hit = r.read()
                keep("text/html", url, None, hit)
            raw = hit.decode("utf-8", "replace")
            title = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
            body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S)
            body = _html.unescape(re.sub(r"<[^>]+>", " ", body))
            return {"title": _html.unescape(re.sub(r"<[^>]+>", "", title[1])).strip() if title else url,
                    "text": " ".join(body.split())}
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


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


# ---------------------------------------------------------------- names: what a building was, not who is in it now
OCCUPANT_KEYS = ("shop", "office", "brand", "brand:wikidata", "operator", "craft", "healthcare")
OCCUPANT_AMENITY = {"bank", "restaurant", "cafe", "fast_food", "bar", "pub", "nightclub", "pharmacy", "doctors",
                    "dentist", "post_office", "bureau_de_change", "money_transfer", "betting", "gambling", "casino"}
_HE_TAIL = re.compile(r"\s*(?:,|\bAND\b|\bWITH\b|\bINCLUDING\b)\s*(?:THE\s+)?(?:ATTACHED|ADJOINING|ADJACENT|FRONT|BOUNDARY|"
                      r"GATES?|GATEPIERS?|RAILINGS?|WALLS?|PIERS|FORECOURT|LAMP|STEPS|AREA)\b.*$", re.I)


def occupied(tags):
    """True when the outline's name is probably a business inside it (a shop, an office, a brand) rather than
    the building's own name: OpenStreetMap often puts the occupier's tags on the building."""
    return any(tags.get(k) for k in OCCUPANT_KEYS) or tags.get("amenity") in OCCUPANT_AMENITY


def tidy_listing(name):
    """Historic England's name for a building, readable: 'NEWCASTLE HOUSE AND ATTACHED BOUNDARY WALL' ->
    'Newcastle House'. None when it is only an address ('3 AND 5, HOUNDS GATE')."""
    if not name:
        return None
    n = name.strip()
    was = re.search(r"\bformerly (?:the )?(.+)$", n, re.I)     # "11 Pelham Street…, formerly the Nottingham and…"
    if was:
        n = was[1]
    n = _HE_TAIL.sub("", re.sub(r"\s*\([^)]*\)", "", n)).strip(" ,")
    n = re.sub(r",\s*Nottingham$", "", n, flags=re.I)
    if not n or re.match(r"^\d", n) or re.match(r"^(?:NOS?\.?|NUMBERS?)\s*\d", n, re.I):
        return None
    if re.match(r"^(?:railings|walls?|gates?|gate piers|steps|boundary|lamp|bollards?|kerb)\b", n, re.I):
        return None                       # a listing of railings or a wall names no building
    if n.isupper():
        n = n.title()
    n = re.sub(r"\b(And|Of|The|At|To|On|In|For)\b", lambda m: m[1].lower(), n).replace("'S ", "'s ")
    return n[0].upper() + n[1:]


BUILDINGISH = re.compile(r"\b(house|hall|chapel|church|school|mill|bank|inn|arms|hotel|theatre|cinema|picture|station|works|"
                         r"factory|warehouse|baths|library|exchange|buildings?|chambers|court|lodge|cottages?|almshouses?|"
                         r"institute|club|tavern|brewery|market|offices|mission|tabernacle|hospital|asylum|gaol|barracks|home|"
                         r"school|college|museum|gallery|cross|tower|lodge|works|depot|shop|stores|arcade|castle|centre|site)\b", re.I)
_PLAIN = {"the", "and", "of", "at", "to", "on", "in", "for", "a", "st", "saint", "former", "old", "new", "nottingham"}


def _words(s):
    s = re.sub(r"['’]", "", (s or "").lower())            # Severn's, Severns'
    return {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", s) if w not in _PLAIN}


def other_names(tags, name, today, label=None, listing_name=None):
    """The building's other names, oldest first where known: its old name, Historic England's, Wikidata's, another
    name in OpenStreetMap ("Midland Railway Station" for Nottingham station; "Pearson's Department Store")."""
    seen = {(name or "").lower(), (today or "").lower()}
    out = []
    for n in (tags.get("old_name"), tags.get("historic:name"), tidy_listing(listing_name), label, tags.get("building:name"),
              tags.get("alt_name"), tags.get("name") if tags.get("name") != today else None):
        for part in (n or "").split(";"):
            part = part.strip()
            key = re.sub(r"\s*\([^)]*\)", "", part).lower()      # "D34 (Fire Station) At …" is "D34 at …"
            if part and key not in seen and not any(key in s or s in key for s in seen if s):
                seen.add(key)
                out.append(part)
    return out or None


LANDMARK = re.compile(r"\b(museum|gallery|theatre|cinema|college|university|school|church|cathedral|chapel|"
                      r"mosque|synagogue|station|library|hospital|arts centre|concert hall)\b", re.I)
LANDMARK_USE = {"amenity": {"theatre", "cinema", "arts_centre", "library", "college", "university", "school",
                            "place_of_worship", "townhall", "courthouse", "hospital", "concert_hall"},
                "tourism": {"museum", "gallery"}, "building": {"train_station", "church", "cathedral", "chapel",
                                                               "university", "college", "museum"},
                "railway": {"station"}, "public_transport": {"station"}}


_TRADE = re.compile(r"\b(bar|caf[eé]|restaurant|gaming|pub|grill|lounge|hotel|former|academy|global|ltd|limited)\b", re.I)


def landmark(tags_list, now):
    """A lasting public institution (a museum, theatre, college, church, station), whose current name belongs in
    the title next to what the building was: 'Shire Hall and County Gaol · National Justice Museum'. Its name must
    say so, and not be a business's ('Riverbank Bar and Gallery') or an old name ('Former Police Station')."""
    return bool(now and LANDMARK.search(now) and not _TRADE.search(now))


def same_place(a, b):
    """Two ways of naming one thing: 'Church of St Mary' and 'St Mary's Church'; 'The Corner House' and
    'The Cornerhouse'; 'Castle Gate Congregational Church' and '… Centre'."""
    squash = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(the|of|church|saint|st)\b", "", n.lower()))  # noqa: E731
    if squash(a) and squash(b) and (squash(a) in squash(b) or squash(b) in squash(a)):
        return True
    mine = lambda n: _words(n) - {m.lower().rstrip("s") for m in BUILDINGISH.findall(n)}  # noqa: E731
    return bool(mine(a) & mine(b))


FIXTURES = {"vending_machine", "photo_booth", "atm", "telephone", "post_box", "bench", "waste_basket",
            "bicycle_parking", "parking_entrance", "ticket_validator", "drinking_water", "recycling", "toilets",
            "charging_station", "luggage_locker", "left_luggage", "clock", "fountain", "bureau_de_change",
            "parcel_locker", "public_bookcase", "shelter", "kiosk"}


def marker(tags):
    """A thing on or in a building that names something else: a plaque or memorial ("Near this site stood the
    Malt Cross"), a sign, or a fixture (a Photo-Me booth in the station, a cash machine)."""
    return ((tags.get("historic") and tags["historic"] not in ("building", "castle", "church", "manor", "house"))
            or tags.get("memorial") or tags.get("tourism") == "information"
            or tags.get("amenity") in FIXTURES or tags.get("shop") in ("kiosk", "vending")
            or tags.get("vending"))


def he_names_more(he, osm):
    """Historic England's name says what the building was, and the OpenStreetMap name is another thing entirely
    (an occupier without shop or office tags: "Regus" in Stanford House, "Jem Leisure" in the Midland Bank)."""
    if not he or not osm or not BUILDINGISH.search(he) or re.match(r"^(railings|walls?|gates?|steps|boundary)\b", he, re.I):
        return False
    mine = lambda n: _words(n) - {m.lower().rstrip("s") for m in BUILDINGISH.findall(n)}  # noqa: E731
    # both must name something of their own ("Nottingham Castle" names only the town and the kind of building),
    # and nothing in common ("Musters Road Methodist Church" is "West Bridgford Methodist Church")
    return bool(mine(he)) and bool(mine(osm)) and not (mine(he) & mine(osm))


def house_numbers(n):
    """An address's numbers as written: '15;16' -> '15 and 16', '3;5;7' -> '3, 5 and 7', '2-4' -> '2–4'."""
    parts = [x.strip().replace("-", "–") for x in re.split(r"[;,]", n or "") if x.strip()]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1] if parts else ""


def building_name(tags, story=None, label=None, listing_name=None, place=None):
    """(name, today): the name to show and, if different, who or what uses the building today.

    Prefer what the building was: a story's name, the building's own name in OpenStreetMap (building:name,
    historic:name), Historic England's name, the listed building's Wikidata item, an old_name that names a
    building ("Kings Arms", "Albert Hall"; old_name is more often just the previous shop, which is skipped);
    the OpenStreetMap name only when it is the building's own name, otherwise it becomes 'today'."""
    osm = tags.get("name")
    own = tags.get("building:name") or tags.get("historic:name") or tags.get("name:historic")
    old = tags.get("old_name")
    if old and (";" in old or not BUILDINGISH.search(old)):
        old = None
    he = tidy_listing(listing_name)
    if label and re.match(r"^(?:railings|walls?|gates?|gate piers|steps|boundary)\b", label, re.I):
        label = None                      # a listing of railings names no building
    if label:   # Wikidata labels of listed buildings copy Historic England's: tidy them the same way
        label = re.sub(r"\b(And|Of|The|At|To|On|In|For)\b", lambda m: m[1].lower(),
                       _HE_TAIL.sub("", label).strip(" ,")) or label
        label = label[0].upper() + label[1:]
    num, street = tags.get("addr:housenumber"), tags.get("addr:street")
    address = f"{house_numbers(num)} {street}" if num and street else None
    # an unlisted shop, café or office with no name for the building itself: its address, the business 'Today'
    # (a building with only an address stays unnamed: its card is titled by the address)
    trade = tags.get("building") in ("retail", "commercial", "office", "industrial", "warehouse", "supermarket", "kiosk")
    if story:
        name = story
    elif own:
        name = own
    elif osm and not occupied(tags) and not he_names_more(he, osm) and not (trade and address and not he and not label
                                                                           and not BUILDINGISH.search(osm)):
        name = osm
    else:
        # a pub's name, or a name that says what the building is ("Kings Arms", "Albert Hall"), beats the address
        keep = osm and (tags.get("amenity") == "pub" or BUILDINGISH.search(osm))
        name = he or label or old or (osm if keep else address if osm else None) or osm or place
    m = re.match(r"^(?:Numbers?|Nos?\.?)\s+(\d.*)$", name or "")
    if m:                                 # "Numbers 119 and 121" -> "119 and 121 Derby Road"
        street = tags.get("addr:street")
        name = m[1] + (f" {street}" if street and street.lower() not in m[1].lower() else "")
    today = (osm if osm and name and osm.strip().lower() not in name.strip().lower()
             and (occupied(tags) or own or he_names_more(he, osm) or name == address) else None)   # not "Newton" for the Newton Building
    return name, today
