"""What the page loads: vector tiles for the map, a small index of every building, and card files.

The page used to load one file with every building's outline and every detail (18 MB, 2.4 MB compressed)
and build the whole city before showing anything. Now:
  data/<city>/tiles/{z}/{x}/{y}.pbf   Mapbox Vector Tiles (gzipped), made by tippecanoe, zoom 10 to 15
                                      (the map draws closer zooms from the zoom 15 tiles). Layers:
                                      b (buildings: id = building index; y, f, h, base, L for colour, filters and
                                      height), roads (k), water, parks. The phone loads only the tiles on screen,
                                      with simpler outlines when zoomed out.
                                      Also areas (nature and conservation areas…, t = which kind, i = its number),
                                      routes (walking routes: i, name) and basics (toilets, water, benches: t and
                                      a few details, in the zoom 14 and 15 tiles only, drawn close up), and land
                                      (brooks, woods, old railways and canals… from s06_land: t, i, k, u, y0, y1, o).
  data/<city>.json                    the index: only what the page needs before any card opens: the few buildings
                                      with a name, layers or a listing (see index()), how many buildings stand by
                                      each year (for the count under the slider), layers, pins, and the areas'
                                      names and bounds. Small however big the map gets: no outlines, no centres.
  data/<city>/osm/<n>.json            OpenStreetMap id -> building number, for links that name one (?osm=way/123),
                                      in OSM_PARTS files by the id's number (n = number % OSM_PARTS), so a link
                                      loads a few kilobytes, not the list of every building.
  data/<city>/cards/<n>.json          everything else about a building (its centre, year, summary, photos, stories,
                                      sources, height…), CHUNK buildings per file (a few kilobytes gzipped), loaded when
                                      a card opens.
                                      Buildings are numbered in map order (s01), so one file is one part of town.
tippecanoe (github.com/felt/tippecanoe, BSD) must be on the PATH, or named by $TIPPECANOE. Without it this step
writes the old single file instead, which the page can still read.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

from .common import load, log
from .geo import centroid

CHUNK = 250
OSM_PARTS = 64
MIN_Z, MAX_Z = 10, 15         # zoomed out (10-11) the smallest buildings are left out so tiles stay small
TILE_PROPS = ("y", "f", "h", "base", "L")
# what the index keeps, for the few buildings that have them; everything else goes to the card files
SPARSE = ("name", "listName", "L", "stories", "grade")
AREA_PROPS = ("t", "name")          # in the tiles; the rest of an area's details are in the index
TILE_ONLY = ("tpo",)                # many small areas, all alike: only in the tiles (the card takes the rest from the layer)


def tippecanoe():
    exe = os.environ.get("TIPPECANOE") or shutil.which("tippecanoe")
    return exe if exe and Path(exe).exists() else None


def write_fc(path, feats):
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))


def index(props):
    """The few buildings with a name, layers, stories or a listing (each story as brief() keeps it), and how many
    buildings have each year, so the page can count the buildings standing by any year without a list of every
    building: {"hist": [[year, buildings], ...], "undated": n, "estimated": n}."""
    years = Counter(p["y"] for p in props if p.get("y") is not None)
    return {"n": len(props),
            "hist": sorted(years.items()), "undated": sum(1 for p in props if p.get("y") is None),
            "estimated": sum(1 for p in props if p.get("f") == "area"),
            "props": {str(i): s for i, p in enumerate(props) if (s := {k: brief(p[k]) if k == "stories" else p[k]
                                                                        for k in SPARSE if k in p})}}


def bounds(g):
    pts = [c for ring in (g["coordinates"] if g["type"] == "Polygon" else [r for poly in g["coordinates"] for r in poly])
           for c in ring]
    xs, ys = [c[0] for c in pts], [c[1] for c in pts]
    return [round(min(xs), 5), round(min(ys), 5), round(max(xs), 5), round(max(ys), 5)]


def bounds_lines(g):
    pts = [c for ln in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]) for c in ln]
    xs, ys = [c[0] for c in pts], [c[1] for c in pts]
    return [round(min(xs), 5), round(min(ys), 5), round(max(xs), 5), round(max(ys), 5)]


def brief(stories):
    """A building's stories as the index keeps them: the layer, the person, the plaque, not the words."""
    return [{k: st[k] for k in ("layer", "who", "pin") if k in st} for st in stories]


def main(city_id):
    pkg = load(city_id, "package")
    out_json = Path(f"data/{city_id}.json")
    exe = tippecanoe()
    if not exe:
        log("s10 tiles: tippecanoe not found, writing the single data file instead")
        out_json.write_text(json.dumps(pkg, separators=(",", ":"), ensure_ascii=False))
        return
    feats = pkg["buildings"]["features"]
    root = Path("data") / city_id
    shutil.rmtree(root, ignore_errors=True)
    (root / "cards").mkdir(parents=True)
    (root / "osm").mkdir()

    tmp = Path(tempfile.mkdtemp())
    # the ground (s09_ground): its tiles, and how much taller a building on a slope is drawn so its uphill side
    # is not buried (the map stands a building at the ground under its middle)
    try:
        ground = load(city_id, "ground")
    except FileNotFoundError:
        ground = {}
    if ground and not Path(ground.get("tiles", "")).exists():
        log("s10 tiles: the ground's tiles are not here (a build that did not run s09_ground); no hills")
        ground = {}
    rise = ground.get("rise", {})
    tile_feats, props, cards, storied = [], [], {}, []
    for i, f in enumerate(feats):
        p = f["properties"]
        tp = {k: p[k] for k in TILE_PROPS if k in p}
        if str(i) in rise and "h" in tp:
            tp["h"] = round(tp["h"] + rise[str(i)], 1)
        tile_feats.append({"type": "Feature", "id": i, "geometry": f["geometry"], "properties": tp})
        g = f["geometry"]
        ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        x, y = centroid(ring)
        props.append(p)
        # the card file has everything but what the index has; stories in full (the index keeps only which)
        rest = {k: v for k, v in p.items() if k not in SPARSE or k == "stories"}
        rest["xy"] = [round(x, 5), round(y, 5)]
        if p.get("stories"):        # for the card's Nearby row: buildings with a story, and where they are
            storied.append([i, round(x, 5), round(y, 5)])
        cards.setdefault(i // CHUNK, {})[i] = rest
    write_fc(tmp / "b.json", tile_feats)
    for k in ("roads", "water", "parks"):
        write_fc(tmp / f"{k}.json", pkg[k]["features"])
    areas = pkg.get("nature", {}).get("features", [])
    write_fc(tmp / "areas.json", [{"type": "Feature", "id": j, "geometry": a["geometry"],
                                   "properties": {**{k: a["properties"][k] for k in AREA_PROPS if k in a["properties"]}, "i": j}}
                                  for j, a in enumerate(areas)])

    routes = pkg.get("routes", {}).get("features", [])
    write_fc(tmp / "routes.json", [{"type": "Feature", "geometry": r["geometry"],
                                    "properties": {k: r["properties"][k] for k in ("i", "name") if k in r["properties"]}}
                                   for r in routes])
    land = pkg.get("land", {})
    write_fc(tmp / "land.json", land.get("features", []))
    write_fc(tmp / "basics.json", [{**f, "tippecanoe": {"minzoom": 14}} for f in pkg.get("basics", {}).get("features", [])])

    t0 = time.time()
    tiles = root / "tiles"
    cmd = [exe, "-q", "--force", "-e", str(tiles), f"-Z{MIN_Z}", f"-z{MAX_Z}",
           "--drop-smallest-as-needed", "--extend-zooms-if-still-dropping", "--no-tile-stats",
           "-L", f"b:{tmp / 'b.json'}", "-L", f"roads:{tmp / 'roads.json'}",
           "-L", f"water:{tmp / 'water.json'}", "-L", f"parks:{tmp / 'parks.json'}", "-L", f"areas:{tmp / 'areas.json'}",
           "-L", f"routes:{tmp / 'routes.json'}", "-L", f"land:{tmp / 'land.json'}", "-L", f"basics:{tmp / 'basics.json'}"]
    subprocess.run(cmd, check=True)
    (tiles / "metadata.json").unlink(missing_ok=True)
    n_tiles = sum(1 for _ in tiles.rglob("*.pbf"))
    size = sum(f.stat().st_size for f in tiles.rglob("*.pbf"))
    shutil.rmtree(tmp, ignore_errors=True)

    if ground:
        shutil.copytree(ground["tiles"], root / "ground")
    for n, chunk in cards.items():
        (root / "cards" / f"{n}.json").write_text(json.dumps(chunk, separators=(",", ":"), ensure_ascii=False))
    slim = {k: v for k, v in pkg.items() if k not in ("buildings", "roads", "water", "parks", "nature", "routes", "basics", "land")}
    # the land's named places (s06_land): what their card and the Layers sheet need; the shapes are in the tiles
    slim["land"] = land.get("entries", [])
    # routes: drawn from the tiles; here what their card needs, and their bounds to fly to
    slim["routes"] = [{**r["properties"], "bb": bounds_lines(r["geometry"])} for r in routes]
    slim["near"] = storied
    # areas: drawn from the tiles; here what their card and the Layers sheet need, and their bounds to fly to
    slim["areas"] = [None if a["properties"].get("t") in TILE_ONLY else {**a["properties"], "bb": bounds(a["geometry"])}
                     for a in areas]
    parts = {}
    for i, f in enumerate(feats):
        osm = f["properties"].get("osm")
        if osm:
            parts.setdefault(int(osm.split("/")[1]) % OSM_PARTS, {})[osm] = i
    for n, part in parts.items():
        (root / "osm" / f"{n}.json").write_text(json.dumps(part, separators=(",", ":")))
    if ground:
        slim["ground"] = ground["meta"]
    slim.update({"index": index(props), "tiles": {"minzoom": MIN_Z, "maxzoom": MAX_Z, "chunk": CHUNK,
                                                                   "osmParts": OSM_PARTS},
                 "build": time.strftime("%Y%m%d%H%M%S", time.gmtime())})
    out_json.write_text(json.dumps(slim, separators=(",", ":"), ensure_ascii=False))
    log(f"s10 tiles: {n_tiles} tiles ({size / 1e6:.1f} MB gzipped) in {time.time() - t0:.0f} s; "
        f"index {out_json.stat().st_size / 1e6:.1f} MB; {len(cards)} card files")
