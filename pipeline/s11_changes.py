"""What changed since the last build: buildings whose title, year or listing changed, and buildings that came or went.

The twice-yearly refresh brings in whatever OpenStreetMap, Historic England and the rest changed in six months; a
change to the code can rename buildings it was not meant to. Either way this list is what to look over.

Compares the published snapshot of the last build (data/<city>-snapshot.json, kept with the site so that even a
build that starts from nothing has it) with this build's. Writes data/<city>-changes.md and the new snapshot.
"""
import json
from pathlib import Path

from .common import load, log

SHOWN = 60          # rows per kind of change; the rest are counted


def title(n):
    if n.get("full") or n.get("name"):
        return n.get("full") or n["name"]
    w = n.get("where")
    return (w if w[0].isdigit() else f"A building on {w}") if w else "A building"


def snapshot(city_id):
    buildings, names, dates, listing = (load(city_id, k) for k in ("buildings", "names", "dates", "listing"))
    out = {}
    for i, b in enumerate(buildings):
        k = str(i)
        d, best = dates.get(k, {}), (listing.get(k) or [{}])[0]
        row = {"t": title(names.get(k, {}))}
        if d.get("y") is not None and d.get("f") != "area":
            row["y"] = d["y"]
        if best.get("Grade"):
            row["g"] = best["Grade"]
        out[b["osm"]] = row
    return out


def main(city_id):
    path = Path(f"data/{city_id}-snapshot.json")
    old = json.loads(path.read_text()) if path.exists() else None
    new = snapshot(city_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(new, separators=(",", ":"), ensure_ascii=False))
    link = lambda o: f"[{o}](https://www.openstreetmap.org/{o})"  # noqa: E731
    rows = [f"# Changes since the last build: {city_id}", ""]
    if old is None:
        rows.append("No earlier build to compare with.")
        Path(f"data/{city_id}-changes.md").write_text("\n".join(rows) + "\n")
        log("s11 changes: no earlier build to compare with")
        return
    kinds = {
        "Renamed": [(o, f"{old[o]['t']} → **{new[o]['t']}**") for o in new if o in old and old[o]["t"] != new[o]["t"]],
        "Year changed": [(o, f"{new[o]['t']}: {old[o].get('y', 'none')} → **{new[o].get('y', 'none')}**")
                         for o in new if o in old and old[o].get("y") != new[o].get("y")],
        "Listing changed": [(o, f"{new[o]['t']}: {old[o].get('g', 'not listed')} → **{new[o].get('g', 'not listed')}**")
                            for o in new if o in old and old[o].get("g") != new[o].get("g")],
        "New outlines": [(o, new[o]["t"]) for o in new if o not in old],
        "Gone": [(o, old[o]["t"]) for o in old if o not in new],
    }
    # named buildings first: those are the ones people see
    for k in kinds:
        kinds[k].sort(key=lambda r: (r[1].startswith("A building"), r[1]))
    rows += ["| | Buildings |", "|---|---:|", *[f"| {k} | {len(v):,} |" for k, v in kinds.items()], ""]
    for k, v in kinds.items():
        if not v:
            continue
        rows += [f"## {k}", ""] + [f"- {link(o)}: {text}" for o, text in v[:SHOWN]]
        if len(v) > SHOWN:
            rows.append(f"- … and {len(v) - SHOWN:,} more")
        rows.append("")
    Path(f"data/{city_id}-changes.md").write_text("\n".join(rows) + "\n")
    log("s11 changes: " + ", ".join(f"{len(v)} {k.lower()}" for k, v in kinds.items()))
