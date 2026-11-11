"""Layers for visitors: called by s06_layers.

  attractions   museums, galleries, attractions and viewpoints (OpenStreetMap): the building they are in, or a pin
  art           statues, sculpture, murals and memorials: pins, with Art UK's page where there is one
  boards        information boards about history and nature: pins
  routes        waymarked walking routes: lines, items r<index>
  basics        toilets, drinking water and benches: points drawn only close up, from the tiles

Each returns the layer's meta (as s06_layers.py describes) and fills the Collector with members, stories and pins.
A pin's extra fields (osm, kind, artist, start, oh, web, wd, wp, artuk, fee, wc) are what its card shows.
"""
import re

from .common import load, log, work
from .geo import building_at, metres
from .layerdata import grouped

OSM = ("OpenStreetMap", "https://www.openstreetmap.org/copyright")


def an(word):
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def year_of(s):
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", s or "")
    return m[1] if m else None


def kind_of(t):
    """What it is, in plain words: 'statue', 'war memorial', 'mural', 'museum'."""
    k = t.get("artwork_type") or (t.get("memorial") if t.get("historic") == "memorial" else None) \
        or (t.get("historic") if t.get("historic") in ("monument", "statue") else None) or t.get("tourism") or "artwork"
    k = k.replace("_", " ").lower()
    return {"artwork": "work of art", "attraction": "place to visit", "theme park": "theme park"}.get(k, k)


def extra(p):
    t = p["tags"]
    web = t.get("website") or t.get("contact:website") or t.get("url")
    e = {"osm": p["osm"], "kind": kind_of(t), "artist": t.get("artist_name") or t.get("artist"),
         "start": t.get("start_date"), "oh": t.get("opening_hours"), "web": web if web and web.startswith("http") else None,
         "wd": t.get("wikidata"), "wp": t.get("wikipedia"), "artuk": p.get("artuk"), "fee": t.get("fee") or t.get("charge"),
         "wc": t.get("wheelchair"), "op": t.get("operator")}
    return {k: v for k, v in e.items() if v}


def text_of(p):
    """A pin's words: its own description or inscription where OpenStreetMap has one, else what the tags say."""
    t, cat = p["tags"], p["cat"]
    desc = (t.get("description") or "").strip()
    ins = (t.get("inscription") or "").strip()
    if cat == "boards":
        about = {"boards-history": "the history of this place", "boards-nature": "the nature here"}.get(p["group"])
        base = desc or ("An information board" + (f" about {about}." if about else "."))
        return base + (f" It reads: “{ins[:280]}”" if ins and ins not in base else "")
    if desc:
        out = desc
    else:
        k = kind_of(t)
        subject = t.get("subject") or (t.get("name") if cat == "art" and not re.search(re.escape(k), t.get("name", ""), re.I) else None)
        who = t.get("artist_name") or t.get("artist")
        when = year_of(t.get("start_date"))
        op = t.get("operator") if cat == "attractions" else None
        out = (an(k)[0].upper() + an(k)[1:] + (f" of {subject}" if subject and cat == "art" else "")
               + (f" by {who}" if who else "") + (f", from {when}" if when else "") + (f", run by {op}" if op else "") + ".")
    if ins and ins not in out:
        out += f" Inscription: “{ins[:280]}{'…' if len(ins) > 280 else ''}”"
    return out


def name_of(p):
    t = p["tags"]
    return t.get("name") or (t.get("subject") and f"{kind_of(t).capitalize()} of {t['subject']}") or kind_of(t).capitalize()


GROUPS = {
    "attractions": [("visit-museums", "Museums and galleries"), ("visit-places", "Places to visit"), ("viewpoints", "Viewpoints")],
    "art": [("statues", "Statues"), ("sculpture", "Sculpture and other art"), ("murals", "Murals"), ("memorials", "Memorials")],
    "boards": [("boards-history", "About history"), ("boards-nature", "About nature"), ("boards-other", "Other boards")],
    "basics": [("toilets", "Toilets"), ("water", "Drinking water"), ("benches", "Benches")],
}


def visitor(city_id, ctx, out):
    if not work(city_id, "visitor").exists():
        return [], [], []
    v = load(city_id, "visitor")
    meta, items = [], {k: [] for L in GROUPS.values() for k, _ in L}
    for p in v["points"]:
        if p["cat"] == "basics":
            continue
        name = name_of(p)
        b = None
        if p["cat"] == "attractions" and p["group"] != "viewpoints":       # a museum is its building
            b = building_at(ctx.buildings, p["x"], p["y"])
        if b is not None:
            out.add(b, p["group"], p["cat"])
            items[p["group"]].append([b, ctx.buildings[b]["tags"].get("name") or name])
        else:
            ref = out.pin(p["x"], p["y"], name, p["cat"], p["group"], text_of(p), extra=extra(p))   # linked to OpenStreetMap
            items[p["group"]].append([ref, name])
    about = {
        "attractions": ("Attractions", "Museums, galleries, places to visit and viewpoints, as OpenStreetMap has them, "
                        "with opening hours where they are known. A museum or gallery is its building; the rest are pins."),
        "art": ("Statues and art", "Statues, sculpture, murals and memorials in the streets and parks, from OpenStreetMap, "
                "with Art UK's page for the ones it records. Plaques are in the People layer."),
        "boards": ("Information boards", "Boards in the street and in parks that tell the history or the nature of the place, "
                   "from OpenStreetMap. Maps, notices and timetables are left out."),
    }
    for cat, (title, intro) in about.items():
        groups = [{"key": k, "title": t, "count": len(items[k]),
                   "items": sorted(grouped(items[k]), key=lambda it: it[0].lower())} for k, t in GROUPS[cat]]
        meta.append({"id": cat, "title": title, "intro": intro, "section": "Visit",
                     "kind": "rule" if cat == "attractions" else "pins", "source": {"title": OSM[0], "url": OSM[1]},
                     "groups": [g for g in groups if g["count"]]})
        log(f"s06 {cat}: {sum(g['count'] for g in groups)} places")

    # walking routes: lines, and the routes' list
    routes = []
    for j, r in enumerate(v["routes"]):
        t = r["tags"]
        km = sum(metres(a, b) for ln in r["lines"] for a, b in zip(ln, ln[1:])) / 1000
        web = t.get("website") or t.get("url")
        routes.append({"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": r["lines"]},
                       "properties": {k: x for k, x in {"i": j, "name": r["name"], "ref": t.get("ref"), "network": t.get("network"),
                                                        "osm": r["osm"], "km": round(km, 1), "op": t.get("operator"),
                                                        "web": web if web and web.startswith("http") else None,
                                                        "wp": t.get("wikipedia"), "wd": t.get("wikidata"),
                                                        "text": t.get("description")}.items() if x}})
    if routes:
        meta.append({"id": "routes", "title": "Walking routes", "section": "Visit", "kind": "routes",
                     "intro": "Waymarked walking routes through the city, as OpenStreetMap has them. Most go on far "
                              "beyond the map; the distance given is the part on it.",
                     "source": {"title": OSM[0], "url": OSM[1]},
                     "groups": [{"key": "routes", "title": "Walking routes", "count": len(routes),
                                 "items": sorted([[f["properties"]["name"], [f"r{f['properties']['i']}"]] for f in routes],
                                                 key=lambda x: x[0].lower())}]})
    log(f"s06 walking routes: {len(routes)}")

    # basics: points in the tiles, drawn close up; not in the index
    basics = []
    for p in v["points"]:
        if p["cat"] != "basics":
            continue
        t = p["tags"]
        pr = {"t": p["group"], "name": t.get("name"), "oh": t.get("opening_hours"), "fee": t.get("fee") or t.get("charge"),
              "wc": t.get("wheelchair"), "ch": t.get("changing_table"), "acc": t.get("access"), "bk": t.get("backrest"),
              "osm": p["osm"]}
        basics.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["x"], p["y"]]},
                       "properties": {k: x for k, x in pr.items() if x}})
    if basics:
        meta.append({"id": "basics", "title": "Toilets, water and benches", "section": "Visit", "kind": "points",
                     "intro": "Public toilets, drinking water and benches, from OpenStreetMap. Shown when the map is "
                              "zoomed in to a few streets.",
                     "source": {"title": OSM[0], "url": OSM[1]},
                     "groups": [{"key": k, "title": t, "count": sum(1 for f in basics if f["properties"]["t"] == k)}
                                for k, t in GROUPS["basics"] if any(f["properties"]["t"] == k for f in basics)]})
    log(f"s06 basics: {len(basics)} points")
    return meta, routes, basics


