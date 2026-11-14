"""Read a city's stories from Markdown files (stories/<city>/), written to be edited by hand.

A story layer is one file, `NN-<id>.md` (NN sets the order):

    # Old inns                        <- the layer's title
    id: inns                          <- settings, one per line (id; kind: people or facts for those layers)
    groups: inns-old = The oldest | inns-coaching = Coaching inns
                                      <- optional: the layer's tickboxes, key = title; each entry names its group

    The layer's introduction: one paragraph, as many lines as you like.

    ## Ye Olde Trip to Jerusalem      <- an entry: the place, person or fact's name
    - source: en:Ye Olde Trip to Jerusalem      (the Wikipedia article it rests on; a person's, for People; or
                                                 he:1254566; or web:https://… for another site's page, read
                                                 once by hand: then also read: 2026-11-14 and title: the page's)
    - place: en:Nottingham Castle               (People: the place's article)
    - at: name:Ye Olde Trip to Jerusalem        (where, if not where the article says: name:, osm:, nhle:, pin:lon,lat,
                                                 pin:article for a pin at the article's coordinates)
    - year: c. 1650                             (when the building standing today was built)
    - group: sport                              (People: the kind of person, if Wikidata has none; a layer
                                                 with groups: the entry's group key)
    - see: The castle burned, 1831 | culture/Nottingham Castle
                                                (other stories to link from this one: their headings, or
                                                 layer/heading where a heading is used twice)
    - quote: …                                  (passages copied from a Historic England entry, one per line)
    - names: no                                 (the entry's name is not the building's name)
    - check: 1189 | caves                       (words the article must contain, separated by |)
    - note: …                                   (for editors only: why, where from; not shown)

    The story: one or two plain sentences, any number of lines.

Corrections and links are tables, one file each (names.md, titles.md, wikipedia.md, plaques.md, tags.md,
collections.md, credits.md); each has a Note column for why. See stories/<city>/README.md.
"""
import re
from pathlib import Path

ENTRY_KEYS = {"source", "place", "at", "year", "group", "quote", "names", "check", "note", "architect", "see", "read",
              "title", "where"}


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


def layer(path):
    lines = Path(path).read_text().splitlines()
    L, entries, cur, intro, body = {}, [], None, [], []

    def close():
        if cur is not None:
            # [[links]] to people and notes, and [words](url) links, as in a note (pipeline/notes.py)
            from .notes import inline
            cur["story"], cur["links"], cur["weblinks"] = inline(" ".join(body).strip())
            entries.append(cur)

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("# ") and "title" not in L:
            L["title"] = line[2:].strip()
        elif line.startswith("## "):
            close()
            cur, body = {"name": line[3:].strip()}, []
        elif cur is None:
            m = re.match(r"^(id|kind|groups):\s*(.+)$", line)
            if m and not intro and m[1] == "groups":     # "key = Title | key = Title"
                L["groups"] = [[k.strip(), t.strip()] for k, _, t in (g.partition("=") for g in m[2].split(" | "))]
            elif m and not intro:
                L[m[1]] = m[2].strip()
            elif line.strip():
                intro.append(line.strip())
        else:
            m = re.match(r"^- (\w+):\s*(.*)$", line)
            if m and m[1] in ENTRY_KEYS and not body:
                k, v = m[1], m[2].strip()
                if k == "note":          # for whoever edits the file: why, where from
                    pass
                elif k == "check":
                    cur["facts"] = tuple(x.strip() for x in v.split(" | ") if x.strip())
                elif k == "quote":       # passages copied from a source that cannot be read automatically
                    cur.setdefault("quote", []).append(v)
                elif k == "architect":
                    cur["architect"] = architects(v)
                elif k == "see":
                    cur["see"] = [x.strip() for x in v.split(" | ") if x.strip()]
                elif k == "names":
                    if v.lower() in ("no", "false"):
                        cur["names"] = False
                else:
                    cur[k] = v
            elif line.strip():
                body.append(line.strip())
    close()
    L["intro"] = " ".join(intro)
    L["entries"] = entries
    return L


TOPIC_KINDS = ("story", "person", "plaque", "building")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def topic(path):
    """A topic (topics/<id>.md): stories, people, plaques and buildings from anywhere on the map, on one subject.

        # Riot, rebellion and war         <- the topic's title
        id: war

        The topic's introduction: one paragraph.

        ## The Civil War                  <- optional: a sub-group (a tickbox of its own)
        - story: The storming of Shelford House     (a story, by its heading, or layer/heading)
        - person: Colonel Hutchinson                (someone in the People layer, by name: all their places)
        - plaque: Plaque to Albert Ball             (a plaque, by its title on the map)
        - building: way/80847199                    (a building, by its OpenStreetMap id)
        - note: …                                   (for editors only)

    Anything can be in several topics. The build fails if a line finds nothing, or more than one thing."""
    T, intro, group, problems = {"groups": [], "members": []}, [], None, []
    for n, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if raw.startswith("# ") and "title" not in T:
            T["title"] = line[2:].strip()
        elif raw.startswith("## "):
            group = line[3:].strip()
            T["groups"].append(group)
        elif m := re.match(r"^- (\w+):\s*(.+)$", line):
            if m[1] == "note":
                continue
            if m[1] not in TOPIC_KINDS:
                problems.append(f"{Path(path).name}:{n}: '{m[1]}:' is not one of {', '.join(TOPIC_KINDS)}")
                continue
            T["members"].append({"kind": m[1], "name": m[2].strip(), "group": group, "line": f"{Path(path).name}:{n}"})
        elif (m := re.match(r"^id:\s*(\S+)$", line)) and not intro and not T["members"]:
            T["id"] = m[1]
        elif not T["groups"] and not T["members"]:
            intro.append(line)
        else:
            problems.append(f"{Path(path).name}:{n}: not a member line ('- story: …', '- person: …', …): {line[:60]}")
    T.setdefault("id", Path(path).stem)
    T.setdefault("title", T["id"])
    T["intro"] = " ".join(intro)
    if problems:
        raise ValueError("topics: " + "; ".join(problems))
    return T


def load(folder):
    """Everything a city's stories folder holds: CURATED, TOPICS and the correction tables."""
    folder = Path(folder)
    curated = [layer(p) for p in sorted(folder.glob("[0-9][0-9]-*.md"))]
    out = {"CURATED": curated}
    # notes (notes/**/*.md): people, events and stories one per file, added to the layers' entries
    from . import notes
    out["NOTES"] = notes.load(folder / "notes", curated)
    out["TOPICS"] = [topic(p) for p in sorted((folder / "topics").glob("*.md")) if p.name.lower() != "readme.md"]
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
    # who each plaque remembers (plaque-people.md), and summaries for people with no Wikipedia article (about.md)
    f = folder / "plaque-people.md"
    out["PLAQUE_PEOPLE"] = {r["inscription starts"]: {"people": [n.strip() for n in r["people"].split(" & ") if n.strip()],
                                                      **({"group": r["group"]} if r.get("group") else {})}
                            for r in (table(f) if f.exists() else []) if r.get("people")}
    f = folder / "about.md"
    out["ABOUT"] = {r["name"]: {"text": r["who"], "url": r["source"], "read": r.get("read") or None}
                    for r in (table(f) if f.exists() else []) if r.get("name") and r.get("who") and r.get("source")}
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
