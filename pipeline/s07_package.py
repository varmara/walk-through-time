"""Write the files the page loads, and a data report.

  work/<city>/package.json  everything the page shows: buildings (GeoJSON with all attributes), base map, layers,
                            stats. Step s10_tiles turns it into what the page loads (tiles, a small index, card files).
  data/<city>-report.md   coverage of dates by precision and source, conflicts, layers, dropped stories

Building properties: name, y (year), f (exact | approx | century), src, alts [{y, f, src}],
h (height, m), base (bridges: deck height above the ground), levels, kind, osm, grade, listEntry, listName, listUrl, qid, image, article,
architect, L (",group,group," for map filters), stories [{layer, text, source}],
sum (one to three sentences) and sumSrc {title, url?, kind}.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import urllib.parse

from .common import building_name, load, log, save, work
from .s05_dates import info_for, osm_article


def main(city_id):
    buildings = load(city_id, "buildings")
    base = load(city_id, "base")
    listing = load(city_id, "listing")
    wd = load(city_id, "wikidata")
    dates = load(city_id, "dates")
    lay = load(city_id, "layers")
    cur = load(city_id, "curated")
    sums = load(city_id, "summaries") if work(city_id, "summaries").exists() else {}
    photos = load(city_id, "photos") if work(city_id, "photos").exists() else {}
    dyk = {}
    for e in cur["entries"]:
        if e["layer"] == "facts" and e["b"] is not None:
            dyk.setdefault(str(e["b"]), []).append({"text": e["story"], "source": e["source"]})
    commons = lambda f: "http://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(f.replace(" ", "_"))  # noqa: E731
    # names for outlines that have none in OpenStreetMap: a story's name, then a named place inside
    fallback, story_name = {}, {}
    for e in cur["entries"]:
        if e.get("layer") != "people":      # a person's name is not the building's
            story_name.setdefault(str(e["b"]), e["name"])
    for k, v in lay.get("names", {}).items():   # plaque addresses
        fallback.setdefault(k, v)
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
        if not article and osm_article(t):
            article = "https://en.wikipedia.org/wiki/" + osm_article(t).replace(" ", "_")
        name, today = building_name(t, story_name.get(k), info.get("label"), best.get("Name"), fallback.get(k))
        p = {
            "name": name or best.get("Name"), "today": today,
            "y": d.get("y"), "f": d.get("f"), "src": d.get("src"), "alts": d.get("alts"),
            "per": d.get("period"), "sh": d.get("share"), "dt": d.get("text"),
            "h": b["h"], "base": b.get("base"), "levels": t.get("building:levels"), "osm": b["osm"],
            "kind": t.get("building") if t.get("building") != "yes" else None,
            "grade": best.get("Grade"), "listEntry": best.get("ListEntry"), "listName": best.get("Name"),
            "listUrl": best.get("hyperlink"), "qid": info.get("qid") or t.get("wikidata"),
            "image": info.get("image") or ((photos.get(k) or {}).get("photo") and commons(photos[k]["photo"]["file"])),
            "credit": None if info.get("image") else (photos.get(k) or {}).get("photo"),
            "archive": (photos.get(k) or {}).get("archive"), "dyk": dyk.get(k), "article": article, "architect": info.get("architect") or t.get("architect"),
            "L": ("," + ",".join(lay["member"][k]) + ",") if k in lay["member"] else None,
            "stories": lay["stories"].get(k),
            "sum": (sums.get(k) or {}).get("text"), "sumSrc": (sums.get(k) or {}).get("src"),
        }
        p = {kk: v for kk, v in p.items() if v not in (None, "", [])}
        rings = b["rings"]
        geom = ({"type": "Polygon", "coordinates": [rings[0]]} if len(rings) == 1
                else {"type": "MultiPolygon", "coordinates": [[r] for r in rings]})
        feats.append({"type": "Feature", "properties": p, "geometry": geom})

    n = len(feats)
    dated = [d for d in dates.values() if d["f"] != "area"]
    estimated = sum(1 for d in dates.values() if d["f"] == "area")
    stats = {
        "buildings": n, "dated": len(dated),
        "byPrecision": {f: sum(d["f"] == f for d in dated) for f in ("exact", "approx", "century")},
        "bySource": {s: sum(d["src"] == s for d in dated) for s in ("OpenStreetMap", "Wikipedia", "Wikidata")},
        "conflicts": sum("alts" in d for d in dated), "estimated": estimated,
        "listed": sum(1 for es in listing.values() if es),
        "stories": len(cur["entries"]), "storiesDropped": len(cur["dropped"]),
    }
    fc = lambda f: {"type": "FeatureCollection", "features": f}  # noqa: E731
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nature = load(city_id, "nature") if work(city_id, "nature").exists() else []
    # areas drawn on the ground (nature and conservation areas) travel together; "t" says which kind
    nature += load(city_id, "conservation") if work(city_id, "conservation").exists() else []
    pins = [{"type": "Feature", "properties": {"i": k, **{kk: v for kk, v in pn.items() if kk not in ("x", "y")}},
             "geometry": {"type": "Point", "coordinates": [pn["x"], pn["y"]]}} for k, pn in enumerate(lay.get("pins", []))]
    out = {"city": city_id, "built": built, "stats": stats, "layers": lay["meta"], "nature": fc(nature), "pins": fc(pins),
           "people": lay.get("people", {}),
           "buildings": fc(feats), "roads": fc(base["roads"]), "water": fc(base["water"]), "parks": fc(base["parks"])}
    Path("data").mkdir(exist_ok=True)
    save(city_id, "package", out)

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
        f"| no date, area estimate from Council Tax | {estimated:,} | {pct(estimated)} |",
        "", "## Layers", "", "| Section | Layer | Group | Count |", "|---|---|---|---:|",
        *[f"| {L['section']} | {L['title']} | {g['title']} | {g['count']:,} |" for L in lay["meta"] for g in L["groups"]],
        "", "## Stories dropped by the checks", "",
        *([f"- **{d['layer']} / {d['name']}**: {d['why']}" for d in cur["dropped"]] or ["None."]),
        "", "## Stories and how they were placed", "",
        *[f"- {e['layer']} / {e['name']}: {e['how']}" for e in cur["entries"]],
    ]
    Path(f"data/{city_id}-report.md").write_text("\n".join(rows) + "\n")
    log(f"s07 packaged ({n} buildings, {stats['dated']} dated, {stats['stories']} stories)")
