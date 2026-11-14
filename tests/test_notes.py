"""Notes (pipeline/notes.py): one story, event or person per file, read into the story layers' entries."""
import re
import tempfile
import unittest
from pathlib import Path

from pipeline import notes

ROOT = Path(__file__).resolve().parent.parent

EVENT = """---
type: event
layer: civic
source:
  - https://en.wikipedia.org/wiki/1831_reform_riots
  - https://en.wikipedia.org/wiki/Nottingham_Castle
check: 8 October 1831 | Duke of Newcastle
at:
  - https://www.openstreetmap.org/way/16459858
  - Lowe's Silk Mill, 52.9265, -1.2165
see:
  - "[[Mortimer's Hole]]"
---

When the Lords threw out the Bill, a crowd burned [Nottingham Castle](https://www.openstreetmap.org/way/16459858),
the house of the [[Henry Pelham-Clinton|Duke of Newcastle]].[^castle]

It reopened as a museum.

> [!fact]
> source: https://en.wikipedia.org/wiki/Nottingham_Castle
> check: 1878
>
> It reopened in 1878.

[^castle]: https://en.wikipedia.org/wiki/Nottingham_Castle — check: 1878 | museum
"""

PERSON = """---
type: person
kind: sport
wikipedia: https://en.wikipedia.org/wiki/William_Thompson_(boxer)
source: https://map.mappingwomenssuffrage.org.uk/items/show/1
read: 2026-11-14
at:
  - Lowe's Silk Mill
---
He lived by the mill.

> [!fact]
> A fact about him.
"""


def layers():
    return [{"id": "civic", "title": "Civic", "entries": []},
            {"id": "people", "kind": "people", "title": "People", "entries": []},
            {"id": "facts", "kind": "facts", "title": "Did you know", "entries": []}]


def load(files, Ls=None):
    Ls = Ls if Ls is not None else layers()
    with tempfile.TemporaryDirectory() as d:
        for name, text in files.items():
            p = Path(d) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        return notes.load(Path(d), Ls), Ls


class Read(unittest.TestCase):
    def test_event(self):
        info, (civic, people, facts) = load({"events/The castle burned.md": EVENT})
        a, b = civic["entries"]
        self.assertEqual((a["name"], a["source"], a["sources"]), ("The castle burned", "en:1831 reform riots", ["en:Nottingham Castle"]))
        self.assertEqual(a["facts"], ("8 October 1831", "Duke of Newcastle"))
        self.assertEqual(a["at"], "osm:way/16459858")
        self.assertEqual((b["at"], b["where"]), ("pin:-1.2165,52.9265", "Lowe's Silk Mill"))
        self.assertEqual(a["story"], "When the Lords threw out the Bill, a crowd burned Nottingham Castle, the house of the "
                                     "Duke of Newcastle.[^castle]\n\nIt reopened as a museum.")
        self.assertEqual(a["links"], ["Henry Pelham-Clinton"])
        self.assertEqual(a["weblinks"], [["Duke of Newcastle", "note:Henry Pelham-Clinton"],
                                         ["Nottingham Castle", "https://www.openstreetmap.org/way/16459858"]])
        self.assertEqual(a["cites"], {"castle": {"source": "en:Nottingham Castle", "check": ("1878", "museum")}})
        self.assertEqual(a["see"], ["Mortimer's Hole"])
        # the fact: at the note's places, with its own source and words
        self.assertEqual([(f["at"], f["source"], f["facts"], f["story"]) for f in facts["entries"]],
                         [("osm:way/16459858", "en:Nottingham Castle", ("1878",), "It reopened in 1878."),
                          ("pin:-1.2165,52.9265", "en:Nottingham Castle", ("1878",), "It reopened in 1878.")])
        self.assertEqual(info["names"], ["The castle burned"])

    def test_person_and_a_pin_another_note_made(self):
        info, (civic, people, facts) = load({"events/E.md": EVENT, "people/William Thompson.md": PERSON})
        (p,) = people["entries"]
        self.assertEqual((p["name"], p["group"], p["at"], p["where"]), ("William Thompson", "sport", "pin:-1.2165,52.9265", "Lowe's Silk Mill"))
        self.assertEqual((p["source"], p["read"]), ("web:https://map.mappingwomenssuffrage.org.uk/items/show/1", "2026-11-14"))
        self.assertEqual(info["people"]["William Thompson"], {"wikipedia": "William Thompson (boxer)", "group": "sport"})
        # a person's fact with no place of its own: on their card
        (f,) = [f for f in facts["entries"] if f.get("who")]
        self.assertEqual((f["who"], f["unplaced"], f["source"]), ("William Thompson", True, p["source"]))

    def test_person_with_no_text_or_place(self):
        info, (civic, people, facts) = load({"people/W. G. Grace.md": "---\ntype: person\nwikipedia: no\n---\n"})
        self.assertEqual(people["entries"], [])
        self.assertIs(info["people"]["W. G. Grace"]["wikipedia"], False)

    def test_person_text_with_no_place(self):
        _, (civic, people, facts) = load({"people/A.md": "---\ntype: person\nsource: en:A\n---\nWho they were.\n"})
        (p,) = people["entries"]
        self.assertTrue(p["unplaced"])
        self.assertNotIn("at", p)

    def test_events_layer_made_when_none_named(self):
        _, Ls = load({"events/E.md": EVENT.replace("layer: civic\n", "")})
        self.assertEqual(Ls[-1]["id"], "events")
        self.assertEqual(len(Ls[-1]["entries"]), 2)

    def test_problems(self):
        for text, want in [
            ("---\ntype: thing\n---\n", "type: must be one of"),
            ("---\ntype: event\nlayer: civic\nsource: en:A\n---\nNo places.\n", "no at:"),
            ("---\ntype: event\nlayer: civic\nat:\n  - https://www.openstreetmap.org/way/1\n---\nNo source.\n", "no source:"),
            ("---\ntype: event\nlayer: nowhere\nsource: en:A\nat:\n  - Somewhere, 52.9, -1.1\n---\nText.\n", "not a story layer"),
            ("---\ntype: event\nlayer: civic\nsource: en:A\nat:\n  - The moon\n---\nText.\n", "'The moon' is not"),
            ("---\ntype: event\nlayer: civic\nsource: en:A\nat:\n  - Pin, 52.9, -1.1\n---\nText.[^x]\n", "[^x] has no line"),
            ("---\ntype: event\nlayer: civic\nsource: en:A\nat:\n  - Pin, -100.1, 52.9\n---\nText.\n", "latitude, then longitude"),
            ("---\ntype: [\n---\n", "not valid YAML"),
        ]:
            with self.subTest(want=want), self.assertRaisesRegex(notes.NoteError, re.escape(want)):
                load({"N.md": text})

    def test_two_notes_of_one_name(self):
        with self.assertRaisesRegex(notes.NoteError, "two notes are called 'A'"):
            load({"a/A.md": PERSON, "b/A.md": PERSON})

    def test_sources(self):
        self.assertEqual(notes.ref("https://en.wikipedia.org/wiki/Green%27s_Windmill"), "en:Green's Windmill")
        self.assertEqual(notes.ref("https://historicengland.org.uk/listing/the-list/list-entry/1254566"), "he:1254566")
        self.assertEqual(notes.ref("https://leftlion.co.uk/x"), "web:https://leftlion.co.uk/x")
        self.assertEqual(notes.ref("en:Nottingham Castle"), "en:Nottingham Castle")

    def test_city_notes_read(self):
        from pipeline import stories_md
        for folder in (ROOT / "stories").iterdir():
            if (folder / "notes").is_dir():
                out = stories_md.load(folder)
                self.assertTrue(out["NOTES"]["names"], folder.name)


if __name__ == "__main__":
    unittest.main()
