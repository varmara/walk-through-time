"""Rule layers: sets of buildings picked by a rule over an open dataset.

Each layer is a function decorated with @layer(...). It receives a Context and returns
{building index: group key} or {building index: (group key, {"story": "..."})}.
Groups split a layer into parts the page can show apart (for example listing grades).

These rules use only data the pipeline already downloads, so they work for any English city.
Hand-written stories are a different kind of layer: see stories/<city>.py and CONTRIBUTING.md.
"""
from dataclasses import dataclass

from .common import building_at, point_in_ring

LAYERS = []


def layer(**meta):
    """meta: id, title, intro, groups=[(key, title)], source=(title, url)."""
    def wrap(fn):
        LAYERS.append(dict(meta, fn=fn))
        return fn
    return wrap


@dataclass
class Context:
    buildings: list
    listing: dict      # {building index (str): [list entries, highest grade first]}
    places: list       # named OpenStreetMap points, with b = building index or None
    monuments: list    # Historic England scheduled monument features (GeoJSON)


# ---------- helpers for common joins ----------

def within(ctx, features, group):
    """Buildings whose centre lies inside any of the polygon features. group: key or fn(feature) -> key."""
    out = {}
    for f in features:
        g = f.get("geometry") or {}
        polys = [g["coordinates"]] if g.get("type") == "Polygon" else g.get("coordinates", []) if g.get("type") == "MultiPolygon" else []
        for poly in polys:
            outer = poly[0]
            xs, ys = [c[0] for c in outer], [c[1] for c in outer]
            for i, b in enumerate(ctx.buildings):
                bb = b["bb"]
                cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                if min(xs) <= cx <= max(xs) and min(ys) <= cy <= max(ys) and point_in_ring(cx, cy, outer):
                    out[i] = group(f) if callable(group) else group
    return out


def containing_places(ctx, test, group):
    """Buildings that contain a named OpenStreetMap place passing test(tags), or are tagged that way themselves."""
    out = {}
    for p in ctx.places:
        if p["b"] is not None and test(p["tags"]):
            out[p["b"]] = group
    for i, b in enumerate(ctx.buildings):
        if test(b["tags"]):
            out[i] = group
    return out


# ---------- layers ----------

@layer(id="listed", title="Listed buildings",
       intro="Buildings on the National Heritage List for England. Grade I buildings are of exceptional interest, "
             "Grade II* buildings are particularly important, and Grade II buildings are of special interest.",
       groups=[("listed-I", "Grade I"), ("listed-II*", "Grade II*"), ("listed-II", "Grade II")],
       source=("Historic England, National Heritage List for England", "https://historicengland.org.uk/listing/the-list/"))
def listed(ctx):
    return {int(i): "listed-" + es[0]["Grade"] for i, es in ctx.listing.items() if es[0].get("Grade") in ("I", "II*", "II")}


@layer(id="scheduled", title="Scheduled monuments",
       intro="Buildings standing on a scheduled monument: a nationally important archaeological site or structure "
             "protected by law.",
       groups=[("scheduled", "Scheduled monument")],
       source=("Historic England, National Heritage List for England", "https://historicengland.org.uk/listing/the-list/"))
def scheduled(ctx):
    return {i: ("scheduled", {"story": f"Part of the scheduled monument “{f['properties'].get('Name', '').strip()}”."})
            for f in ctx.monuments for i in within(ctx, [f], "scheduled")}


@layer(id="pubs", title="Pubs today",
       intro="Buildings with a pub in them today, according to OpenStreetMap.",
       groups=[("pubs", "Pub")],
       source=("OpenStreetMap", "https://www.openstreetmap.org/copyright"))
def pubs(ctx):
    return containing_places(ctx, lambda t: t.get("amenity") == "pub", "pubs")
