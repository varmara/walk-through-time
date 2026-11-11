"""What the page loads: vector tiles for the map, a small index of every building, and card files.

The page used to load one file with every building's outline and every detail (18 MB, 2.4 MB compressed)
and build the whole city before showing anything. Now:
  data/<city>/tiles/{z}/{x}/{y}.pbf   Mapbox Vector Tiles (gzipped), made by tippecanoe, zoom 10 to 15
                                      (the map draws closer zooms from the zoom 15 tiles). Layers:
                                      b (buildings: id = building index; y, f, h, base, L for colour, filters and
                                      height), roads (k), water, parks. The phone loads only the tiles on screen,
                                      with simpler outlines when zoomed out.
                                      Also areas (nature and conservation areas, t = which kind, i = its number).
  data/<city>.json                    the index: only what the page needs before any card opens: the few buildings
                                      with a name, layers or a listing (see index()), how many buildings stand by
                                      each year (for the count under the slider), layers, pins, and the areas'
                                      names and bounds. Small however big the map gets: no outlines, no centres.
  data/<city>/osm.json                OpenStreetMap id of every building, for links that name one (?osm=way/123).
  data/<city>/cards/<n>.json          everything else about a building (its centre, year, summary, photos, stories,
                                      sources, height…), CHUNK buildings per file, loaded when a card opens.
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

from .common import centroid, load, log

CHUNK = 1000
MIN_Z, MAX_Z = 10, 15         # zoomed out (10-11) the smallest buildings are left out so tiles stay small
TILE_PROPS = ("y", "f", "h", "base", "L")
# what the index keeps, for the few buildings that have them; everything else goes to the card files
SPARSE = ("name", "listName", "L", "stories", "grade")
AREA_PROPS = ("t", "name")          # in the tiles; the rest of an area's details are in the index


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

    tmp = Path(tempfile.mkdtemp())
    tile_feats, props, cards = [], [], {}
    for i, f in enumerate(feats):
        p = f["properties"]
        tile_feats.append({"type": "Feature", "id": i, "geometry": f["geometry"],
                           "properties": {k: p[k] for k in TILE_PROPS if k in p}})
        g = f["geometry"]
        ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        x, y = centroid(ring)
        props.append(p)
        # the card file has everything but what the index has; stories in full (the index keeps only which)
        rest = {k: v for k, v in p.items() if k not in SPARSE or k == "stories"}
        rest["xy"] = [round(x, 5), round(y, 5)]
        cards.setdefault(i // CHUNK, {})[i] = rest
    write_fc(tmp / "b.json", tile_feats)
    for k in ("roads", "water", "parks"):
        write_fc(tmp / f"{k}.json", pkg[k]["features"])
    areas = pkg.get("nature", {}).get("features", [])
    write_fc(tmp / "areas.json", [{"type": "Feature", "id": j, "geometry": a["geometry"],
                                   "properties": {**{k: a["properties"][k] for k in AREA_PROPS if k in a["properties"]}, "i": j}}
                                  for j, a in enumerate(areas)])

    t0 = time.time()
    tiles = root / "tiles"
    cmd = [exe, "-q", "--force", "-e", str(tiles), f"-Z{MIN_Z}", f"-z{MAX_Z}",
           "--drop-smallest-as-needed", "--extend-zooms-if-still-dropping", "--no-tile-stats",
           "-L", f"b:{tmp / 'b.json'}", "-L", f"roads:{tmp / 'roads.json'}",
           "-L", f"water:{tmp / 'water.json'}", "-L", f"parks:{tmp / 'parks.json'}", "-L", f"areas:{tmp / 'areas.json'}"]
    subprocess.run(cmd, check=True)
    (tiles / "metadata.json").unlink(missing_ok=True)
    n_tiles = sum(1 for _ in tiles.rglob("*.pbf"))
    size = sum(f.stat().st_size for f in tiles.rglob("*.pbf"))
    shutil.rmtree(tmp, ignore_errors=True)

    for n, chunk in cards.items():
        (root / "cards" / f"{n}.json").write_text(json.dumps(chunk, separators=(",", ":"), ensure_ascii=False))
    slim = {k: v for k, v in pkg.items() if k not in ("buildings", "roads", "water", "parks", "nature")}
    # areas: drawn from the tiles; here what their card and the Layers sheet need, and their bounds to fly to
    slim["areas"] = [{**a["properties"], "bb": bounds(a["geometry"])} for a in areas]
    (root / "osm.json").write_text(json.dumps([f["properties"].get("osm") for f in feats], separators=(",", ":")))
    slim.update({"index": index(props), "tiles": {"minzoom": MIN_Z, "maxzoom": MAX_Z, "chunk": CHUNK},
                 "build": time.strftime("%Y%m%d%H%M%S", time.gmtime())})
    out_json.write_text(json.dumps(slim, separators=(",", ":"), ensure_ascii=False))
    log(f"s10 tiles: {n_tiles} tiles ({size / 1e6:.1f} MB gzipped) in {time.time() - t0:.0f} s; "
        f"index {out_json.stat().st_size / 1e6:.1f} MB; {len(cards)} card files")
