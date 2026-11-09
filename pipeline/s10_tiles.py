"""What the page loads: vector tiles for the map, a small index of every building, and card files.

The page used to load one file with every building's outline and every detail (18 MB, 2.4 MB compressed)
and build the whole city before showing anything. Now:
  data/<city>/tiles/{z}/{x}/{y}.pbf   Mapbox Vector Tiles (gzipped), made by tippecanoe, zoom 12 to 15
                                      (the map draws closer zooms from the zoom 15 tiles). Layers:
                                      b (buildings: id = building index; y, f, h, base, L for colour, filters and
                                      height), roads (k), water, parks. The phone loads only the tiles on screen,
                                      with simpler outlines when zoomed out.
  data/<city>.json                    the index: per building what the year slider, the layers, the counts and the
                                      places strip need, in columns (see index()), plus layers, pins and areas.
                                      No outlines.
  data/<city>/osm.json                OpenStreetMap id of every building, for links that name one (?osm=way/123).
  data/<city>/cards/<n>.json          everything else a building's card shows (summary, photos, sources, height…),
                                      CHUNK buildings per file, loaded when a card opens.
tippecanoe (github.com/felt/tippecanoe, BSD) must be on the PATH, or named by $TIPPECANOE. Without it this step
writes the old single file instead, which the page can still read.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .common import centroid, load, log

CHUNK = 1000
MIN_Z, MAX_Z = 12, 15
TILE_PROPS = ("y", "f", "h", "base", "L")
# what the index keeps; everything else goes to the card files
INDEX_PROPS = ("name", "listName", "y", "f", "per", "sh", "dt", "L", "stories", "grade")
SPARSE = ("name", "listName", "dt", "L", "stories", "grade")      # few buildings have these: kept per building
FLAG = {"exact": "e", "approx": "a", "century": "c", "area": "r"}
SCALE = 1e5                                                      # centres to about a metre


def tippecanoe():
    exe = os.environ.get("TIPPECANOE") or shutil.which("tippecanoe")
    return exe if exe and Path(exe).exists() else None


def write_fc(path, feats):
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))


def index(props, centres):
    """Columns, one value per building (its index), which compress far better than one object per building:
    centre points as whole numbers of 1e-5 degrees, each the difference from the previous one; years (null when
    none); date precision as one letter each (e exact, a approx, c century, r area estimate, - none); area
    periods as a number into a list; and the rarer fields (name, layers, stories, listing) per building."""
    ox, oy = min(c[0] for c in centres), min(c[1] for c in centres)
    dxy, px, py = [], 0, 0
    for x, y in centres:
        ix, iy = round((x - ox) * SCALE), round((y - oy) * SCALE)
        dxy += [ix - px, iy - py]
        px, py = ix, iy
    periods = sorted({p["per"] for p in props if p.get("per")})
    return {"n": len(props), "origin": [round(ox, 5), round(oy, 5)], "scale": SCALE, "dxy": dxy,
            "y": [p.get("y") for p in props], "f": "".join(FLAG.get(p.get("f"), "-") for p in props),
            "periods": periods, "per": [periods.index(p["per"]) if p.get("per") else -1 for p in props],
            "sh": [p.get("sh") or 0 for p in props],
            "props": {str(i): s for i, p in enumerate(props) if (s := {k: p[k] for k in SPARSE if k in p})}}


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
    tile_feats, props, centres, cards = [], [], [], {}
    for i, f in enumerate(feats):
        p = f["properties"]
        tile_feats.append({"type": "Feature", "id": i, "geometry": f["geometry"],
                           "properties": {k: p[k] for k in TILE_PROPS if k in p}})
        g = f["geometry"]
        ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        x, y = centroid(ring)
        props.append(p)
        centres.append((x, y))
        rest = {k: v for k, v in p.items() if k not in INDEX_PROPS}
        if rest:
            cards.setdefault(i // CHUNK, {})[i] = rest
    write_fc(tmp / "b.json", tile_feats)
    for k in ("roads", "water", "parks"):
        write_fc(tmp / f"{k}.json", pkg[k]["features"])

    t0 = time.time()
    tiles = root / "tiles"
    cmd = [exe, "-q", "--force", "-e", str(tiles), f"-Z{MIN_Z}", f"-z{MAX_Z}",
           "--drop-smallest-as-needed", "--extend-zooms-if-still-dropping", "--no-tile-stats",
           "-L", f"b:{tmp / 'b.json'}", "-L", f"roads:{tmp / 'roads.json'}",
           "-L", f"water:{tmp / 'water.json'}", "-L", f"parks:{tmp / 'parks.json'}"]
    subprocess.run(cmd, check=True)
    (tiles / "metadata.json").unlink(missing_ok=True)
    n_tiles = sum(1 for _ in tiles.rglob("*.pbf"))
    size = sum(f.stat().st_size for f in tiles.rglob("*.pbf"))
    shutil.rmtree(tmp, ignore_errors=True)

    for n, chunk in cards.items():
        (root / "cards" / f"{n}.json").write_text(json.dumps(chunk, separators=(",", ":"), ensure_ascii=False))
    slim = {k: v for k, v in pkg.items() if k not in ("buildings", "roads", "water", "parks")}
    (root / "osm.json").write_text(json.dumps([f["properties"].get("osm") for f in feats], separators=(",", ":")))
    slim.update({"index": index(props, centres), "tiles": {"minzoom": MIN_Z, "maxzoom": MAX_Z, "chunk": CHUNK},
                 "build": time.strftime("%Y%m%d%H%M%S", time.gmtime())})
    out_json.write_text(json.dumps(slim, separators=(",", ":"), ensure_ascii=False))
    log(f"s10 tiles: {n_tiles} tiles ({size / 1e6:.1f} MB gzipped) in {time.time() - t0:.0f} s; "
        f"index {out_json.stat().st_size / 1e6:.1f} MB; {len(cards)} card files")
