"""The shape of the ground, for the map's hills: elevation tiles made from the Environment Agency's laser survey.

  source   LIDAR Composite DTM, 2 m (the ground with buildings, bridges and trees taken out), the latest year,
           in the Ordnance Survey's 5 km squares, found through the Defra survey catalogue's search and downloaded
           as GeoTIFF. Open Government Licence; "© Environment Agency copyright and/or database right".
  area     the city's box and MARGIN around it, so the hills do not end in a cliff at the map's edge; beyond the
           survey, and in its few gaps (water, glass), the nearest height is carried on.
  tiles    data/<city>/ground/{z}/{x}/{y}.png, zoom MIN_Z to MAX_Z, 256 px, "Terrarium" encoding (MapLibre's
           raster-dem): red * 256 + green + blue / 256 - 32768 metres, heights to 0.1 m (enough, and the PNGs smaller).

The tiles are kept in $WTT_CACHE (with the downloads) under a fingerprint of the area and this script, so a build
that changes neither reuses them instead of downloading 100 MB again (the downloads themselves are not kept). Needs rasterio, numpy and Pillow (the build
installs them); without them the step says so and the map has no hills.
"""
import hashlib
import io
import json
import math
import os
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

from .common import city, log
from .web import UA

SEARCH = "https://environment.data.gov.uk/backend/catalog/api/tiles/collections/survey/search"
PRODUCT, RES = "lidar_composite_dtm", "2m"
MIN_Z, MAX_Z = 10, 15
MARGIN = 0.02                 # degrees, about 1.5 km
TILE = 256
CREDIT = "© Environment Agency copyright and/or database right"


def ground_box(c):
    b = c["bbox"]
    return {"w": b["w"] - MARGIN * 1.6, "s": b["s"] - MARGIN, "e": b["e"] + MARGIN * 1.6, "n": b["n"] + MARGIN}


def squares(box):
    """The survey's 5 km squares over the box, latest year: [{label, uri, year}]."""
    ring = [[box["w"], box["s"]], [box["e"], box["s"]], [box["e"], box["n"]], [box["w"], box["n"]], [box["w"], box["s"]]]
    r = json.loads(fetch(SEARCH, json.dumps({"type": "Polygon", "coordinates": [ring]}).encode(), timeout=120))
    best = {}
    for x in r.get("results", []):
        if x["product"]["id"] != PRODUCT or x["resolution"]["label"] != RES:
            continue
        t = x["tile"]["id"]
        if t not in best or x["year"]["id"] > best[t]["year"]:
            best[t] = {"label": x["label"], "uri": x["uri"], "year": x["year"]["id"]}
    return sorted(best.values(), key=lambda s: s["label"])


def fetch(url, body=None, timeout=300, tries=3):
    """A download, not kept among the saved web answers (the squares are big, and kept apart)."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, **(
                {"Content-Type": "application/geo+json", "Accept": "application/json"} if body else {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - retry any network or server error
            last = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def tiles_for(box, z):
    def tx(lon):
        return int((lon + 180) / 360 * 2 ** z)

    def ty(lat):
        r = math.radians(lat)
        return int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * 2 ** z)
    for x in range(tx(box["w"]), tx(box["e"]) + 1):
        for y in range(ty(box["n"]), ty(box["s"]) + 1):
            yield x, y


def mercator_bounds(z, x, y):
    n = 2 ** z
    size = 2 * math.pi * 6378137 / n
    left = -math.pi * 6378137 + x * size
    top = math.pi * 6378137 - y * size
    return left, top - size, left + size, top


def terrarium(h):
    import numpy as np
    v = np.round(h, 1) + 32768.0
    r = np.floor(v / 256)
    g = np.floor(v - r * 256)
    b = np.round((v - r * 256 - g) * 256)
    return np.dstack([r, g, np.minimum(b, 255)]).astype("uint8")


def build(c, out, cache):
    import numpy as np
    import rasterio
    from PIL import Image
    from rasterio.enums import Resampling
    from rasterio.fill import fillnodata
    from rasterio.transform import Affine
    from rasterio.warp import reproject

    box = ground_box(c)
    sq = squares(box)
    if not sq:
        raise RuntimeError("the survey catalogue found no ground model for this area")
    tifs = []
    for s in sq:
        z = cache / f"{s['label']}.zip"
        if not z.exists():
            z.write_bytes(fetch(s["uri"]))
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".tif"))
            tif = cache / name
            if not tif.exists():
                tif.write_bytes(zf.read(name))
        tifs.append(tif)
    log(f"s10 ground: {len(sq)} squares of the {PRODUCT} {RES} ({', '.join(sorted({s['year'] for s in sq}))})")

    # the squares side by side on their common 2 m grid (rasterio's merge gave a mosaic of zeros here)
    srcs = [rasterio.open(t) for t in tifs]
    res = srcs[0].res[0]
    left, top = min(x.bounds.left for x in srcs), max(x.bounds.top for x in srcs)
    right, bottom = max(x.bounds.right for x in srcs), min(x.bounds.bottom for x in srcs)
    h = np.full((round((top - bottom) / res), round((right - left) / res)), np.nan, "float32")
    for x in srcs:
        a = x.read(1).astype("float32")
        log(f"    {Path(x.name).name}: {x.width} x {x.height}, {np.nanmin(a):.1f} to {np.nanmax(a):.1f}, nodata {x.nodata}")
        if x.nodata is not None:
            a[a == np.float32(x.nodata)] = np.nan
        r0, c0 = round((top - x.bounds.top) / res), round((x.bounds.left - left) / res)
        part = h[r0:r0 + a.shape[0], c0:c0 + a.shape[1]]
        np.copyto(part, a, where=np.isnan(part))
    transform = Affine(res, 0, left, 0, -res, top)
    crs = srcs[0].crs
    for x in srcs:
        x.close()
    valid = np.isfinite(h) & (h > -100)
    log(f"    {h.shape[1]} x {h.shape[0]} cells, {100 * valid.mean():.1f}% surveyed, "
        f"{float(h[valid].min()):.0f} to {float(h[valid].max()):.0f} m")
    if not valid.all():
        h = fillnodata(np.where(valid, h, 0), mask=valid.astype("uint8"), max_search_distance=400)
    log(f"    after filling the gaps: {float(h.min()):.0f} to {float(h.max()):.0f} m")
    # the edges carried outwards, so tiles at the margin have ground under them
    pad = 1500
    h = np.pad(h, pad, mode="edge")
    transform = transform * Affine.translation(-pad, -pad)

    count = 0
    for z in range(MIN_Z, MAX_Z + 1):
        for x, y in tiles_for(box, z):
            left, bottom, right, top = mercator_bounds(z, x, y)
            dst = np.zeros((TILE, TILE), "float32")
            reproject(h, dst, src_transform=transform, src_crs=crs,
                      dst_transform=rasterio.transform.from_bounds(left, bottom, right, top, TILE, TILE),
                      dst_crs="EPSG:3857", resampling=Resampling.average if z < MAX_Z else Resampling.bilinear)
            p = out / str(z) / str(x) / f"{y}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            buf = io.BytesIO()
            Image.fromarray(terrarium(dst), "RGB").save(buf, "PNG", optimize=True)
            p.write_bytes(buf.getvalue())
            count += 1
    lo, hi = float(np.percentile(h, 1)), float(np.percentile(h, 99))
    meta = {"minzoom": MIN_Z, "maxzoom": MAX_Z, "encoding": "terrarium", "tileSize": TILE,
            "bounds": [round(box["w"], 4), round(box["s"], 4), round(box["e"], 4), round(box["n"], 4)],
            "year": max(s["year"] for s in sq), "credit": CREDIT, "range": [round(lo), round(hi)]}
    (out / "ground.json").write_text(json.dumps(meta))
    log(f"    {count} tiles, ground from {lo:.0f} to {hi:.0f} m above sea level")
    return meta


def stamp(c):
    return hashlib.sha256(json.dumps(ground_box(c)).encode() + Path(__file__).read_bytes()).hexdigest()[:16]


def main(city_id):
    c = city(city_id)
    root = Path(os.environ.get("WTT_CACHE") or "work") / "ground" / city_id
    done = root / f"tiles-{stamp(c)}"
    if not (done / "ground.json").exists():
        try:
            import numpy, rasterio, PIL  # noqa: F401
        except ImportError:
            log("s10 ground: rasterio, numpy or Pillow is missing; the map has no hills this build")
            return
        downloads = root / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        for old in root.glob("tiles-*"):
            shutil.rmtree(old, ignore_errors=True)
        tmp = root / "tiles-partial"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            build(c, tmp, downloads)
        except Exception as e:  # noqa: BLE001 - the map works without hills
            log(f"s10 ground: no hills this build: {e}")
            return
        tmp.rename(done)
        shutil.rmtree(downloads, ignore_errors=True)     # the tiles are kept; the squares are 100 MB
    else:
        log("s10 ground: the tiles of the last build (area and script unchanged)")
    dest = Path("data") / city_id / "ground"
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(done, dest)
    meta = json.loads((done / "ground.json").read_text())
    (dest / "ground.json").unlink()
    # the index tells the page there is ground, and where
    idx = Path(f"data/{city_id}.json")
    if idx.exists():
        d = json.loads(idx.read_text())
        d["ground"] = meta
        idx.write_text(json.dumps(d, separators=(",", ":"), ensure_ascii=False))
