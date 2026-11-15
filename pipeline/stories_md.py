"""Read a city's stories (stories/<city>/), written to be edited by hand.

Stories, events, people and the layers' indexes are notes, one Markdown file each in notes/, as in an Obsidian
vault (read by pipeline/notes.py, which says how to write them). Corrections and links to the open data are
tables, one file each beside notes/ (names.md, titles.md, wikipedia.md, plaques.md, plaque-people.md, tags.md,
collections.md, credits.md, architects.md); each has a Note column for why. See stories/<city>/README.md.
"""
import re
from pathlib import Path

def architects(v):
    """`en:Thomas Rickman | Vincent Harris = en:E. Vincent Harris` -> [[name, article], ...]: the name as the story
    writes it, and the architect's Wikipedia article (a bare name: found by name, like a plaque's person)."""
    out = []
    for part in (x.strip() for x in v.split(" | ")):
        name, _, art = part.partition("=") if "=" in part else ("", "", part)
        art = art.strip()
        title = art[3:].strip() if art.startswith("en:") else None
        name = name.strip() or re.sub(r"\s*\(.*\)$", "", title or art)
        if name:
            out.append([name, title])
    return out


def _cell(s):
    return s.strip().replace("\\|", "|")


def table(path):
    """Rows of a Markdown table as dicts, keyed by the header's words in lower case."""
    rows, head = [], None
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [_cell(c) for c in re.split(r"(?<!\\)\|", line.strip("|"))]
        if head is None:
            head = [c.lower() for c in cells]
        elif not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            rows.append(dict(zip(head, cells)))
    return rows


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load(folder):
    """Everything a city's stories folder holds: CURATED (the story layers, with the People and facts layers, and
    their entries), TOPICS, NOTES (who the person notes are, and every note's name) and the correction tables."""
    folder = Path(folder)
    from . import notes
    n = notes.load(folder / "notes")
    out = {"CURATED": n["layers"], "TOPICS": n["topics"], "NOTES": {"people": n["people"], "names": n["names"]}}
    f = folder / "wikipedia.md"
    out["WIKIPEDIA"] = {r["name on plaque"]: r["wikipedia article"] for r in table(f)} if f.exists() else {}
    for name, key in (("names.md", "NAMES"), ("titles.md", "TITLES")):
        f = folder / name
        out[key] = {r["outline"]: r[key.lower()[:-1]] for r in table(f)} if f.exists() else {}
    plaques = {}
    f = folder / "plaques.md"
    for r in (table(f) if f.exists() else []):
        fix = {k: r[k] for k in ("label", "group", "type") if r.get(k)}
        plaques[r["inscription starts, or subject"]] = fix
    out["PLAQUES"] = plaques
    # who each plaque remembers (plaque-people.md)
    f = folder / "plaque-people.md"
    out["PLAQUE_PEOPLE"] = {r["inscription starts"]: {"people": [n.strip() for n in r["people"].split(" & ") if n.strip()],
                                                      **({"group": r["group"]} if r.get("group") else {})}
                            for r in (table(f) if f.exists() else []) if r.get("people")}
    tags = {}
    f = folder / "tags.md"
    for r in (table(f) if f.exists() else []):
        tags.setdefault(r["outline"], {})[r["tag"]] = None if r["value"] == "(remove)" else r["value"]
    out["TAG_FIXES"] = tags
    colls = []
    f = folder / "collections.md"
    for r in (table(f) if f.exists() else []):
        c = {"title": r["title"], "url": r["url"]}
        for col, key in (("areas", "areas"), ("names", "names"), ("layers", "layers"), ("people", "who")):
            vals = [v.strip() for v in r.get(col, "").split(";") if v.strip()]
            if vals:
                c[key] = vals
        colls.append(c)
    out["COLLECTIONS"] = colls
    f = folder / "credits.md"
    out["CREDITS"] = {r["site"]: r["credit"] for r in table(f)} if f.exists() else {}
    f = folder / "architects.md"
    out["ARCHITECTS"] = {r["name in openstreetmap"]: {k: r[k2] for k, k2 in (("name", "architect"), ("article", "wikipedia article"),
                                                                                   ("source", "other source"))
                                                      if r.get(k2)} for r in table(f)} if f.exists() else {}
    return out
