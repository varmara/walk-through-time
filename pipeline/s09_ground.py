"""The shape of the ground, for the map's hills: elevation tiles made from the Environment Agency's laser survey.

  source   LIDAR Composite DTM, 2 m (the ground with buildings, bridges and trees taken out), the latest year,
           in the Ordnance Survey's 5 km squares, found through the Defra survey catalogue's search and downloaded
           as GeoTIFF. Open Government Licence; "© Environment Agency copyright and/or database right".
  area     the city's box and MARGIN around it, so the hills do not end in a cliff at the map's edge; beyond the
           survey, and in its few gaps (water, glass), the nearest height is carried on.
  tiles    data/<city>/ground/{z}/{x}/{y}.webp (copied there by s10_tiles), zoom MIN_Z to MAX_Z, 256 px, "Terrarium"
           encoding (MapLibre's raster-dem): red * 256 + green + blue / 256 - 32768 metres, heights to 0.1 m (enough,
           and the files smaller). Lossless WebP: the very pixels a PNG would hold (so the very heights), in about
           60% of the bytes; never a lossy kind, which would change heights.

Buildings on a slope: the map stands each building at the ground under its middle, so on a steep street (the
Park's cliff, Mapperley) its uphill side would be buried. For each building this step measures how far the ground
under its outline rises above its middle (`rise`, in work/<city>/ground.json), and s10_tiles makes the building
that much taller; the map already sinks a building's foot 10 m into the ground on its downhill side.

When the hills are made again: only when their source changes. Each build asks the catalogue which squares cover
the area (one small request); the hills' fingerprint is the area, those squares' names (each names its survey year,
so a newer survey is a new name) and FORMAT, the way the tiles are made: raise FORMAT when changing that (the zooms,
the encoding), and only then. Other edits to this script do not make the hills again.

Where the made hills are kept: under their fingerprint in $WTT_CACHE (the build cache, which GitHub drops after a
week unused), and as hills-<city>-<fingerprint>.tar in $WTT_RAW, which the build keeps in the repo's "raw-data"
release (tools/raw.sh), so a build after a quiet week unpacks them in seconds instead of making them again.

If the catalogue cannot be asked (its address has changed before): the last hills made, else the squares kept
from earlier. If the hills cannot be made: the last build's, else (s10_tiles) the hills already published.

The squares are kept as downloaded in $WTT_RAW and in the release; a square's name has its survey year, so one kept
is never downloaded from the survey again. A build fetches them from the release only when it makes the hills. Needs rasterio, numpy and Pillow (the build installs them); without them, the last
hills made are used.
"""
import hashlib
import io
import json
import math
import os
import shutil
import tarfile
import time
import urllib.request
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import city, load, log, save
from .web import UA

SEARCH = "https://environment.data.gov.uk/tiles/collections/survey/search"
PRODUCT, RES = "lidar_composite_dtm", "2m"
MIN_Z, MAX_Z = 10, 15
MARGIN = 0.02                 # degrees, about 1.5 km
TILE = 256
EXT = "webp"                  # the tiles' file type (also in ground.json, for the page)
FORMAT = 2                    # how the tiles are made (1: PNG, 2: lossless WebP); raise it to make them again
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


def in_release(cache):
    """The names of the files in the raw-data release (raw/assets.txt, written by tools/raw.sh fetch)."""
    f = Path(cache) / "assets.txt"
    return set(f.read_text().split()) if f.exists() else set()


def released(name):
    """The address of a file in the repo's raw-data release, if it is there (on GitHub Actions)."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    cache = os.environ.get("WTT_RAW") or "raw"
    if repo and name in in_release(cache):
        return f"https://github.com/{repo}/releases/download/raw-data/{name}"
    return None


def kept_squares(cache):
    """The squares already kept in the raw folder, named as the catalogue named them (ground-<label>.zip): for when
    the catalogue cannot be asked (its address has changed before). All are offered; build() leaves out those that do
    not touch the area."""
    best = {}
    names = {z.name for z in Path(cache).glob(f"ground-{PRODUCT}-*-{RES}-*.zip")}
    names |= {n for n in in_release(cache) if n.startswith(f"ground-{PRODUCT}-") and f"-{RES}-" in n and n.endswith(".zip")}
    for name in sorted(names):
        label = name[len("ground-"):-len(".zip")]
        year, tile = label.split("-")[1], label.split("-")[-1]
        if tile not in best or year > best[tile]["year"]:
            best[tile] = {"label": label, "uri": None, "year": year}
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


def encode(arr):
    """A tile (Terrarium pixels) as lossless WebP. Method 6, the smallest: slow, but paid once, as the tiles are made
    again only when their source changes."""
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, "WEBP", lossless=True, quality=100, method=6)
    return buf.getvalue()


def build(c, out, cache, sq):
    import numpy as np
    import rasterio
    from PIL import features
    from rasterio.enums import Resampling
    from rasterio.fill import fillnodata
    from rasterio.transform import Affine
    from rasterio.warp import reproject, transform_bounds

    if not features.check("webp"):
        raise RuntimeError("this Pillow cannot write WebP")
    box = ground_box(c)
    if not sq:
        raise RuntimeError("the survey catalogue found no ground model for this area")
    tifs, used, got, kept = [], [], 0, 0
    unpacked = out / "unpacked"
    unpacked.mkdir(parents=True, exist_ok=True)
    for s in sq:
        z = cache / f"ground-{s['label']}.zip"
        if not z.exists():
            from_release = released(z.name)
            if from_release:
                z.write_bytes(fetch(from_release))
                kept += 1
            elif s["uri"]:
                z.write_bytes(fetch(s["uri"]))
                got += 1
            else:
                raise RuntimeError(f"{z.name} is neither here nor in the release, and has no address")
        else:
            kept += 1
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".tif"))
            tif = unpacked / name
            tif.write_bytes(zf.read(name))
        with rasterio.open(tif) as r:             # (a kept square may belong to another area)
            w, so, e, n = transform_bounds("EPSG:4326", r.crs, box["w"], box["s"], box["e"], box["n"])
            near = r.bounds.right >= w and r.bounds.left <= e and r.bounds.top >= so and r.bounds.bottom <= n
        if near:
            tifs.append(tif)
            used.append(s)
        else:
            tif.unlink()
    if not tifs:
        raise RuntimeError("none of the ground squares touches this area")
    sq = used
    log(f"s09 ground: {len(sq)} squares of the {PRODUCT} {RES} ({', '.join(sorted({s['year'] for s in sq}))}), "
        f"{got} downloaded from the survey, {kept} kept from earlier")

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
    shutil.rmtree(unpacked, ignore_errors=True)
    valid = np.isfinite(h) & (h > -100)
    log(f"    {h.shape[1]} x {h.shape[0]} cells, {100 * valid.mean():.1f}% surveyed, "
        f"{float(h[valid].min()):.0f} to {float(h[valid].max()):.0f} m")
    if not valid.all():
        h = fillnodata(np.where(valid, h, 0), mask=valid.astype("uint8"), max_search_distance=400)
    log(f"    after filling the gaps: {float(h.min()):.0f} to {float(h.max()):.0f} m")
    # kept, at 4 m and to 0.1 m, for measuring buildings on slopes (main, rises)
    small = np.round(h[::2, ::2] * 10).astype("int16")
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "dem.npz", dm=small, transform=np.array(tuple(transform * Affine.scale(2)))[:6],
                        crs=np.array(crs.to_wkt()))
    # the edges carried outwards, so tiles at the margin have ground under them
    pad = 1500
    h = np.pad(h, pad, mode="edge")
    transform = transform * Affine.translation(-pad, -pad)

    count, total = 0, 0
    workers = os.cpu_count() or 2
    waiting = deque()                 # (file, its encoding under way), oldest first: at most a few at a time in memory

    def write_oldest():
        nonlocal total
        p, job = waiting.popleft()
        data = job.result()
        p.write_bytes(data)
        total += len(data)

    with ThreadPoolExecutor(workers) as pool:         # (Pillow lets go of the interpreter while it encodes)
        for z in range(MIN_Z, MAX_Z + 1):
            for x, y in tiles_for(box, z):
                left, bottom, right, top = mercator_bounds(z, x, y)
                dst = np.zeros((TILE, TILE), "float32")
                reproject(h, dst, src_transform=transform, src_crs=crs,
                          dst_transform=rasterio.transform.from_bounds(left, bottom, right, top, TILE, TILE),
                          dst_crs="EPSG:3857", resampling=Resampling.average if z < MAX_Z else Resampling.bilinear)
                p = out / "tiles" / str(z) / str(x) / f"{y}.{EXT}"
                p.parent.mkdir(parents=True, exist_ok=True)
                waiting.append((p, pool.submit(encode, terrarium(dst))))
                count += 1
                while len(waiting) > 4 * workers:
                    write_oldest()
        while waiting:
            write_oldest()
    lo, hi = float(np.percentile(h, 1)), float(np.percentile(h, 99))
    meta = {"minzoom": MIN_Z, "maxzoom": MAX_Z, "encoding": "terrarium", "tileSize": TILE,
            "bounds": [round(box["w"], 4), round(box["s"], 4), round(box["e"], 4), round(box["n"], 4)],
            "ext": EXT, "year": max(s["year"] for s in sq), "credit": CREDIT, "range": [round(lo), round(hi)]}
    (out / "ground.json").write_text(json.dumps(meta))
    log(f"    {count} tiles ({total / 1e6:.1f} MB), ground from {lo:.0f} to {hi:.0f} m above sea level")
    return meta


def fingerprint(box, sq):
    """The hills' source: the area, the squares (by name: each names its survey year) and how the tiles are made."""
    src = {"box": box, "squares": sorted(x["label"] for x in sq), "format": FORMAT,
           "tiles": [MIN_Z, MAX_Z, TILE, EXT, PRODUCT, RES]}
    return hashlib.sha256(json.dumps(src, sort_keys=True).encode()).hexdigest()[:16]


def package(downloads, city_id, fp):
    return Path(downloads) / f"hills-{city_id}-{fp}.tar"


def unpack(tar, done):
    tmp = done.with_name("tiles-unpacking")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(tar) as t:
        t.extractall(tmp, filter="data")
    tmp.rename(done)


def pack(done, tar):
    part = tar.with_suffix(".partial")
    with tarfile.open(part, "w") as t:          # (WebP and npz are packed already: no compression)
        for name in ("ground.json", "dem.npz", "tiles"):
            t.add(done / name, arcname=name)
    part.rename(tar)
    for old in tar.parent.glob(tar.name.rsplit("-", 1)[0] + "-*.tar"):
        if old != tar:
            old.unlink()


def find(root, downloads, city_id, fp):
    """The hills already made from this source (fp), here or in the release; with no fingerprint (the catalogue
    could not be asked), the last made."""
    if fp:
        done = root / f"tiles-{fp}"
        if (done / "ground.json").exists():
            return done, "kept from the last build (their source is unchanged)"
        tar = package(downloads, city_id, fp)
        if tar.exists():
            unpack(tar, done)
            return done, "unpacked from the raw-data release (their source is unchanged)"
        return None, None
    made = sorted((d for d in root.glob("tiles-*") if (d / "ground.json").exists()), key=lambda d: d.stat().st_mtime)
    if made:
        return made[-1], "the last made"
    tars = sorted(Path(downloads).glob(f"hills-{city_id}-*.tar"))
    if tars:
        done = root / f"tiles-{tars[-1].stem.rsplit('-', 1)[1]}"
        unpack(tars[-1], done)
        return done, "the last made, from the raw-data release"
    return None, None


def main(city_id):
    c = city(city_id)
    box = ground_box(c)
    root = Path(os.environ.get("WTT_CACHE") or "work") / "ground" / city_id
    root.mkdir(parents=True, exist_ok=True)
    downloads = Path(os.environ.get("WTT_RAW") or "raw")      # the squares as downloaded, and the hills: kept
    downloads.mkdir(parents=True, exist_ok=True)               # (tools/raw.sh)
    try:
        sq = squares(box)
    except Exception as e:  # noqa: BLE001 - the catalogue is down or has moved
        log(f"s09 ground: the survey catalogue could not be asked ({e})")
        sq = None
    fp = fingerprint(box, sq) if sq else None
    done, how = find(root, downloads, city_id, fp)
    if done:
        log(f"s09 ground: the hills {how}")
    else:
        try:
            import numpy, rasterio, PIL  # noqa: F401
        except ImportError:
            log("s09 ground: rasterio, numpy or Pillow is missing")
            keep_last(city_id)
            return
        if sq is None:
            sq = kept_squares(downloads)
            log(f"s09 ground: using the {len(sq)} squares kept from earlier")
            fp = fingerprint(box, sq)
        done = root / f"tiles-{fp}"
        tmp = root / "tiles-partial"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            build(c, tmp, downloads, sq)
        except Exception as e:  # noqa: BLE001 - the map works without hills
            log(f"s09 ground: the hills could not be built: {e}")
            shutil.rmtree(tmp, ignore_errors=True)
            done, how = find(root, downloads, city_id, None)
            if not done:
                keep_last(city_id)
                return
            log(f"s09 ground: the hills {how}")
        else:
            tmp.rename(done)
            pack(done, package(downloads, city_id, fp))
            log(f"    packed for the raw-data release: {package(downloads, city_id, fp).name}")
    for old in root.glob("tiles-*"):              # others: an older source's
        if old != done:
            shutil.rmtree(old, ignore_errors=True)
    meta = json.loads((done / "ground.json").read_text())
    rise = rises(city_id, done / "dem.npz")
    save(city_id, "ground", {"tiles": str(done / "tiles"), "meta": meta, "rise": rise})
    log(f"    {len(rise)} buildings stand on a slope: made taller by up to {max(rise.values(), default=0):.0f} m")


def keep_last(city_id):
    """The hills could not be built: keep the last build's (its work file and tiles, if still here), else none.
    (s10_tiles then falls back to the hills already published.)"""
    try:
        last = load(city_id, "ground")
    except FileNotFoundError:
        last = {}
    if last and Path(last.get("tiles", "")).exists():
        log("s09 ground: keeping the hills of the last build")
        return
    save(city_id, "ground", {})


def rises(city_id, dem):
    """{building index: metres} where the ground under a building's outline rises more than a metre above the
    ground under its middle (the vertices' average, as the map takes it)."""
    import numpy as np
    from rasterio.crs import CRS
    from rasterio.transform import Affine
    from rasterio.warp import transform as reproject_points
    d = np.load(dem)
    dm, t, crs = d["dm"], Affine(*d["transform"].tolist()), CRS.from_wkt(str(d["crs"]))
    feats = load(city_id, "package")["buildings"]["features"]
    xs, ys, owner = [], [], []
    for i, f in enumerate(feats):
        g = f["geometry"]
        ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        ring = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
        pts = ring + [[sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)]]   # the middle last
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
        owner.append(len(pts))
    ex, ny = reproject_points("EPSG:4326", crs, xs, ys)
    inv = ~t
    cols, rows = inv * (np.array(ex), np.array(ny))
    rows = np.clip(rows.astype(int), 0, dm.shape[0] - 1)
    cols = np.clip(cols.astype(int), 0, dm.shape[1] - 1)
    g = dm[rows, cols] / 10.0
    out, k = {}, 0
    for i, n in enumerate(owner):
        part = g[k:k + n]
        k += n
        r = float(part[:-1].max() - part[-1])
        if r > 1:
            out[str(i)] = round(r * 2) / 2
    return out
