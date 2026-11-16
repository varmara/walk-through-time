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

from .stories_md import architects, slug

TYPES = ("person", "event", "story", "index")
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


SECTIONS = ("Places", "Threads")
ITEM_PLAQUE = re.compile(r"^plaque:\s*(.+)$")
# a date as a note's when: or a thread's line gives it: 1952, c. 1200, 1930s, 13th century
WHEN = r"(?:c\.\s*)?\d{3,4}s?|\d{1,2}(?:st|nd|rd|th) century"
ITEM_WHEN = re.compile(rf"^({WHEN}):\s+(.+)$")


def when(value, name, prop="when"):
    """A note's when: or made: as written ("c. 1200"), checked to be a date the build can order."""
    v = str(value).strip()
    if not re.fullmatch(WHEN, v):
        raise NoteError(f"{name}: {prop}: {v!r} is not a date: write 1952, c. 1200, 1930s or 13th century")
    return v


def index_layer(name, props, body):
    """An index note (type: index): a layer of the Layers sheet. Its text: the introduction, then `## Group`
    headings, each a tickbox, listing its members one per line:

        - [[Note]]                     a story or event (each is in at least one Places index), or in a thread
                                       also a person (a note, or someone on the map by name)
        - c. 1200: [[Note]]            in a thread: its date on this thread, where it differs from the note's own
        - plaque: Plaque to Albert Ball                                   a plaque, by its title (a topic)
        - [Wollaton Hall](https://www.openstreetmap.org/way/4438894)      a building (a topic)

    Properties: id (else from the file's name), section (Places, the default, or Threads), area (for a place: the
    heading it folds under in the Layers sheet, "The city", "South of the Trent"), order (its place in
    the section), kind (people or facts, for those layers, whose members are not listed). A group's key, which
    links and remembered tickboxes use, is the id and its heading: wilford-the-village."""
    L = {"id": str(props.get("id") or slug(name)), "title": str(props.get("title") or name), "note": name,
         "section": str(props.get("section") or "Places"), "order": props.get("order"),
         **({"area": str(props["area"])} if props.get("area") else {}),
         **({"kind": str(props["kind"])} if props.get("kind") else {}), "entries": [], "members": []}
    if L["section"] not in SECTIONS:
        raise NoteError(f"{name}: section: must be one of {', '.join(SECTIONS)}")
    intro, group, groups = [], None, []
    for n, raw in enumerate(body.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            group = line[3:].strip()
            groups.append([f"{L['id']}-{slug(group)}", group])
        elif line.startswith("- "):
            item, dated = line[2:].strip(), None
            if m := ITEM_WHEN.match(item):       # "- c. 1200: [[Statue of Robin Hood]]": its date on this thread
                dated, item = m[1], m[2].strip()
            if m := WIKILINK.fullmatch(item):
                member = {"kind": "note", "name": m[1].strip()}
            elif m := MDLINK.fullmatch(item):
                if not (o := OSM.match(m[2])):
                    raise NoteError(f"{name}: '{item}': a member links a note ([[…]]) or a building's OpenStreetMap page")
                member = {"kind": "building", "name": f"{o[1]}/{o[2]}"}
            elif m := ITEM_PLAQUE.match(item):
                member = {"kind": "plaque", "name": m[1].strip()}
            else:
                raise NoteError(f"{name}: '{item}' is not a member: [[Note]], plaque: Title, or [Name](OpenStreetMap link)")
            L["members"].append({**member, "group": group, "line": f"{name}:{n}", **({"when": dated} if dated else {})})
        elif group is None and not L["members"]:
            intro.append(line)
        else:
            raise NoteError(f"{name}: '{line[:60]}': below the introduction, only ## groups and - members")
    L["intro"] = " ".join(intro)
    if groups:
        L["groups"] = groups
    return L


def topic(L, kinds):
    """A Threads index as s06_layers.topic_layers takes it: its groups' titles and keys, and its members, a [[link]]
    being a story (a story or event note) or else a person (a person note, or someone on the map by name).
    kinds: {note name: its type}."""
    return {"id": L["id"], "title": L["title"], "intro": L["intro"], "order": L["order"],
            "groups": [t for _, t in L.get("groups", [])], "keys": {t: k for k, t in L.get("groups", [])},
            "members": [{**m, "kind": ("story" if kinds.get(m["name"]) in ("story", "event") else "person")
                         if m["kind"] == "note" else m["kind"]} for m in L["members"]]}


def load(folder):
    """The notes under the folder as the build's layers. Returns {"layers": the Places indexes (with the People
    and facts layers), each with its notes' entries; "topics": the Threads indexes, for s06_layers.topic_layers;
    "people": {name: {"wikipedia": title | False, "group"}}; "names": [note names]}. Raises NoteError naming the
    note for anything it cannot read, and for a story or event no Places index lists (or two do)."""
    folder = Path(folder)
    if not folder.is_dir():
        return {"layers": [], "topics": [], "people": {}, "names": []}
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
    # the indexes: layers, and where each story or event is told (its Places index and group)
    kinds = {name: props.get("type") for name, props, _ in notes}
    indexes = []
    for name, props, body in notes:
        if props.get("type") == "index":
            try:
                indexes.append(index_layer(name, props, body))
            except NoteError as e:
                problems.append(str(e))
    indexes.sort(key=lambda L: (L["order"] if isinstance(L["order"], int) else 999, L["note"]))
    home = {}
    for L in indexes:
        if L["section"] != "Places":
            continue
        for m in L["members"]:
            if m["kind"] != "note" or kinds.get(m["name"]) not in ("story", "event"):
                problems.append(f"{m['line']}: a Places index lists stories and events: "
                                f"{m['name']!r} is " + ("no note" if m["name"] not in kinds else f"a {kinds[m['name']]} note"))
            elif any(H is L and g == m["group"] for H, g in home.get(m["name"], [])):
                problems.append(f"{m['line']}: {m['name']!r} is listed twice here")
            else:            # (a story can be in several places: Trent Bridge in West Bridgford and the Meadows)
                home.setdefault(m["name"], []).append((L, m["group"]))
    layers = [L for L in indexes if L["section"] == "Places"]
    if not any(L.get("kind") == "facts" for L in layers):
        layers.append({"id": "facts", "kind": "facts", "title": "Did you know", "intro": "", "entries": [], "members": []})
    topics = [topic(L, kinds) for L in indexes if L["section"] == "Threads"]
    people_layer = next((L for L in layers if L.get("kind") == "people"), None)
    facts_layer = next((L for L in layers if L.get("kind") == "facts"), None)
    info = {}
    for name, props, body in notes:
        if props.get("type") == "index":
            continue
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
            # the name shown on the map (name:), when the note's own differs: two "St Mary's Church" notes are
            # "St Mary's Church, Clifton" and "St Mary's Church, Nottingham", each shown as St Mary's Church
            shown = str(props.get("name") or name)
            base = {"name": shown, "note": name, "source": sources[0] if sources else None, "sources": sources[1:],
                    "facts": checks(props.get("check")), "story": story, "links": links, "weblinks": web,
                    "cites": {k: fns[k] for k in fns}, "type": kind,
                    **({"read": str(props["read"])} if props.get("read") else {}),
                    **({"title": str(props["title"])} if props.get("title") else {}),
                    **({"year": str(props["year"])} if props.get("year") else {}),
                    # when the story is set (else the first year in its text), and when the thing itself was made
                    **({"when": when(props["when"], name)} if props.get("when") else {}),
                    **({"made": when(props["made"], name, "made")} if props.get("made") else {}),
                    # passages copied from a Historic England list entry, which blocks automated requests
                    **({"quote": listed(props.get("quote"))} if props.get("quote") else {}),
                    # other stories to link from this one, as see: in a story file (also [[links]] in its text)
                    **({"see": [WIKILINK.sub(lambda m: m[1], s) for s in listed(props.get("see"))]} if props.get("see") else {}),
                    **({"names": False} if props.get("names") is False or str(props.get("names")).lower() == "no" else {}),
                    # who designed the building, as in a story file: "en:Thomas Rickman | Vincent Harris = en:E. Vincent Harris"
                    **({"architect": architects(" | ".join(listed(props.get("architect"))))} if props.get("architect") else {})}
            if kind == "person":
                if people_layer is None:
                    raise NoteError(f"{name}: a person note, but there is no People layer (kind: people)")
                wp = props.get("wikipedia")
                info[name] = {"wikipedia": False if str(wp).lower() in ("no", "false") else
                              (ref(wp)[3:] if wp and ref(wp).startswith("en:") else None),
                              **({"group": str(props["kind"])} if props.get("kind") else {})}
                target, group = people_layer, props.get("kind")
            elif story:
                if props.get("layer") or props.get("group"):
                    raise NoteError(f"{name}: layer: and group: are not used: list the note in an index "
                                    f"(notes/indexes/), under its group's heading")
                if name not in home:
                    raise NoteError(f"{name}: no Places index lists it: add - [[{name}]] to one (notes/indexes/)")
                homes = [(T, next((k for k, t in T.get("groups", []) if t == g), None)) for T, g in home[name]]
                target, group = homes[0]
            else:
                target = group = None       # facts only (a note of "Did you know?" callouts)
            base = {k: v for k, v in base.items() if v not in ((), [], {}, None) or k in ("name", "story")}
            if story:
                if not places and kind != "person":
                    raise NoteError(f"{name}: no at: (its places)")
                for T, grp in (homes if kind != "person" else [(target, group)]):
                    for at, where in places or [(None, None)]:
                        e = {**base, **({"group": str(grp)} if grp else {})}
                        if at:
                            e["at"] = at
                        else:
                            e["unplaced"] = True        # a person's own text, on their card only
                        if where:
                            e["where"] = where
                        T["entries"].append(e)
            for f in facts:
                if facts_layer is None:
                    raise NoteError(f"{name}: a fact callout, but there is no facts layer (kind: facts)")
                fsrc = [ref(f["source"])] if f.get("source") else sources
                if not fsrc:
                    raise NoteError(f"{name}: a fact callout with no source, in a note with none")
                ftext, flinks, fweb = inline(f["text"])
                fplaces = [place(a, name, pins) for a in f.get("at", [])] or places
                fe = {"name": shown, "note": name, "source": fsrc[0], "sources": fsrc[1:],
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
    for L in layers:
        L.pop("members", None)
    return {"layers": layers, "topics": topics, "people": info, "names": [n for n, _, _ in notes]}
