"""One-off: the hand-written People entries (stories/<city>/NN-people.md) as person notes (notes/people/*.md).

Each entry's place is written as the build last placed it (work/<city>/curated.json): a building's OpenStreetMap
link, or its pin by name, latitude and longitude. Run once, after tools/fetch-built.sh work."""
import json
import sys
import urllib.parse
from pathlib import Path

from pipeline import stories_md


def url(ref):
    if ref.startswith("en:"):
        return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(ref[3:].replace(" ", "_"), safe="(),'")
    if ref.startswith("he:"):
        return f"https://historicengland.org.uk/listing/the-list/list-entry/{ref[3:]}"
    return ref[4:] if ref.startswith("web:") else ref


def q(s):
    """A YAML value, quoted only when it has to be (so it reads as plainly in Obsidian)."""
    s = str(s)
    plain = s == s.strip() and s and s[0] not in "'\"[]{}|>&*!%@`#,?:-" and ": " not in s and " #" not in s
    return s if plain else json.dumps(s, ensure_ascii=False)


def main(city):
    folder = Path("stories") / city
    f = next(folder.glob("[0-9][0-9]-people.md"))
    L = stories_md.layer(f)
    cur = json.load(open(f"work/{city}/curated.json"))
    blds = json.load(open(f"work/{city}/buildings.json"))
    placed = {}
    for e in cur["entries"]:
        if e["layer"] == L["id"]:
            placed.setdefault((e["name"], e["story"]), e)
    notes = {}
    for e in L["entries"]:
        r = placed.get((e["name"], e["story"]))
        if r is None:
            sys.exit(f"{e['name']}: not placed in the last build")
        at = f"https://www.openstreetmap.org/{blds[r['b']]['osm']}" if r["b"] is not None else \
            f"{r.get('where') or e.get('where')}, {round(r['pin'][1], 6)}, {round(r['pin'][0], 6)}"
        n = notes.setdefault(e["name"], {"source": [], "check": [], "at": [], "text": [], "props": {}})
        for s in filter(None, (e["source"], e.get("place"))):
            if url(s) not in n["source"]:
                n["source"].append(url(s))
        n["check"] += [c for c in e.get("facts", ()) if c not in n["check"]]
        n["at"].append(at)
        n["text"].append(e["story"])
        for k in ("group", "read", "title", "year", "note"):
            if e.get(k):
                n["props"]["kind" if k == "group" else k] = e[k]
        if e.get("names") is False:
            n["props"]["names"] = "no"
    out = folder / "notes" / "people"
    out.mkdir(parents=True, exist_ok=True)
    for name, n in notes.items():
        lines = ["---", "type: person"]
        if "kind" in n["props"]:
            lines.append(f"kind: {n['props']['kind']}")
        lines += (["source:"] + [f"  - {q(s)}" for s in n["source"]]) if len(n["source"]) > 1 else [f"source: {q(n['source'][0])}"]
        for k in ("title", "read", "year", "names"):
            if k in n["props"]:
                lines.append(f"{k}: {q(n['props'][k])}")
        if n["check"]:
            lines.append(f"check: {q(' | '.join(n['check']))}")
        lines += ["at:"] + [f"  - {q(a)}" for a in n["at"]]
        if "note" in n["props"]:
            lines.append(f"note: {q(n['props']['note'])}")
        lines += ["---", ""] + ["\n".join(wrap(t)) + "\n" for t in n["text"]]
        (out / f"{name}.md").write_text("\n".join(lines).rstrip("\n") + "\n")
    print(f"{len(notes)} person notes from {len(L['entries'])} entries")


def wrap(t, width=116):
    out, line = [], ""
    for w in t.split():
        if line and len(line) + 1 + len(w) > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return out + [line]


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "nottingham")
