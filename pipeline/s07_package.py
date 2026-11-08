"""Write the files the page loads, and a data report.

  data/<city>.json        buildings (GeoJSON with all attributes), base map, layers, stats
  data/<city>-report.md   coverage of dates by precision and source, conflicts, layers, dropped stories

Building properties: name, y (year), f (exact | approx | century), src, alts [{y, f, src}],
h (height, m), levels, kind, osm, grade, listEntry, listName, listUrl, qid, image, article,
architect, L (",group,group," for map filters), stories [{layer, text, source}].
"""
from datetime import datetime, timezone
from pathlib import Path
import json

from .common import load, log
from .s05_dates import info_for


def main(city_id):
    buildings = load(city_id, "buildings")
    base = load(city_id, "base")
    listing = load(city_id, "listing")
    wd = load(city_id, "wikidata")
    dates = load(city_id, "dates")
    lay = load(city_id, "layers")
    cur = load(city_id, "curated")
    # names for outlines that have none in OpenStreetMap: a story's name, then a named place inside
    fallback = {}
    for e in cur["entries"]:
        fallback.setdefault(str(e["b"]), e["name"])
    for pl in load(city_id, "places"):
        if pl["b"] is not None and pl["name"]:
            fallback.setdefault(str(pl["b"]), pl["name"])

    feats = []
    for i, b in enumerate(buildings):
        t, k = b["tags"], str(i)
        best = (listing.get(k) or [None])[0] or {}
        info = info_for(b, i, wd, listing) or {}
        d = dates.get(k, {})
        article = info.get("article")
        if not article and t.get("wikipedia", "").startswith("en:"):
            article = "https://en.wikipedia.org/wiki/" + t["wikipedia"][3:].replace(" ", "_")
        p = {
            "name": t.get("name") or info.get("label") or fallback.get(k) or best.get("Name"),
            "y": d.get("y"), "f": d.get("f"), "src": d.get("src"), "alts": d.get("alts"),
            "h": b["h"], "levels": t.get("building:levels"), "osm": b["osm"],
            "kind": t.get("building") if t.get("building") != "yes" else None,
            "grade": best.get("Grade"), "listEntry": best.get("ListEntry"), "listName": best.get("Name"),
            "listUrl": best.get("hyperlink"), "qid": info.get("qid") or t.get("wikidata"),
            "image": info.get("image"), "article": article, "architect": info.get("architect") or t.get("architect"),
            "L": ("," + ",".join(lay["member"][k]) + ",") if k in lay["member"] else None,
            "stories": lay["stories"].get(k),
        }
        p = {kk: v for kk, v in p.items() if v not in (None, "", [])}
        rings = b["rings"]
        geom = ({"type": "Polygon", "coordinates": [rings[0]]} if len(rings) == 1
                else {"type": "MultiPolygon", "coordinates": [[r] for r in rings]})
        feats.append({"type": "Feature", "properties": p, "geometry": geom})

    n = len(feats)
    dated = [d for d in dates.values()]
    stats = {
        "buildings": n, "dated": len(dated),
        "byPrecision": {f: sum(d["f"] == f for d in dated) for f in ("exact", "approx", "century")},
        "bySource": {s: sum(d["src"] == s for d in dated) for s in ("OpenStreetMap", "Wikipedia", "Wikidata")},
        "conflicts": sum("alts" in d for d in dated),
        "listed": sum(1 for es in listing.values() if es),
        "stories": len(cur["entries"]), "storiesDropped": len(cur["dropped"]),
    }
    fc = lambda f: {"type": "FeatureCollection", "features": f}  # noqa: E731
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = {"city": city_id, "built": built, "stats": stats, "layers": lay["meta"],
           "buildings": fc(feats), "roads": fc(base["roads"]), "water": fc(base["water"]), "parks": fc(base["parks"])}
    Path("data").mkdir(exist_ok=True)
    Path(f"data/{city_id}.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

    pct = lambda a: f"{100 * a / n:.1f}%" if n else "–"  # noqa: E731
    rows = [
        f"# Data report: {city_id}", "", f"Built {built} by the pipeline in `pipeline/`.", "",
        "## Construction years", "",
        "| | Buildings | Share |", "|---|---:|---:|",
        f"| All buildings | {n:,} | 100% |",
        f"| With a year | {stats['dated']:,} | {pct(stats['dated'])} |",
        *[f"| precision: {f} | {c:,} | {pct(c)} |" for f, c in stats["byPrecision"].items()],
        *[f"| source: {s} | {c:,} | {pct(c)} |" for s, c in stats["bySource"].items()],
        f"| sources disagree (all dates shown) | {stats['conflicts']:,} | {pct(stats['conflicts'])} |",
        "", "## Layers", "", "| Layer | Kind | Buildings |", "|---|---|---:|",
        *[f"| {L['title']} | {L['kind']} | {L['count']:,} |" for L in lay["meta"]],
        "", "## Stories dropped by the checks", "",
        *([f"- **{d['layer']} / {d['name']}**: {d['why']}" for d in cur["dropped"]] or ["None."]),
        "", "## Stories and how they were placed", "",
        *[f"- {e['layer']} / {e['name']}: {e['how']}" for e in cur["entries"]],
    ]
    Path(f"data/{city_id}-report.md").write_text("\n".join(rows) + "\n")
    log(f"s07 wrote data/{city_id}.json ({n} buildings, {stats['dated']} dated, {stats['stories']} stories)")
