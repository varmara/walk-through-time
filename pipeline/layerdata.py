"""What the layer steps build up together: which buildings are in which groups, their stories, and pins.

AREAS: the work files of areas drawn on the ground, in the order they are packaged (s07): layer items refer to
an area as a<index> in that order.

s06_people fills one with the People layer and saves it; s06_layers carries on with it for the other layers.
"""

AREAS = ("nature", "conservation", "parks", "article4", "tpo")


def grouped(pairs):
    """[[building, name], ...] -> [[name, [buildings]]]: one entry per name, with every building it has."""
    out = {}
    for b, name in pairs:
        bs = out.setdefault(name, [])
        if b not in bs:
            bs.append(b)
    return [[n, bs] for n, bs in out.items()]


class Collector:
    """member {building index: [group keys]}, stories {building index: [story]}, pins [pin]."""

    def __init__(self, data=None):
        data = data or {}
        self.member, self.stories, self.pins = data.get("member", {}), data.get("stories", {}), data.get("pins", [])

    def json(self):
        return {"member": self.member, "stories": self.stories, "pins": self.pins}

    def pin(self, x, y, name, layer_id, group, text, source=None, place=None, who=None, on=None):
        """A place that is not a building (a bridge, grounds, a plaque): layer items refer to it as "p<index>"."""
        self.pins.append({"x": round(x, 6), "y": round(y, 6), "name": name, "layer": layer_id, "group": group,
                          "text": text, **({"source": source} if source else {}), **({"place": place} if place else {}),
                          **({"who": who} if who else {}), **({"on": on} if on is not None else {})})
        return f"p{len(self.pins) - 1}"

    def add(self, i, group, layer_id, story=None, source=None, place=None, who=None, pin_ref=None, tpl=None, of=None):
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
                      **({"place": place} if place else {}), **({"who": who} if who else {})}
        if story_:
            self.stories.setdefault(str(i), []).append(story_)
