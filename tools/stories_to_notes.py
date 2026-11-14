"""One-off: the story layers' entries (stories/<city>/NN-*.md) and the "Did you know" facts as notes.

Each story becomes notes/stories/<name>.md (type: story, layer: …), placed where the last build placed it
(work/<city>/curated.json): a building's OpenStreetMap link, or its pin by name, latitude and longitude. Two
stories of one name in one layer (two passages on one building) are one note, the second resting on its own
source as a footnote; in two layers, the file names say where ("St Mary's Church, Clifton") and name: keeps the
name shown. Each fact becomes a [!fact] callout in the note of a story on its building, or in "Did you know"
when there is none. The layer files keep their title, settings and introduction.

Run once, after tools/fetch-built.sh work:  PYTHONPATH=. python tools/stories_to_notes.py nottingham"""
import json
import sys
import urllib.parse
from pathlib import Path

from pipeline import stories_md

KEYS = ("group", "read", "title", "year", "note")
# file names for stories that share a name across layers, where the layer's title does not say where
RENAME = {("churches", "St Mary's Church"): "St Mary's Church, Nottingham", ("clifton", "St Mary's Church"): "St Mary's Church, Clifton"}


def url(ref):
    if ref.startswith("en:"):
        return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(ref[3:].replace(" ", "_"), safe="(),'")
    if ref.startswith("he:"):
        return f"https://historicengland.org.uk/listing/the-list/list-entry/{ref[3:]}"
    return ref[4:] if ref.startswith("web:") else ref


def q(s):
    """A YAML value, quoted only when it has to be (so it reads as plainly in Obsidian)."""
    s = str(s)
    plain = s == s.strip() and s and s[0] not in "'\"[]{}|>&*!%@`#,?:-" and ": " not in s and " #" not in s \
        and not s.replace(".", "").isdigit() and s.lower() not in ("yes", "no", "true", "false", "null", "on", "off")
    return s if plain else json.dumps(s, ensure_ascii=False)


def wrap(t, width=116, lead=""):
    out, line = [], ""
    for w in t.split():
        if line and len(lead) + len(line) + 1 + len(w) > width:
            out.append(lead + line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return out + [lead + line]


def architect_text(arch):
    return " | ".join(f"{n} = en:{t}" if t and n != t.split(" (")[0] else (f"en:{t}" if t else n) for n, t in arch)


def main(city):
    folder = Path("stories") / city
    cur = json.load(open(f"work/{city}/curated.json"))
    blds = json.load(open(f"work/{city}/buildings.json"))
    placed = {}
    for e in cur["entries"]:
        placed.setdefault((e["layer"], e["name"], e["story"]), e)
    files = [p for p in sorted(folder.glob("[0-9][0-9]-*.md"))]
    layers = [(p, stories_md.layer(p)) for p in files]
    names = {}                        # display name -> [layer ids]
    for _, L in layers:
        if L.get("kind") in ("people", "facts"):
            continue
        for e in L["entries"]:
            if L["id"] not in names.setdefault(e["name"], []):
                names[e["name"]].append(L["id"])
    taken = {p.stem for p in (folder / "notes").rglob("*.md")}

    def where_of(L, e):
        r = placed.get((L["id"], e["name"], e["story"]))
        if r is None:
            sys.exit(f"{L['id']} / {e['name']}: not placed in the last build")
        if r["b"] is not None:
            return f"https://www.openstreetmap.org/{blds[r['b']]['osm']}", ("b", r["b"])
        return f"{e.get('where') or e['name']}, {round(r['pin'][1], 6)}, {round(r['pin'][0], 6)}", ("p", tuple(r["pin"]))

    notes, at_place = {}, {}         # file name -> note; a place -> the notes on it
    for _, L in layers:
        if L.get("kind") in ("people", "facts"):
            continue
        for e in L["entries"]:
            fname = RENAME.get((L["id"], e["name"])) or (e["name"] if len(names[e["name"]]) == 1 else f"{e['name']}, {L['title']}")
            if fname in taken:
                sys.exit(f"{fname}: a note of that name exists already")
            at, key = where_of(L, e)
            srcs = [url(s) for s in filter(None, (e["source"], e.get("place")))]
            n = notes.get(fname)
            if n is None:
                n = notes[fname] = {"name": e["name"], "layer": L["id"], "source": srcs, "check": list(e.get("facts", ())),
                                    "at": [at], "text": [e["story"]], "props": {k: e[k] for k in KEYS if e.get(k)},
                                    "see": list(e.get("see", [])), "quote": list(e.get("quote", [])),
                                    "architect": e.get("architect"), "names": e.get("names", True),
                                    "facts": [], "footnotes": []}
            else:            # a second passage on the same place: its own source, as a footnote
                if at not in n["at"]:
                    sys.exit(f"{fname}: two stories of one name in {L['id']} at different places")
                k = f"{len(n['footnotes']) + 2}"
                n["footnotes"].append(f"[^{k}]: {' '.join(srcs[:1])}"
                                      + (f" — check: {' | '.join(e['facts'])}" if e.get("facts") else ""))
                if len(srcs) > 1:
                    n["source"] += [s for s in srcs[1:] if s not in n["source"]]
                n["text"].append(e["story"] + f"[^{k}]")
                n["see"] += [s for s in e.get("see", []) if s not in n["see"]]
                n["quote"] += e.get("quote", [])
                n["names"] = n["names"] and e.get("names", True)
            at_place.setdefault(key, []).append(fname)
    # facts: into a note on the same place, else "Did you know"
    facts_layer = next(L for _, L in layers if L.get("kind") == "facts")
    for e in facts_layer["entries"]:
        r = placed.get(("facts", e["name"], e["story"]))
        if r is None:
            sys.exit(f"facts / {e['name']}: not placed in the last build")
        key = ("b", r["b"]) if r["b"] is not None else ("p", tuple(r["pin"]))
        host = (at_place.get(key) or [None])[0]
        at = f"https://www.openstreetmap.org/{blds[r['b']]['osm']}" if r["b"] is not None else \
            f"{e['name']}, {round(r['pin'][1], 6)}, {round(r['pin'][0], 6)}"
        f = {"source": url(e["source"]), "check": list(e.get("facts", ())), "text": e["story"],
             "at": at if host is None or len(notes[host]["at"]) > 1 else None}
        (notes[host]["facts"] if host else notes.setdefault("Did you know", {"facts": [], "only_facts": True})["facts"]).append(f)

    out = folder / "notes" / "stories"
    out.mkdir(parents=True, exist_ok=True)
    for fname, n in notes.items():
        if n.get("only_facts"):
            lines = ["---", "type: story", "note: facts about buildings with no story of their own", "---", ""]
        else:
            lines = ["---", "type: story", f"layer: {n['layer']}"]
            if n["name"] != fname:
                lines.append(f"name: {q(n['name'])}")
            if n["props"].get("group"):
                lines.append(f"group: {n['props']['group']}")
            lines += (["source:"] + [f"  - {q(s)}" for s in n["source"]]) if len(n["source"]) > 1 else [f"source: {q(n['source'][0])}"]
            for k in ("title", "read", "year"):
                if k in n["props"]:
                    lines.append(f"{k}: {q(n['props'][k])}")
            if n["check"]:
                lines.append(f"check: {q(' | '.join(n['check']))}")
            if n["quote"]:
                lines += ["quote:"] + [f"  - {q(x)}" for x in n["quote"]]
            if n["architect"]:
                lines.append(f"architect: {q(architect_text(n['architect']))}")
            lines += ["at:"] + [f"  - {q(a)}" for a in n["at"]]
            if not n["names"]:
                lines.append("names: no")
            if n["see"]:
                lines += ["see:"] + [f"  - {q(s)}" for s in n["see"]]
            if "note" in n["props"]:
                lines.append(f"note: {q(n['props']['note'])}")
            lines += ["---", ""]
            for t in n["text"]:
                lines += wrap(t) + [""]
        for f in n["facts"]:
            lines += ["> [!fact]"] + ([f"> at: {f['at']}"] if f["at"] else []) + [f"> source: {f['source']}"] \
                + ([f"> check: {' | '.join(f['check'])}"] if f["check"] else []) + [">"] + wrap(f["text"], lead="> ") + [""]
        lines += n.get("footnotes", [])
        (out / f"{fname}.md").write_text("\n".join(lines).rstrip("\n") + "\n")
    # the layer files: title, settings and introduction only
    for p, L in layers:
        if L.get("kind") == "people":
            continue
        s = p.read_text()
        i = s.find("\n## ")
        if i >= 0:
            p.write_text(s[:i].rstrip() + "\n")
    print(f"{len(notes)} notes from {sum(len(L['entries']) for _, L in layers if L.get('kind') != 'people')} entries")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "nottingham")
