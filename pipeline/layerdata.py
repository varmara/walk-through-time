"""What the layer steps build up together: which buildings are in which groups, their stories, and pins.

AREAS: the work files of areas drawn on the ground, in the order they are packaged (s07): layer items refer to
an area as a<index> in that order.

s06_people fills one with the People layer and saves it; s06_layers carries on with it for the other layers.
"""
import re

AREAS =("nature", "conservation", "parks", "article4", "tpo")


def grouped(pairs, where=None, within=150):
    """[[building, name], ...] -> [[name, [buildings]]].

    Without `where`, one entry per name, with every building it has: for a person or a story, whose name is the
    same subject wherever it is. With `where` (ref -> (lon, lat)), for places: a name is joined only with places
    of that name within `within` metres of one already in the entry (a pub of two outlines, one artwork's two
    pins), so unrelated places that share a name ("Red Lion", "War memorial", "In this house") stay apart."""
    if where is None:
        out = {}
        for b, name in pairs:
            bs = out.setdefault(name, [])
            if b not in bs:
                bs.append(b)
        return [[n, bs] for n, bs in out.items()]
    from math import cos, hypot, radians
    entries = []                          # [name, [refs], [points]]
    for b, name in pairs:
        p = where(b)
        near = lambda q: p is not None and q is not None and hypot((p[0] - q[0]) * 111320 * cos(radians(p[1])),  # noqa: E731
                                                                     (p[1] - q[1]) * 110540) <= within
        e = next((e for e in entries if e[0] == name and (b in e[1] or any(near(q) for q in e[2]))), None)
        if e is None:
            entries.append([name, [b], [p]])
        elif b not in e[1]:
            e[1].append(b)
            e[2].append(p)
    return [[n, bs] for n, bs, _ in entries]


def place_of(buildings, pins):
    """ref -> (lon, lat): a building's (its outline's middle) or a pin's ("p12"), for grouped()."""
    from .geo import centroid

    def where(ref):
        if isinstance(ref, str) and ref.startswith("p"):
            p = pins[int(ref[1:])]
            return p["x"], p["y"]
        if isinstance(ref, int) and 0 <= ref < len(buildings):
            return centroid(buildings[ref]["rings"][0])
        return None
    return where


YEAR = re.compile(r"(?<![\d,.£$])\b(1[0-9]{3}|20[0-9]{2})\b(?![,.]\d)")
CENTURY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)[ -]century", re.I)


def year_in(text):
    """The first year a text tells of ("the 12th century" is 1100), or None. A plaque's text is its words, not
    when it was put up ("Plaque put up in 1990: “… born here 1811”" tells of 1811)."""
    t = text or ""
    if "“" in t:
        t = t.split("“", 1)[1]
    ys = [(m.start(), int(m[1])) for m in YEAR.finditer(t)] + [(m.start(), (int(m[1]) - 1) * 100) for m in CENTURY.finditer(t)]
    return min(ys)[1] if ys else None


def in_date_order(meta, stories, pins, dates, about):
    """Each story, people or topic group's items, and each item's places, in date order: the year of what it tells
    (a story's, a plaque's words'), a person's year of birth, a building's year of building. Undated last; ties keep
    their order. The page's numbered cards follow this order."""
    def ref_year(r, name=None, layer=None):
        if isinstance(r, str) and r.startswith("p"):
            return year_in(pins[int(r[1:])].get("text"))
        if not isinstance(r, int):
            return None
        ss = stories.get(str(r), [])

        def text(s):
            return s.get("text") or (pins[int(s["pin"][1:])].get("text") if s.get("pin") else "")
        mine = [s for s in ss if (layer and s.get("layer") == layer) or (name and (s.get("who") == name or name in text(s)))]
        for s in mine:
            if (y := year_in(text(s))) is not None:
                return y
        return (dates.get(str(r)) or {}).get("y")

    def born(name):
        m = re.match(r"(\d{3,4})", (about.get(name) or {}).get("life") or "")
        return int(m[1]) if m else None

    def later(y):
        return (y is None, y or 0)

    for L in meta:
        if L.get("kind") not in ("stories", "people", "topics"):
            continue
        for g in L["groups"]:
            items = g.get("items") or []
            keyed = []
            for it in items:
                name, refs = it[0], it[1]
                hint = it[2] if len(it) > 2 else {}
                person = L["kind"] == "people" and g["key"] != "people-events" or hint.get("person")
                layer = hint.get("layer") or (L["id"] if L["kind"] == "stories" else None)
                ys = {r: ref_year(r, name if person or L["kind"] == "people" else None, layer) for r in refs}
                it[1] = sorted(refs, key=lambda r: later(ys[r]))
                first = min((y for y in ys.values() if y is not None), default=None)
                if hint.get("building"):
                    first = (dates.get(str(refs[0])) or {}).get("y") if refs else None
                keyed.append((later(born(name) if person and born(name) is not None else first), it))
            g["items"] = [it for _, it in sorted(keyed, key=lambda k: k[0])]


MORE = ("sources", "cites", "weblinks", "links")


def more_of(e):
    """What a note adds to a story (pipeline/notes.py): its other sources, footnotes' pages and links."""
    return {k: e[k] for k in MORE if e.get(k)}


class Collector:
    """member {building index: [group keys]}, stories {building index: [story]}, pins [pin]."""

    def __init__(self, data=None):
        data = data or {}
        self.member, self.stories, self.pins = data.get("member", {}), data.get("stories", {}), data.get("pins", [])

    def json(self):
        return {"member": self.member, "stories": self.stories, "pins": self.pins}

    def pin(self, x, y, name, layer_id, group, text, source=None, place=None, who=None, on=None, extra=None):
        """A place that is not a building (a bridge, grounds, a plaque): layer items refer to it as "p<index>".
        extra: more fields for its card (visitorlayers.py)."""
        self.pins.append({**(extra or {}), "x": round(x, 6), "y": round(y, 6), "name": name, "layer": layer_id, "group": group,
                          "text": text, **({"source": source} if source else {}), **({"place": place} if place else {}),
                          **({"who": who} if who else {}), **({"on": on} if on is not None else {})})
        return f"p{len(self.pins) - 1}"

    def add(self, i, group, layer_id, story=None, source=None, place=None, who=None, pin_ref=None, tpl=None, of=None,
            more=None):
        """more: a note's other sources, footnotes' pages, links (MORE), kept with its story."""
        groups = self.member.setdefault(str(i), [])
        if group not in groups:
            groups.append(group)
        story_ = None
        if pin_ref:          # a plaque on this building: its words are stored once, on the plaque's pin
            story_ = {"layer": layer_id, "pin": pin_ref, **({"who": who} if who else {})}
        elif tpl:            # the same words but for a name: a template (texts.TEMPLATES)
            story_ = {"layer": layer_id, "tpl": tpl, **({"who": who} if who else {}), **({"of": of} if of else {}),
                      **({"source": source} if source else {})}
        elif story:
            story_ = {"layer": layer_id, "text": story, **({"source": source} if source else {}),
                      **({"place": place} if place else {}), **({"who": who} if who else {}), **(more or {})}
        if story_:
            self.stories.setdefault(str(i), []).append(story_)
