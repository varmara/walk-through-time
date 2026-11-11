"""Words stored once: a story points to its plaque's pin or to a template instead of repeating the words."""


# A building's story holds its words itself, or points to where they are kept once:
#   {"layer", "pin": "p12"}                     a plaque: the words are on the plaque's pin
#   {"layer", "tpl": "architect", "who": ...}   words that are the same but for a name: a template in the package's
#                                               "templates", filled in by the page (app/city/data.js: storyOf) and here
TEMPLATES = {"architect": "Designed by {who}, according to Wikidata.",
             "scheduled": "Part of the scheduled monument “{of}”.",
             "locallist": "On the council's local heritage list as “{of}”."}


def story_text(st, pins=None, templates=TEMPLATES):
    """A story with its words (and, for a plaque, its source) filled in."""
    if st.get("text"):
        return st
    if st.get("pin") and pins is not None:
        pp = pins[int(st["pin"][1:])]
        pp = pp.get("properties", pp)
        return {**st, "text": pp.get("text"), "source": pp.get("source"), "who": st.get("who") or pp.get("who")}
    if st.get("tpl") in templates:
        return {**st, "text": templates[st["tpl"]].format(who=st.get("who", ""), of=st.get("of", ""))}
    return st
