"""Download what a visitor looks for from OpenStreetMap: attractions, statues and public art, information boards,
waymarked walking routes and visitor basics (toilets, drinking water, benches); and Art UK's pages for the art.

The main OpenStreetMap download (s00_fetch_osm) takes most of an hour and is kept between builds, so these come in
a small download of their own: a few thousand points and a few route lines, in one request each.

  points  attractions (tourism=attraction, museum, gallery, viewpoint, zoo, theme_park); art (tourism=artwork,
          historic=memorial except plaques, historic=monument, historic=statue); information boards
          (tourism=information + information=board); basics (amenity=toilets, drinking_water, bench).
          Ways and relations come as their centre.
  routes  route=hiking, foot or walking relations: walking routes with a name, clipped to the city's box.
  artuk   Art UK artwork pages for the art, from Wikidata (P1679, Art UK artwork ID): by the item OpenStreetMap
          names (wikidata=Q…), or an item with an Art UK page standing within 40 m with a similar name.

Writes work/<city>/visitor.json: {points: [{x, y, osm, cat, group, tags}], routes: [{osm, name, tags, lines}]}.
Licence: ODbL, © OpenStreetMap contributors; Wikidata CC0.
"""
import re

from .common import city, log, save
from .geo import metres
from .s00_fetch_osm import OVERPASS
from .web import http

WDQS = "https://query.wikidata.org/sparql"
# the tags a card uses; the rest are dropped
KEEP = ("name", "tourism", "historic", "amenity", "memorial", "artwork_type", "board_type", "artist_name", "artist",
        "subject", "inscription", "description", "start_date", "opening_hours", "website", "contact:website", "url",
        "wikidata", "wikipedia", "subject:wikidata", "fee", "charge", "wheelchair", "operator", "material",
        "changing_table", "unisex", "access", "backrest", "ref", "network", "distance", "symbol", "osmc:symbol",
        "colour")
NOT_ART = {"plaque", "blue_plaque", "stolperstein", "bench", "ghost_bike", "tree", "grave"}


def classify(t):
    """(category, group) for a point's tags, or None. Categories are the page's layers; groups its tickboxes."""
    tour, hist, am = t.get("tourism"), t.get("historic"), t.get("amenity")
    if tour in ("museum", "gallery"):
        return "attractions", "museums"
    if tour in ("attraction", "zoo", "theme_park"):
        return "attractions", "attractions"
    if tour == "viewpoint":
        return "attractions", "viewpoints"
    if tour == "artwork" or hist == "statue":
        kind = (t.get("artwork_type") or ("statue" if hist == "statue" else "")).lower()
        if kind in ("statue", "bust"):
            return "art", "statues"
        if kind in ("mural", "graffiti", "painting", "mosaic"):
            return "art", "murals"
        return "art", "sculpture"
    if hist == "memorial" and t.get("memorial", "").lower() not in NOT_ART:
        return "art", "statues" if t.get("memorial") in ("statue", "bust") else "memorials"
    if hist == "monument":
        return "art", "memorials"
    if tour == "information" and t.get("information") == "board":
        bt = (t.get("board_type") or "").lower()
        if re.search(r"histor|heritage", bt):
            return "boards", "boards-history"
        if re.search(r"nature|wildlife|plant|geolog|tree", bt):
            return "boards", "boards-nature"
        if t.get("name") and bt in ("", "board", "tourism", "general"):
            return "boards", "boards-other"
        return None                  # maps, notices and timetables
    if am in ("toilets", "drinking_water", "bench"):
        return "basics", {"toilets": "toilets", "drinking_water": "water", "bench": "benches"}[am]
    return None


def overpass(q):
    last = None
    for url in OVERPASS:
        try:
            return http(url, {"data": q}, tries=2, timeout=240)["elements"]
        except Exception as e:  # noqa: BLE001 - try the next server
            last = e
            log(f"    {url.split('/')[2]}: {e}")
    raise RuntimeError(f"All Overpass servers failed: {last}")


def points(c):
    poly = ('(poly:"' + " ".join(f"{y} {x}" for x, y in c["polygon"]) + '")') if c.get("polygon") else ""
    b = c["bbox"]
    area = poly + f"({b['s']},{b['w']},{b['n']},{b['e']})"
    q = f"""[out:json][timeout:200];(
      nwr["tourism"~"^(attraction|museum|gallery|viewpoint|zoo|theme_park|artwork)$"]{area};
      nwr["historic"~"^(memorial|monument|statue)$"]{area};
      node["tourism"="information"]["information"="board"]{area};
      node["amenity"~"^(toilets|drinking_water|bench)$"]{area};
    ); out center tags qt;"""
    out = []
    for el in overpass(q):
        t = el.get("tags", {})
        x, y = (el["lon"], el["lat"]) if "lon" in el else (el.get("center", {}).get("lon"), el.get("center", {}).get("lat"))
        cg = classify(t)
        if x is None or not cg:
            continue
        out.append({"x": round(x, 6), "y": round(y, 6), "osm": f"{el['type']}/{el['id']}", "cat": cg[0], "group": cg[1],
                    "tags": {k: v for k, v in t.items() if k in KEEP}})
    return out


def routes(c):
    b = c["bbox"]
    box = f"({b['s']},{b['w']},{b['n']},{b['e']})"
    q = f"""[out:json][timeout:200];relation["route"~"^(hiking|foot|walking)$"]["name"]{box};out tags geom{box};"""
    out = []
    for el in overpass(q):
        lines = [[[round(p["lon"], 5), round(p["lat"], 5)] for p in m["geometry"] if p]
                 for m in el.get("members", []) if m.get("type") == "way" and m.get("geometry")]
        lines = [ln for ln in lines if len(ln) > 1]
        if lines:
            t = el.get("tags", {})
            out.append({"osm": f"relation/{el['id']}", "name": t["name"], "tags": {k: v for k, v in t.items() if k in KEEP},
                        "lines": lines})
    return out


def words(s):
    return {w for w in re.findall(r"[a-z]{4,}", (s or "").lower()) if w not in ("statue", "memorial", "sculpture", "nottingham")}


def art_uk(c, pts):
    """{osm id: Art UK artwork id} for the art."""
    art = [p for p in pts if p["cat"] == "art"]
    found = {}
    qids = sorted({p["tags"]["wikidata"] for p in art if re.fullmatch(r"Q\d+", p["tags"].get("wikidata", ""))})
    by_qid = {}
    for i in range(0, len(qids), 200):
        vals = " ".join(f"wd:{q}" for q in qids[i:i + 200])
        try:
            rows = http(WDQS, {"query": f"SELECT ?item ?artuk WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P1679 ?artuk }}",
                               "format": "json"}, accept="application/sparql-results+json")["results"]["bindings"]
        except Exception as e:  # noqa: BLE001 - optional: the art is shown without the links
            log(f"s00 Art UK (by item): {e}")
            rows = []
        for r in rows:
            by_qid[r["item"]["value"].rsplit("/", 1)[1]] = r["artuk"]["value"]
    b = c["bbox"]
    try:
        near = http(WDQS, {"query": f"""SELECT ?item ?artuk ?label ?coord WHERE {{
              SERVICE wikibase:box {{ ?item wdt:P625 ?coord .
                bd:serviceParam wikibase:cornerSouthWest "Point({b['w']} {b['s']})"^^geo:wktLiteral .
                bd:serviceParam wikibase:cornerNorthEast "Point({b['e']} {b['n']})"^^geo:wktLiteral . }}
              ?item wdt:P1679 ?artuk . ?item rdfs:label ?label . FILTER(LANG(?label) = "en") }}""", "format": "json"},
            accept="application/sparql-results+json")["results"]["bindings"]
    except Exception as e:  # noqa: BLE001
        log(f"s00 Art UK (nearby): {e}")
        near = []
    places = []
    for r in near:
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", r["coord"]["value"])
        if m:
            places.append((float(m[1]), float(m[2]), r["label"]["value"], r["artuk"]["value"]))
    for p in art:
        q = p["tags"].get("wikidata")
        if q in by_qid:
            found[p["osm"]] = by_qid[q]
            continue
        mine = words(p["tags"].get("name")) | words(p["tags"].get("subject")) | words(p["tags"].get("inscription"))
        best = None
        for x, y, label, aid in places:
            d = metres([p["x"], p["y"]], [x, y])
            if d <= 40 and mine & words(label) and (best is None or d < best[0]):
                best = (d, aid)
        if best:
            found[p["osm"]] = best[1]
    log(f"s00 Art UK: {len(found)} of {len(art)} artworks and memorials have an Art UK page "
        f"({len(by_qid)} by their Wikidata item, {len(places)} Art UK items in the area)")
    return found


def main(city_id):
    c = city(city_id)
    pts = points(c)
    for osm, aid in art_uk(c, pts).items():
        next(p for p in pts if p["osm"] == osm)["artuk"] = aid
    rs = routes(c)
    by = {}
    for p in pts:
        by[p["group"]] = by.get(p["group"], 0) + 1
    log(f"s00 visitor points: {len(pts)} ({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}); "
        f"{len(rs)} walking routes: {', '.join(r['name'] for r in rs)}")
    save(city_id, "visitor", {"points": pts, "routes": rs})
