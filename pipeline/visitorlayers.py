"""Layers for visitors, and the layers that come from lists rather than rules: called by s06_layers.

  attractions   museums, galleries, attractions and viewpoints (OpenStreetMap): the building they are in, or a pin
  art           statues, sculpture, murals and memorials: pins, with Art UK's page where there is one
  boards        information boards about history and nature: pins
  routes        waymarked walking routes: lines, items r<index>
  basics        toilets, drinking water and benches: points drawn only close up, from the tiles
  museums       Mapping Museums: museums open now and closed since, on their building or as a pin
  pubheritage   CAMRA's historic pub interiors (stories/<city>/pub-heritage.md): the pub's building

Each returns the layer's meta (as s06_layers.py describes) and fills the Collector with members, stories and pins.
A pin's extra fields (osm, kind, artist, start, oh, web, wd, wp, artuk, fee, wc) are what its card shows.
"""
import re
from pathlib import Path

from .common import load, log, work
from .geo import building_at, metres
from .layerdata import grouped
from .s00_fetch_museums import DATASET
from .stories_md import table

OSM = ("OpenStreetMap", "https://www.openstreetmap.org/copyright")
MMSOURCE = {"kind": "Mapping Museums", "title": "Mapping Museums Data, Birkbeck, University of London (CC BY 4.0)", "url": DATASET}


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


# a person's name alone, "Brian Clough" or "Jesse Boot": two to four capitalised words, nothing like "of"
PERSON_NAME = re.compile(r"(?:Sir |Dame |Lord |Lady )?[A-Z][\w'.-]+(?: [A-Z][\w'.-]+){1,3}")


def name_of(p):
    """A pin's title. A statue or bust named with only the person it shows is "Statue of Brian Clough": the pin is
    a work of art in a place, not the person."""
    t = p["tags"]
    name, k = t.get("name"), kind_of(t)
    if name and p.get("cat") == "art" and k in ("statue", "bust") \
            and PERSON_NAME.fullmatch(name) and (t.get("subject") in (None, name)):
        return f"{k.capitalize()} of {name}"
    return name or (t.get("subject") and f"{k.capitalize()} of {t['subject']}") or k.capitalize()


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
                                                        "text": t.get("description")}.items() if x not in (None, "")}})
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


def museums(city_id, ctx, out):
    """Mapping Museums: each museum's building, or a pin where its address stands on none."""
    if not work(city_id, "museums").exists() or not load(city_id, "museums"):
        return []
    items = {"mm-open": [], "mm-closed": []}
    for m in load(city_id, "museums"):
        g = "mm-closed" if m["closed"] else "mm-open"
        when = lambda y: f"in {y}" if y and not y.startswith("between") else (y or "")  # noqa: E731
        text = (f"{m['name']} opened {when(m['opened'])}".rstrip() + (f" and closed {when(m['closed'])}" if m["closed"] else "")
                + "." + (f" Subject: {m['subject'].lower()}." if m.get("subject") else ""))
        b = building_at(ctx.buildings, m["x"], m["y"], near=15)
        if b is not None:
            out.add(b, g, "museums", text, MMSOURCE)
            items[g].append([b, m["name"]])
        else:
            ref = out.pin(m["x"], m["y"], m["name"], "museums", g, text, MMSOURCE,
                          extra={k: x for k, x in {"kind": "museum", "gov": m.get("governance"),
                                                   "acc": m.get("accreditation")}.items() if x})
            items[g].append([ref, m["name"]])
    log(f"s06 museums (Mapping Museums): {len(items['mm-open'])} open, {len(items['mm-closed'])} closed")
    return [{"id": "museums", "title": "Museums, past and present", "section": "Visit", "kind": "rule",
             "intro": "Every museum open in the city at some time since 1960, with the years it opened and closed: the "
                      "big ones and the small ones, and those that have gone. From Mapping Museums, a research project at "
                      "Birkbeck, University of London; its data runs to 2021. A museum stands on its building, or is a pin "
                      "at its address.",
             "source": {"title": "Mapping Museums (Birkbeck, CC BY 4.0)", "url": DATASET},
             "groups": [{"key": k, "title": t, "count": len(items[k]),
                         "items": sorted(grouped(items[k]), key=lambda it: it[0].lower())}
                        for k, t in (("mm-open", "Open"), ("mm-closed", "Closed since")) if items[k]]}]


def norm(s):
    s = re.sub(r"\b(the|ye|inn|hotel|pub|tavern|and|&)\b", " ", (s or "").lower().replace("’", "'"))
    return " ".join(re.findall(r"[a-z0-9]+", s))


RATING = {"national": ("camra-national", "Of national importance"),
          "regional": ("camra-regional", "Of regional importance"),
          "some": ("camra-some", "Of some regional importance")}


def the(name):
    return name if re.match(r"(the|ye)\b", name, re.I) else "the " + name


def pub_heritage(city_id, ctx, out):
    f = Path("stories") / city_id / "pub-heritage.md"
    if not f.exists():
        return []
    pubs = [(i, t) for i, b in enumerate(ctx.buildings) if (t := b["tags"]).get("amenity") in ("pub", "bar") and t.get("name")]
    pubs += [(p["b"], p["tags"]) for p in ctx.places if p["b"] is not None and p["tags"].get("amenity") in ("pub", "bar")]
    items, missed = {k: [] for k, _ in RATING.values()}, []
    for r in table(f):
        key, title = RATING[r["rating"].strip().lower()]
        want = norm(r["pub"])
        cands = [(i, t) for i, t in pubs if norm(t.get("name")) == want]
        pc = r.get("postcode", "").replace(" ", "").upper()
        street = norm(r.get("street", "").split(",")[0])
        exact = [(i, t) for i, t in cands if (t.get("addr:postcode", "").replace(" ", "").upper() == pc)
                 or (street and norm(t.get("addr:street")) == street)]
        hit = exact or (cands if len({i for i, _ in cands}) == 1 else [])
        if not hit:
            missed.append(r["pub"])
            continue
        i = hit[0][0]
        text = (f"CAMRA, the Campaign for Real Ale, rates the interior of {the(r['pub'])} as {title.lower()} in its "
                "inventory of historic pub interiors, which records the old bars, snugs and fittings that survive. The "
                "rating gives the interior no legal protection.")
        out.add(i, key, "pubheritage", text, {"kind": "CAMRA", "title": f"{r['pub']}: historic pub interior", "url": r["url"]})
        items[key].append([i, r["pub"]])
    log(f"s06 historic pub interiors (CAMRA): {sum(len(v) for v in items.values())} matched"
        + (f"; not on the map or not matched: {', '.join(missed)}" if missed else ""))
    return [{"id": "pubheritage", "title": "Historic pub interiors", "section": "Heritage", "kind": "rule",
             "intro": "Pubs whose interiors CAMRA, the Campaign for Real Ale, lists as historically important: old bars, "
                      "snugs, tiling and fittings that survive. The ratings and links are CAMRA's; the list gives no legal "
                      "protection.",
             "source": {"title": "Nottingham CAMRA, heritage interiors", "url": "https://nottingham.camra.org.uk/heritage/camra-heritage-interiors/"},
             "groups": [{"key": k, "title": t, "count": len(items[k]), "items": grouped(items[k])}
                        for k, t in RATING.values() if items[k]]}]
