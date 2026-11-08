#!/usr/bin/env python3
"""Build the map data for one city.

Fetches buildings, roads, water and parks from OpenStreetMap (Overpass API),
listed buildings from Historic England (NHLE), and dates and details from
Wikidata, joins them, and writes data/<city id>.json for the city page.

Usage:  python scripts/build_city.py cities/nottingham.json
Only the Python standard library is used, so it runs on a bare GitHub runner.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "walk-through-time/1.0 (+https://github.com/varmara/walk-through-time)"
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
NHLE = ("https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
        "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer/0/query")
WDQS = "https://query.wikidata.org/sparql"
MAX_YEAR = datetime.now(timezone.utc).year


# ---------------------------------------------------------------- HTTP
def http(url, data=None, accept="application/json", tries=4, timeout=180):
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
        except Exception as e:  # noqa: BLE001 - retry any network/server error
            last = e
            wait = 10 * (attempt + 1)
            print(f"  {url.split('/')[2]}: {e}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"{url}: {last}")


# ---------------------------------------------------------------- Parsing helpers
def parse_year(raw):
    """OSM-style date text -> (year, approximate) or None."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    m = re.search(r"(\d{4})\s*(?:\.\.|–|-|to)\s*(\d{4})", s)
    if m:
        return round((int(m[1]) + int(m[2])) / 2), True
    m = re.search(r"\b(\d{3})0s\b", s)
    if m:
        return int(m[1] + "5"), True
    if not re.search(r"\d{4}", s):
        m = re.search(r"\bc\s?(\d{1,2})\b", s) or re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*c(?:entury)?\b", s)
        if m:
            base = (int(m[1]) - 1) * 100
            off = 20 if re.search(r"early|first half", s) else 80 if re.search(r"late|second half", s) else 50
            return base + off, True
        return None
    y = int(re.search(r"(\d{4})", s)[1])
    if y < 1000 or y > MAX_YEAR:
        return None
    approx = bool(re.match(r"^(c|ca|circa|about|~|before|after|early|mid|late|pre)", s) or re.search(r"[?~]", s))
    return y, approx


def height_of(t):
    for k in ("height", "building:height"):
        try:
            h = float(str(t.get(k, "")).replace("m", "").strip())
            if 0 < h < 400:
                return round(h, 1)
        except ValueError:
            pass
    try:
        lv = float(t.get("building:levels", ""))
    except ValueError:
        lv = 0
    try:
        rl = float(t.get("roof:levels", ""))
    except ValueError:
        rl = 0
    if lv > 0:
        return round(lv * 3.2 + rl * 1.6 + 1, 1)
    kind = t.get("building")
    if kind in ("house", "detached", "semidetached_house", "terrace", "residential"):
        return 8
    if kind in ("garage", "garages", "shed", "hut", "kiosk", "roof", "carport"):
        return 3
    if kind in ("church", "chapel"):
        return 16
    if kind == "cathedral":
        return 28
    return 10


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


def point_in_ring(x, y, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def rnd(coords):
    return [[round(x, 6), round(y, 6)] for x, y in coords]


# ---------------------------------------------------------------- Sources
def fetch_osm(b):
    bb = f"{b['s']},{b['w']},{b['n']},{b['e']}"
    q = f"""[out:json][timeout:180];(
      way["building"]({bb}); relation["building"]["type"="multipolygon"]({bb});
      way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|service|footway)$"]({bb});
      way["natural"="water"]({bb}); way["waterway"~"^(canal|river)$"]({bb}); relation["natural"="water"]({bb});
      way["leisure"~"^(park|garden)$"]({bb}); way["landuse"="grass"]({bb});
    ); out tags geom qt;"""
    last = None
    for url in OVERPASS:
        try:
            print(f"OpenStreetMap: {url}")
            return http(url, {"data": q}, tries=2)
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"All Overpass servers failed: {last}")


def fetch_listed(b):
    params = urllib.parse.urlencode({
        "where": "1=1", "geometry": f"{b['w']},{b['s']},{b['e']},{b['n']}",
        "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ListEntry,Name,Grade,hyperlink", "outSR": "4326", "returnGeometry": "true",
        "resultRecordCount": "2000", "f": "geojson",
    })
    print("Historic England: listed buildings")
    gj = http(NHLE + "?" + params)
    pts = []
    for f in gj.get("features", []):
        g = f.get("geometry") or {}
        coords = g.get("coordinates")
        if g.get("type") == "Point":
            coords = [coords]
        elif g.get("type") != "MultiPoint":
            continue
        for c in coords:
            pts.append((c[0], c[1], f["properties"]))
    return pts


WD_FIELDS = """
  OPTIONAL { ?item p:P571/psv:P571 ?iv . ?iv wikibase:timeValue ?inception ; wikibase:timePrecision ?prec . }
  OPTIONAL { ?item wdt:P18 ?image }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?item wdt:P84 ?architect . ?architect rdfs:label ?architectLabel . FILTER(LANG(?architectLabel) = "en") }
  OPTIONAL { ?item rdfs:label ?label . FILTER(LANG(?label) = "en") }"""


def fetch_wikidata(qids, nhle_ids):
    out = {}

    def take(rows, key_fn):
        for b in rows:
            k = key_fn(b)
            prev = out.get(k, {})
            info = {
                "qid": b["item"]["value"].rsplit("/", 1)[-1],
                "label": prev.get("label") or b.get("label", {}).get("value"),
                "image": prev.get("image") or b.get("image", {}).get("value"),
                "article": prev.get("article") or b.get("article", {}).get("value"),
                "architect": prev.get("architect") or b.get("architectLabel", {}).get("value"),
                "inception": prev.get("inception"), "prec": prev.get("prec"),
            }
            if "inception" in b and (not prev.get("inception") or int(b["prec"]["value"]) > (prev.get("prec") or 0)):
                info["inception"], info["prec"] = b["inception"]["value"], int(b["prec"]["value"])
            out[k] = info

    def chunks(a, n):
        return [a[i:i + n] for i in range(0, len(a), n)]

    print(f"Wikidata: {len(qids)} items by OSM tag, {len(nhle_ids)} by list entry number")
    for c in chunks(qids, 200):
        q = f"SELECT ?item ?inception ?prec ?image ?article ?architectLabel ?label WHERE {{ VALUES ?item {{ {' '.join('wd:' + x for x in c)} }} {WD_FIELDS} }}"
        take(http(WDQS, {"query": q, "format": "json"}, accept="application/sparql-results+json")["results"]["bindings"],
             lambda b: b["item"]["value"].rsplit("/", 1)[-1])
        time.sleep(1)
    for c in chunks(nhle_ids, 200):
        q = f"SELECT ?item ?nhle ?inception ?prec ?image ?article ?architectLabel ?label WHERE {{ VALUES ?nhle {{ {' '.join(chr(34) + x + chr(34) for x in c)} }} ?item wdt:P1216 ?nhle . {WD_FIELDS} }}"
        take(http(WDQS, {"query": q, "format": "json"}, accept="application/sparql-results+json")["results"]["bindings"],
             lambda b: "nhle:" + b["nhle"]["value"])
        time.sleep(1)
    return out


def wd_year(info):
    if not info or not info.get("inception"):
        return None
    m = re.match(r"^([+-]?\d+)-", info["inception"])
    if not m:
        return None
    y, p = int(m[1]), info.get("prec") or 0
    if p >= 9:
        return y, False
    if p == 8:
        return y + 5, True
    if p == 7:
        return (-(-y // 100) - 1) * 100 + 50, True
    return None


# ---------------------------------------------------------------- Build
def build(city, osm, listed, wd_fetch=fetch_wikidata):
    buildings, roads, water, parks = [], [], [], []
    for el in osm["elements"]:
        t = el.get("tags", {})
        if el["type"] == "way" and el.get("geometry"):
            coords = [[g["lon"], g["lat"]] for g in el["geometry"]]
            if t.get("building"):
                if len(coords) >= 4:
                    buildings.append({"rings": [coords], "tags": t, "osm": f"way/{el['id']}"})
            elif t.get("highway"):
                k = "minor" if t["highway"] in ("footway", "service", "pedestrian") else "major"
                roads.append({"type": "Feature", "properties": {"k": k}, "geometry": {"type": "LineString", "coordinates": rnd(coords)}})
            elif t.get("waterway"):
                water.append({"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": rnd(coords)}})
            elif t.get("natural") == "water" and len(coords) > 3:
                water.append({"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [rnd(coords)]}})
            elif (t.get("leisure") or t.get("landuse")) and len(coords) > 3:
                parks.append({"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [rnd(coords)]}})
        elif el["type"] == "relation" and el.get("members"):
            outers = [[[g["lon"], g["lat"]] for g in m["geometry"]] for m in el["members"] if m.get("role") == "outer" and m.get("geometry")]
            rings = stitch_rings(outers)
            if not rings:
                continue
            if t.get("building"):
                buildings.append({"rings": rings, "tags": t, "osm": f"relation/{el['id']}"})
            elif t.get("natural") == "water":
                water += [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [rnd(r)]}} for r in rings]

    for b in buildings:
        xs = [c[0] for c in b["rings"][0]]
        ys = [c[1] for c in b["rings"][0]]
        b["bb"], b["listed"] = (min(xs), min(ys), max(xs), max(ys)), []
    for x, y, p in listed:
        for b in buildings:
            bb = b["bb"]
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and any(point_in_ring(x, y, r) for r in b["rings"]):
                b["listed"].append(p)
                break

    qids = sorted({b["tags"]["wikidata"] for b in buildings if re.match(r"^Q\d+$", b["tags"].get("wikidata", ""))})
    nhle_ids = sorted({str(p["ListEntry"]) for b in buildings for p in b["listed"]})
    try:
        wd = wd_fetch(qids, nhle_ids)
    except Exception as e:  # noqa: BLE001 - Wikidata is optional
        print(f"Wikidata failed, continuing without it: {e}", file=sys.stderr)
        wd = {}

    rank = {"I": 3, "II*": 2}
    feats, known, by_source = [], 0, {"Wikidata": 0, "OpenStreetMap": 0}
    for b in buildings:
        t = b["tags"]
        best = sorted(b["listed"], key=lambda p: -rank.get(p.get("Grade"), 1))[0] if b["listed"] else None
        info = wd.get(t.get("wikidata", "")) or (best and wd.get(f"nhle:{best['ListEntry']}")) or None
        osm_y = parse_year(t.get("start_date") or t.get("building:start_date") or t.get("construction_date") or t.get("year_of_construction"))
        wd_y = wd_year(info)
        yr = src = None
        for cand, s in ((wd_y, "Wikidata"), (osm_y, "OpenStreetMap")):
            if cand and not cand[1] and not yr:
                yr, src = cand, s
        for cand, s in ((wd_y, "Wikidata"), (osm_y, "OpenStreetMap")):
            if cand and not yr:
                yr, src = cand, s
        if yr:
            known += 1
            by_source[src] += 1
        article = (info or {}).get("article")
        if not article and t.get("wikipedia", "").startswith("en:"):
            article = "https://en.wikipedia.org/wiki/" + t["wikipedia"][3:].replace(" ", "_")
        p = {
            "name": t.get("name") or (info or {}).get("label") or (best or {}).get("Name"),
            "y": yr[0] if yr else None, "ya": yr[1] if yr else False, "ysrc": src,
            "h": height_of(t), "osm": b["osm"], "kind": t.get("building"),
            "levels": t.get("building:levels"),
            "grade": (best or {}).get("Grade"), "listEntry": (best or {}).get("ListEntry"),
            "listName": (best or {}).get("Name"), "listUrl": (best or {}).get("hyperlink"),
            "qid": (info or {}).get("qid") or t.get("wikidata"), "image": (info or {}).get("image"),
            "article": article, "architect": (info or {}).get("architect") or t.get("architect"),
        }
        p = {k: v for k, v in p.items() if v not in (None, False, "")}
        rings = [rnd(r) for r in b["rings"]]
        geom = {"type": "Polygon", "coordinates": [rings[0]]} if len(rings) == 1 else {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}
        feats.append({"type": "Feature", "properties": p, "geometry": geom})

    fc = lambda f: {"type": "FeatureCollection", "features": f}  # noqa: E731
    listed_fc = [{"type": "Feature", "properties": {"g": p.get("Grade")}, "geometry": {"type": "Point", "coordinates": [round(x, 6), round(y, 6)]}} for x, y, p in listed]
    return {
        "city": city["id"], "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "stats": {"buildings": len(feats), "dated": known, "datedBySource": by_source, "listed": len(listed)},
        "buildings": fc(feats), "roads": fc(roads), "water": fc(water), "parks": fc(parks), "listed": fc(listed_fc),
    }


def main(cfg_path):
    city = json.loads(Path(cfg_path).read_text())
    osm = fetch_osm(city["bbox"])
    try:
        listed = fetch_listed(city["bbox"])
    except Exception as e:  # noqa: BLE001 - listed buildings are optional
        print(f"Historic England failed, continuing without it: {e}", file=sys.stderr)
        listed = []
    data = build(city, osm, listed)
    if not data["stats"]["buildings"]:
        raise SystemExit("No buildings returned; keeping the previous data file.")
    out = Path("data") / f"{city['id']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    s = data["stats"]
    print(f"Wrote {out}: {s['buildings']} buildings, {s['dated']} dated "
          f"({100 * s['dated'] / s['buildings']:.0f}%), {s['listed']} listed entries")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cities/nottingham.json")
