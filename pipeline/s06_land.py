"""The land's other shapes, sorted into the layers of the page's Layers sheet: brooks and springs, ponds, woods,
disused railways and lost canals (with the years they opened and closed, where known), historic sites, cemeteries,
allotments and orchards.

Reads work/<city>/land_osm.json (s00_fetch_land) and, for ponds, work/<city>/osm.json (s00_fetch_osm).

A railway's or canal's years come, in this order, from:
  stories/<city>/old-lines.md   a hand-checked table: Name in OpenStreetMap | Opened | Closed | Source | Note
  Wikidata                      the line the map's wikidata tag names: opened (P1619, P729, P571) and closed
                                (P3999, P730, P576)
  OpenStreetMap                 the start_date and end_date tags (opening_date, closing_date…)
A line's parts that share a name share its years (the earliest opening, the latest closing found).

Writes work/<city>/land.json:
  features  GeoJSON, properties {t: kind, i?: its entry, k?: what sort (an earthwork, a ditch), u?: 1 when a brook
            runs underground (culverted), y0?, y1?: the years a railway or canal opened and closed, o: its
            OpenStreetMap id}
  entries   one per named place (a line's parts together): {t, name, k?, from?, to?, dsrc?, wd?, wp?, osm, km?, bb}
  meta      the layers, as s06_layers's meta (kind "land", items l<entry>)
"""
import math
import re
from pathlib import Path

from .common import city, load, log, parse_year, save, work
from .s00_fetch_osm import in_area
from .stories_md import table
from .web import http

KINDS = {      # key: (group title, singular, layer)
    "brook": ("Brooks and streams", "Brook or stream", "water"),
    "pond": ("Ponds", "Pond", "water"),
    "wood": ("Woods", "Wood", "woods"),
    "rail": ("Disused railways", "Disused railway", "oldlines"),
    "canal": ("Lost canals", "Lost canal", "oldlines"),
    "oldsite": ("Historic sites", "Historic site", "oldsites"),
    "cemetery": ("Cemeteries and churchyards", "Cemetery", "greens"),
    "allot": ("Allotments", "Allotments", "greens"),
    "orchard": ("Orchards", "Orchard", "greens"),
}
LAYERS = [
    {"id": "water-land", "title": "Brooks, streams and ponds", "section": "Nature", "groups": ["brook", "pond"],
     "intro": "The smaller water: brooks, streams, ditches and springs, and ponds, as OpenStreetMap's mappers have "
              "drawn them. Where a brook runs underground, in a culvert, its line is dotted."},
    {"id": "woods", "title": "Woods", "section": "Nature", "groups": ["wood"],
     "intro": "Woods and plantations as OpenStreetMap records them today. Ancient woodland, wooded since at least "
              "1600, is in the Nature layer, from Natural England."},
    {"id": "oldlines", "title": "Old railways and canals", "section": "Heritage", "groups": ["rail", "canal"],
     "intro": "Railways whose trains have gone and canals no longer used or filled in, many now footpaths and cycle "
              "tracks. Each is drawn from the year it opened; solid while it was in use, dashed once it closed. "
              "Their years come from a hand-checked list, Wikidata or OpenStreetMap, as each card says."},
    {"id": "oldsites", "title": "Historic sites", "section": "Heritage", "groups": ["oldsite"],
     "intro": "What OpenStreetMap's mappers have marked as historic on the ground: archaeological sites, earthworks "
              "and moats, ruins, the castle, old walls, wells, boundary stones and milestones, mills and caves. "
              "Scheduled monuments, protected by law, are a layer of their own."},
    {"id": "greens", "title": "Cemeteries, allotments and orchards", "section": "Nature",
     "groups": ["cemetery", "allot", "orchard"],
     "intro": "Cemeteries and churchyards, allotment gardens and orchards, from OpenStreetMap."},
]
AREA_KINDS = {"wood", "pond", "cemetery", "allot", "orchard", "oldsite"}
LINEAR_SITES = {"city_walls", "citywalls", "milestone", "boundary_stone"}
NOT_LINES = {"station", "platform", "halt", "signal_box", "turntable", "buffer_stop", "level_crossing"}
HISTORIC_KIND = {"archaeological_site": "Archaeological site", "city_walls": "Town walls", "citywalls": "Town walls",
                 "castle": "Castle", "ruins": "Ruins", "earthworks": "Earthworks", "moat": "Moat", "fort": "Fort",
                 "tumulus": "Burial mound", "boundary_stone": "Boundary stone", "well": "Well", "holy_well": "Holy well",
                 "milestone": "Milestone", "mine": "Mine", "mine_shaft": "Mine shaft", "quarry": "Old quarry",
                 "mill": "Mill", "wayside_cross": "Wayside cross", "cave": "Cave", "cave_entrance": "Cave entrance",
                 "ice_house": "Ice house", "dovecote": "Dovecote", "bridge_site": "Site of a bridge",
                 "industrial": "Industrial remains", "kiln": "Kiln", "lime_kiln": "Lime kiln", "pinfold": "Pinfold"}
BROOK_KIND = {"stream": "Stream", "brook": "Brook", "ditch": "Ditch", "drain": "Drain", "weir": "Weir",
              "spring": "Spring"}
WDQS = "https://query.wikidata.org/sparql"
OPENED, CLOSED = ("P1619", "P729", "P571"), ("P3999", "P730", "P576")


def kind(t):
    """The layer group an element belongs to, or None."""
    if t.get("historic") in HISTORIC_KIND or t.get("natural") == "cave_entrance":
        if t.get("historic") not in ("railway", "canal"):
            return "oldsite"
    if t.get("railway") in ("abandoned", "disused", "dismantled", "razed") or t.get("historic") == "railway" \
            or any(t.get(k) for k in ("abandoned:railway", "disused:railway", "razed:railway")):
        if t.get("railway") in ("rail", "light_rail", "tram", "subway", "narrow_gauge"):
            return None                      # still in use (a disused siding drawn on a working line's way)
        if any(t.get(k) in NOT_LINES for k in ("railway", "abandoned:railway", "disused:railway", "razed:railway")):
            return None
        return "rail"
    if t.get("abandoned:waterway") or t.get("disused:waterway") or t.get("waterway") == "derelict_canal" \
            or t.get("historic") == "canal" or (t.get("waterway") == "canal" and "yes" in (t.get("disused"), t.get("abandoned"))):
        return "canal"
    if t.get("waterway") in BROOK_KIND or t.get("natural") == "spring":
        return "brook"
    if t.get("natural") == "water" and t.get("water") == "pond":
        return "pond"
    if t.get("natural") == "wood" or t.get("landuse") == "forest":
        return "wood"
    if t.get("landuse") == "cemetery" or t.get("amenity") == "grave_yard":
        return "cemetery"
    if t.get("landuse") == "allotments":
        return "allot"
    if t.get("landuse") == "orchard":
        return "orchard"
    return None


def rnd(pts):
    return [[round(p["lon"], 5), round(p["lat"], 5)] for p in pts if p]


def join(parts):
    """Ways (point lists) joined end to end into closed rings, as a multipolygon's outer members are."""
    parts = [p[:] for p in parts if len(p) > 1]
    rings = []
    while parts:
        ring = parts.pop(0)
        grew = True
        while ring[0] != ring[-1] and grew:
            grew = False
            for k, p in enumerate(parts):
                if p[0] == ring[-1]:
                    ring += p[1:]
                elif p[-1] == ring[-1]:
                    ring += p[::-1][1:]
                elif p[-1] == ring[0]:
                    ring = p[:-1] + ring
                elif p[0] == ring[0]:
                    ring = p[::-1][:-1] + ring
                else:
                    continue
                parts.pop(k)
                grew = True
                break
        if ring[0] == ring[-1] and len(ring) > 3:
            rings.append(ring)
    return rings


def geometry(el, t, k):
    if el["type"] == "node":
        return {"type": "Point", "coordinates": [round(el["lon"], 5), round(el["lat"], 5)]}
    if el["type"] == "way":
        pts = rnd(el.get("geometry") or [])
        if len(pts) < 2:
            return None
        closed = pts[0] == pts[-1] and len(pts) > 3
        area = k in AREA_KINDS and closed and t.get("area") != "no" and t.get("historic") not in LINEAR_SITES
        if k in ("rail", "canal", "brook") and closed and t.get("area") == "yes":
            return None                      # a station's or a basin's outline, not a line
        return {"type": "Polygon", "coordinates": [pts]} if area else {"type": "LineString", "coordinates": pts}
    rings = join([rnd(m.get("geometry") or []) for m in el.get("members", []) if m.get("role") in ("outer", "")
                  and m.get("type") == "way"])
    return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]} if rings else None


def pts_of(g):
    c = g["coordinates"]
    return [c] if g["type"] == "Point" else c if g["type"] == "LineString" else c[0] if g["type"] == "Polygon" \
        else [p for poly in c for p in poly[0]]


def km(g):
    if g["type"] != "LineString":
        return 0
    c, d = g["coordinates"], 0.0
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        dx = math.radians(x2 - x1) * math.cos(math.radians((y1 + y2) / 2))
        d += 6371 * math.hypot(dx, math.radians(y2 - y1))
    return d


def name_of(t, k):
    for key in ("name", "old_name", "abandoned:name", "disused:name", "historic:name"):
        if t.get(key):
            return t[key]
    if k == "rail" and t.get("old_railway_operator"):
        return f"Former {t['old_railway_operator']} line"
    return None


def year(t, keys):
    for key in keys:
        y = parse_year(t.get(key))
        if y:
            return y[0]
    return None


def wikidata_years(ids):
    """{Q-id: (opened, closed)} from Wikidata."""
    out = {}
    ids = sorted(ids)
    for n in range(0, len(ids), 100):
        vals = " ".join("wd:" + q for q in ids[n:n + 100])
        props = " ".join(f"wdt:{p}" for p in OPENED + CLOSED)
        q = f"""SELECT ?item ?p (YEAR(?d) AS ?y) WHERE {{ VALUES ?item {{ {vals} }} VALUES ?p {{ {props} }}
                ?item ?p ?d . }}"""
        try:
            rows = http(WDQS, {"query": q, "format": "json"}, accept="application/sparql-results+json")["results"]["bindings"]
        except Exception as e:  # noqa: BLE001 - the years are optional
            log(f"    Wikidata years failed: {e}")
            continue
        got = {}
        for r in rows:
            qid, p = r["item"]["value"].rsplit("/", 1)[1], r["p"]["value"].rsplit("/", 1)[1]
            if r.get("y", {}).get("value"):
                got.setdefault(qid, {}).setdefault(p, []).append(int(r["y"]["value"]))
        for qid, ps in got.items():
            first = next((min(ps[p]) for p in OPENED if p in ps), None)
            last = next((max(ps[p]) for p in CLOSED if p in ps), None)
            out[qid] = (first, last)
    return out


def checked_years(city_id):
    """{name in OpenStreetMap: (opened, closed, source)} from stories/<city>/old-lines.md."""
    f = Path("stories") / city_id / "old-lines.md"
    out = {}
    for r in (table(f) if f.exists() else []):
        y = lambda v: int(m[1]) if (m := re.search(r"(\d{4})", v or "")) else None  # noqa: E731
        out[r["name in openstreetmap"]] = (y(r.get("opened")), y(r.get("closed")), r.get("source") or "")
    return out


def main(city_id):
    poly = city(city_id).get("polygon")
    els = load(city_id, "land_osm")["elements"] if work(city_id, "land_osm").exists() else []
    if work(city_id, "osm").exists():          # ponds: in the main download
        els += [e for e in load(city_id, "osm")["elements"] if kind(e.get("tags", {})) == "pond"]
    feats, seen = [], set()
    for el in els:
        t = el.get("tags", {})
        k = kind(t)
        if not k or (el["type"], el["id"]) in seen or not in_area(el, poly):
            continue
        g = geometry(el, t, k)
        if not g:
            continue
        seen.add((el["type"], el["id"]))
        p = {"t": k, "o": f"{el['type']}/{el['id']}"}
        sub = HISTORIC_KIND.get(t.get("historic")) or HISTORIC_KIND.get(t.get("natural")) if k == "oldsite" \
            else BROOK_KIND.get(t.get("waterway") or t.get("natural")) if k == "brook" else None
        if sub:
            p["k"] = sub
        if k == "brook" and (t.get("tunnel") in ("culvert", "yes") or t.get("location") == "underground"):
            p["u"] = 1
        feats.append({"type": "Feature", "geometry": g, "properties": p, "_tags": t})

    # named places: one entry for all the parts that share a kind and a name
    entries, by = [], {}
    for f in feats:
        t, p = f["_tags"], f["properties"]
        name = name_of(t, p["t"])
        if not name:
            continue
        key = (p["t"], name)
        if key not in by:
            by[key] = len(entries)
            entries.append({"t": p["t"], "name": name, "osm": p["o"], "_parts": []})
        e = entries[by[key]]
        e["_parts"].append(f)
        p["i"] = by[key]
        for src, dst in (("wikidata", "wd"), ("wikipedia", "wp")):
            if t.get(src) and dst not in e:
                e[dst] = t[src]
        if p.get("k") and "k" not in e:
            e["k"] = p["k"]
        if t.get("start_date") and "date" not in e and p["t"] not in ("rail", "canal"):
            e["date"] = t["start_date"]

    # a line's years: the hand-checked table, Wikidata, OpenStreetMap
    checked = checked_years(city_id)
    wd = wikidata_years({e["wd"] for e in entries if e["t"] in ("rail", "canal") and re.fullmatch(r"Q\d+", e.get("wd", ""))})
    for e in entries:
        if e["t"] not in ("rail", "canal"):
            continue
        tags = [f["_tags"] for f in e["_parts"]]
        osm = ([y for t in tags if (y := year(t, ("start_date", "opening_date", "railway:start_date")))],
               [y for t in tags if (y := year(t, ("end_date", "closing_date", "disused:start_date", "abandoned:start_date")))])
        for first, last, src in (checked.get(e["name"], (None, None, None)) + (),
                                 wd.get(e.get("wd"), (None, None)) + ("Wikidata",),
                                 (min(osm[0]) if osm[0] else None, max(osm[1]) if osm[1] else None, "OpenStreetMap")):
            if first and "from" not in e:
                e["from"], e["fromSrc"] = first, src
            if last and "to" not in e:
                e["to"], e["toSrc"] = last, src
        for f in e["_parts"]:
            if e.get("from"):
                f["properties"]["y0"] = e["from"]
            if e.get("to"):
                f["properties"]["y1"] = e["to"]

    for e in entries:
        pts = [pt for f in e["_parts"] for pt in pts_of(f["geometry"])]
        xs, ys = [pt[0] for pt in pts], [pt[1] for pt in pts]
        e["bb"] = [min(xs), min(ys), max(xs), max(ys)]
        length = sum(km(f["geometry"]) for f in e["_parts"])
        if length >= 0.1:
            e["km"] = round(length, 1)
        del e["_parts"]
    for f in feats:
        del f["_tags"]

    meta = []
    for L in LAYERS:
        groups = []
        for g in L["groups"]:
            items = sorted([[e["name"], [f"l{j}"]] for j, e in enumerate(entries) if e["t"] == g], key=lambda x: x[0].lower())
            groups.append({"key": g, "title": KINDS[g][0], "count": sum(1 for f in feats if f["properties"]["t"] == g),
                           **({"items": items} if items and len(items) <= 400 else {})})
        meta.append({"id": L["id"], "title": L["title"], "section": L["section"], "kind": "land", "intro": L["intro"],
                     "source": {"title": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright"},
                     "groups": groups})
        log(f"s06 {L['title'].lower()}: " + ", ".join(f"{g['count']} {g['title'].lower()}" for g in groups))
    dated = [e for e in entries if e["t"] in ("rail", "canal")]
    log(f"    old lines: {len(dated)} named, {sum(1 for e in dated if e.get('from') or e.get('to'))} with years; "
        + "; ".join(f"{e['name']} {e.get('from', '?')}–{e.get('to', '?')}" for e in dated[:40]))
    save(city_id, "land", {"features": feats, "entries": entries, "meta": meta})
