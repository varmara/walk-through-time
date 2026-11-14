"""Notes (stories/<city>/notes/**/*.md): stories, events and people written one per file, as in an Obsidian vault.

A note is Markdown with properties at the top (YAML) and its text below. Its name is its file's name.

    ---
    type: event                     person | event | story
    layer: civic                    the story layer it is told in (events: the Events layer if none)
    source: https://en.wikipedia.org/wiki/1831_reform_riots      one page or a list; Wikipedia pages are checked,
                                                                 another site's needs read: (the date it was read)
    check: 8 October 1831 | Lowe's Silk Mill                     words the sources must contain, between them
    at:                             its places, one or more:
      - https://www.openstreetmap.org/way/16459858               a building
      - Lowe's Silk Mill, 52.9265, -1.2165                       a new pin: its name, latitude, longitude
      - Bendigo's tomb                                           a pin another note made
      - from the article                                         a pin at the source article's coordinates
    ---
    When the Lords threw out the Reform Bill, a crowd burned [Nottingham Castle](https://www.openstreetmap.org/way/16459858),
    the house of the [[Henry Pelham-Clinton, 4th Duke of Newcastle|Duke of Newcastle]].[^castle]

    > [!fact]
    > at: https://www.openstreetmap.org/way/…        (optional: the note's own places, else)
    > source: …                                      (optional: the note's own, else)
    > check: …
    >
    > A short fact, shown under "Did you know?".

    [^castle]: https://en.wikipedia.org/wiki/Nottingham_Castle — check: 1878 | museum

A person note (type: person) may also give `kind:` (writers, sport…: else Wikidata's occupation decides) and
`wikipedia:` (the article whose opening starts their card, or `no`); its `at:` places are those its text is about
(a home, a tomb). [[Links]] go to other notes or to people on the map; links to buildings are OpenStreetMap links.

load() turns notes into the same entries the story files give (stories_md.layer), so they are checked and placed
the same way (step s04)."""
import re
import urllib.parse
from pathlib import Path

import yaml

TYPES = ("person", "event", "story")
OSM = re.compile(r"^https?://(?:www\.)?openstreetmap\.org/(way|node|relation)/(\d+)")
NHLE = re.compile(r"^https?://historicengland\.org\.uk/listing/the-list/list-entry/(\d+)")
WIKI = re.compile(r"^https?://([a-z]+)\.(?:m\.)?wikipedia\.org/wiki/([^#?]+)")
PIN = re.compile(r"^(.+?),\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)$")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
MDLINK = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")
FOOTNOTE_DEF = re.compile(r"^\[\^([\w-]+)\]:\s*(.+)$")


class NoteError(ValueError):
    pass


def ref(src):
    """A source as the build names it: 'en:Title' (Wikipedia), 'he:123' (Historic England), 'web:https://…'
    (another site, read by hand). Accepts the page's address, or those forms as they are."""
    s = str(src).strip()
    if m := WIKI.match(s):
        return f"{m[1]}:{urllib.parse.unquote(m[2]).replace('_', ' ')}"
    if m := NHLE.match(s):
        return f"he:{m[1]}"
    if s.startswith(("http://", "https://")):
        return "web:" + s
    return s


def inline(text):
    """Text as shown, with its links: [[Note|shown]] -> 'shown' (the note's name kept in links, and
    ['shown', 'note:Note'] in weblinks, so the card links those words), [words](url) -> 'words' (kept in weblinks: an
    OpenStreetMap link opens that building). Footnote marks [^k] stay."""
    links, web = [], []

    def wl(m):
        links.append(m[1].strip())
        web.append([(m[2] or m[1]).strip(), "note:" + m[1].strip()])
        return (m[2] or m[1]).strip()

    def ml(m):
        web.append([m[1], m[2]])
        return m[1]
    return MDLINK.sub(ml, WIKILINK.sub(wl, text)), list(dict.fromkeys(links)), web


def listed(v):
    if v is None:
        return []
    return [str(x).strip() for x in (v if isinstance(v, list) else [v]) if str(x).strip()]


def checks(v):
    return tuple(x.strip() for x in (" | ".join(listed(v))).split(" | ") if x.strip())


def split(path):
    """(properties, body) of a note."""
    raw = Path(path).read_text()
    if raw.startswith("---\n"):
        head, _, body = raw[4:].partition("\n---")
        try:
            props = yaml.safe_load(head) or {}
        except yaml.YAMLError as e:
            raise NoteError(f"{Path(path).name}: its properties are not valid YAML ({e.problem})") from e
        return props, body.lstrip("-").lstrip("\n")
    return {}, raw


def body_parts(body, name):
    """The note's text (paragraphs joined by blank lines), its fact callouts and its footnotes."""
    lines, facts, notes = [], [], {}
    i, src = 0, body.splitlines()
    while i < len(src):
        line = src[i]
        if m := FOOTNOTE_DEF.match(line.strip()):
            parts = [p.strip() for p in re.split(r"\s+[—–]\s+", m[2])]
            fn = {"source": ref(parts[0])}
            for p in parts[1:]:
                k, _, v = p.partition(":")
                if k.strip() not in ("check", "read", "title"):
                    raise NoteError(f"{name}: footnote [^{m[1]}]: '{k.strip()}' is not check, read or title")
                fn[k.strip()] = checks(v) if k.strip() == "check" else v.strip()
            notes[m[1]] = fn
            i += 1
            continue
        if re.match(r"^>\s*\[!fact\]", line.strip(), re.I):
            block = []
            i += 1
            while i < len(src) and src[i].lstrip().startswith(">"):
                block.append(src[i].lstrip()[1:].strip())
                i += 1
            props, text = {}, []
            for b in block:
                m = re.match(r"^(at|source|check|read|title):\s*(.*)$", b)
                if m and not text:
                    if m[1] == "at":
                        props.setdefault("at", []).append(m[2])
                    else:
                        props[m[1]] = m[2]
                elif b or text:
                    text.append(b)
            if not "".join(text).strip():
                raise NoteError(f"{name}: a fact callout with no text")
            facts.append({**props, "text": " ".join(t for t in text if t)})
            continue
        lines.append(line)
        i += 1
    paras = [" ".join(x.strip() for x in p.splitlines() if x.strip()) for p in re.split(r"\n\s*\n", "\n".join(lines))]
    return "\n\n".join(p for p in paras if p and not p.startswith("#")), facts, notes


def place(a, name, pins):
    """One `at:` item -> (at as the build writes it, where: the pin's name or None). pins: name -> (lon, lat)."""
    a = str(a).strip()
    if m := OSM.match(a):
        return f"osm:{m[1]}/{m[2]}", None
    if m := NHLE.match(a):
        return f"nhle:{m[1]}", None
    if a.lower() in ("from the article", "the article"):
        return "pin:article", None
    if m := PIN.match(a):
        lat, lon = float(m[2]), float(m[3])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise NoteError(f"{name}: at: '{a}': latitude, then longitude")
        return f"pin:{lon},{lat}", m[1].strip()
    if a in pins:
        return f"pin:{pins[a][0]},{pins[a][1]}", a
    raise NoteError(f"{name}: at: '{a}' is not an OpenStreetMap link, a new pin (name, latitude, longitude), "
                    f"'from the article', or the name of a pin another note made")


def read_notes(folder):
    """[(name, properties, body)] of every note under the folder, by file name; two notes of one name fail."""
    out, seen = [], {}
    for p in sorted(Path(folder).rglob("*.md")):
        if p.name.lower() == "readme.md" or any(part.startswith(".") for part in p.parts):
            continue
        if p.stem in seen:
            raise NoteError(f"two notes are called {p.stem!r} ({seen[p.stem]} and {p.relative_to(folder)}): "
                            f"note names must differ, as in Obsidian")
        seen[p.stem] = p.relative_to(folder)
        props, body = split(p)
        out.append((p.stem, props, body))
    return out


def load(folder, layers):
    """Adds the notes' entries to the story layers (person notes to the People layer, fact callouts to the facts
    layer, events to their `layer`, or an Events layer made for them). Returns
    {"people": {name: {"wikipedia": title | False, "group"}}, "names": [note names]}.
    Raises NoteError naming the note for anything it cannot read."""
    folder = Path(folder)
    if not folder.is_dir():
        return {"people": {}, "names": []}
    notes = read_notes(folder)
    problems = []
    # pins first: a note may name a pin another note made
    pins = {}
    for name, props, body in notes:
        for a in listed(props.get("at")):
            if m := PIN.match(a):
                pname = m[1].strip()
                xy = (float(m[3]), float(m[2]))
                if pname in pins and pins[pname] != xy:
                    problems.append(f"{name}: the pin {pname!r} is made twice, at different points")
                pins[pname] = xy
    by_id = {L.get("id"): L for L in layers}
    people_layer = next((L for L in layers if L.get("kind") == "people"), None)
    facts_layer = next((L for L in layers if L.get("kind") == "facts"), None)
    info = {}
    for name, props, body in notes:
        try:
            kind = props.get("type")
            if kind not in TYPES:
                raise NoteError(f"{name}: type: must be one of {', '.join(TYPES)}")
            text, facts, fns = body_parts(body, name)
            story, links, web = inline(text)
            for k in re.findall(r"\[\^([\w-]+)\]", story):
                if k not in fns:
                    raise NoteError(f"{name}: footnote [^{k}] has no line '[^{k}]: …' below the text")
            sources = [ref(s) for s in listed(props.get("source"))]
            if not sources and story:
                raise NoteError(f"{name}: no source: for its text")
            places = [place(a, name, pins) for a in listed(props.get("at"))]
            base = {"name": name, "note": name, "source": sources[0] if sources else None, "sources": sources[1:],
                    "facts": checks(props.get("check")), "story": story, "links": links, "weblinks": web,
                    "cites": {k: fns[k] for k in fns}, "type": kind,
                    **({"read": str(props["read"])} if props.get("read") else {}),
                    **({"title": str(props["title"])} if props.get("title") else {}),
                    **({"year": str(props["year"])} if props.get("year") else {}),
                    # other stories to link from this one, as see: in a story file (also [[links]] in its text)
                    **({"see": [WIKILINK.sub(lambda m: m[1], s) for s in listed(props.get("see"))]} if props.get("see") else {}),
                    **({"names": False} if props.get("names") is False or str(props.get("names")).lower() == "no" else {})}
            if kind == "person":
                if people_layer is None:
                    raise NoteError(f"{name}: a person note, but there is no People layer (kind: people)")
                wp = props.get("wikipedia")
                info[name] = {"wikipedia": False if str(wp).lower() in ("no", "false") else
                              (ref(wp)[3:] if wp and ref(wp).startswith("en:") else None),
                              **({"group": str(props["kind"])} if props.get("kind") else {})}
                target, group = people_layer, props.get("kind")
            else:
                lid = props.get("layer") or "events"
                if lid not in by_id:
                    if props.get("layer"):
                        raise NoteError(f"{name}: layer: {lid!r} is not a story layer's id")
                    by_id[lid] = {"id": "events", "title": "Events", "intro": "Events in the city's history, "
                                  "each at the places where it happened, with the people who took part.", "entries": []}
                    layers.append(by_id[lid])
                target, group = by_id[lid], props.get("group")
            base = {k: v for k, v in base.items() if v not in ((), [], {}, None) or k in ("name", "story")}
            if story:
                if not places and kind != "person":
                    raise NoteError(f"{name}: no at: (its places)")
                for at, where in places or [(None, None)]:
                    e = {**base, **({"group": str(group)} if group else {})}
                    if at:
                        e["at"] = at
                    else:
                        e["unplaced"] = True        # a person's own text, on their card only
                    if where:
                        e["where"] = where
                    target["entries"].append(e)
            for f in facts:
                if facts_layer is None:
                    raise NoteError(f"{name}: a fact callout, but there is no facts layer (kind: facts)")
                fsrc = [ref(f["source"])] if f.get("source") else sources
                if not fsrc:
                    raise NoteError(f"{name}: a fact callout with no source, in a note with none")
                ftext, flinks, fweb = inline(f["text"])
                fplaces = [place(a, name, pins) for a in f.get("at", [])] or places
                fe = {"name": name, "note": name, "source": fsrc[0], "sources": fsrc[1:],
                      "facts": checks(f.get("check")),
                      "story": ftext, "links": flinks, "weblinks": fweb, "cites": {},
                      **({"read": f.get("read") or base.get("read")} if f.get("read") or base.get("read") else {}),
                      **({"title": f["title"]} if f.get("title") else {})}
                if kind == "person" and not f.get("at"):
                    facts_layer["entries"].append({**fe, "who": name, "unplaced": True})
                else:
                    if not fplaces:
                        raise NoteError(f"{name}: a fact callout with no at:, in a note with no places")
                    for at, where in fplaces:
                        facts_layer["entries"].append({**fe, "at": at, **({"where": where} if where else {})})
        except NoteError as e:
            problems.append(str(e))
    if problems:
        raise NoteError("notes: " + "; ".join(problems))
    return {"people": info, "names": [n for n, _, _ in notes]}
