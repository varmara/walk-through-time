"""Geometry in lon/lat degrees: points in rings, centres, distances, finding the building at a point."""
import math


def point_in_ring(x, y, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def bbox(ring):
    xs = [c[0] for c in ring]
    ys = [c[1] for c in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def centroid(ring):
    n = len(ring) - 1 if ring[0] == ring[-1] else len(ring)
    return [sum(c[0] for c in ring[:n]) / n, sum(c[1] for c in ring[:n]) / n]


def metres(a, b):
    """Approximate distance in metres between two lon/lat points (fine at city scale)."""
    kx = 111320 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 110540)


CELL = 0.002   # grid cell in degrees (about 140 x 220 m)
_grids = {}


def _grid(buildings):
    """Spatial index: grid cell -> building indexes whose bounding box touches it. Cached per list."""
    key = id(buildings)
    if key not in _grids or _grids[key][0] is not buildings:
        g = {}
        for i, b in enumerate(buildings):
            bb = b["bb"]
            for cx in range(int(bb[0] // CELL), int(bb[2] // CELL) + 1):
                for cy in range(int(bb[1] // CELL), int(bb[3] // CELL) + 1):
                    g.setdefault((cx, cy), []).append(i)
        _grids[key] = (buildings, g)
    return _grids[key][1]


def building_at(buildings, x, y, near=0):
    """Index of the building containing (x, y); with near > 0, else the closest within `near` metres."""
    pad = near / 70000 if near else 0
    best, best_d = None, None
    g = _grid(buildings)
    cand = set()
    for cx in range(int((x - pad) // CELL), int((x + pad) // CELL) + 1):
        for cy in range(int((y - pad) // CELL), int((y + pad) // CELL) + 1):
            cand.update(g.get((cx, cy), ()))
    for i in sorted(cand):
        b = buildings[i]
        bb = b["bb"]
        if not (bb[0] - pad <= x <= bb[2] + pad and bb[1] - pad <= y <= bb[3] + pad):
            continue
        if any(point_in_ring(x, y, r) for r in b["rings"]):
            return i
        if near:
            d = metres(centroid(b["rings"][0]), [x, y])
            if d <= near and (best_d is None or d < best_d):
                best, best_d = i, d
    return best


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


def rnd(coords):
    return [[round(x, 6), round(y, 6)] for x, y in coords]
