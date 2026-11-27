"""Notes (pipeline/notes.py): one story, event or person per file, read into the story layers' entries."""
import re
import tempfile
import unittest
from pathlib import Path

from pipeline import notes

ROOT = Path(__file__).resolve().parent.parent

EVENT = """---
type: event
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
"""


# the indexes: a Places index (Civic) listing the event, the People layer
INDEXES = {"indexes/Civic.md": "---\ntype: index\narea: The city\nid: civic\norder: 1\n---\nThe council.\n\n- [[The castle burned]]\n",
           "indexes/People.md": "---\ntype: index\narea: The city\nid: people\nkind: people\norder: 2\n---\nWho lived here.\n"}


def load(files, indexes=True):
    with tempfile.TemporaryDirectory() as d:
        idx = dict(INDEXES) if indexes else {}
        if not any(f.endswith("/The castle burned.md") for f in files):       # (the Civic index lists only that)
            idx["indexes/Civic.md"] = idx["indexes/Civic.md"].replace("- [[The castle burned]]\n", "")
        for name, text in {**idx, **files}.items():
            p = Path(d) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        out = notes.load(Path(d))
        return out, out["layers"]


class Read(unittest.TestCase):
    def test_event(self):
        info, (civic, people) = load({"events/The castle burned.md": EVENT})
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
        self.assertEqual(info["names"], ["The castle burned", "Civic", "People"])
        self.assertEqual([(L["id"], L["intro"]) for L in info["layers"]], [("civic", "The council."), ("people", "Who lived here.")])

    def test_person_and_a_pin_another_note_made(self):
        info, (civic, people) = load({"events/The castle burned.md": EVENT, "people/William Thompson.md": PERSON})
        (p,) = people["entries"]
        self.assertEqual((p["name"], p["group"], p["at"], p["where"]), ("William Thompson", "sport", "pin:-1.2165,52.9265", "Lowe's Silk Mill"))
        self.assertEqual((p["source"], p["read"]), ("web:https://map.mappingwomenssuffrage.org.uk/items/show/1", "2026-11-14"))
        self.assertEqual(info["people"]["William Thompson"], {"wikipedia": "William Thompson (boxer)", "group": "sport"})

    def test_person_with_no_text_or_place(self):
        info, (civic, people) = load({"people/W. G. Grace.md": "---\ntype: person\nwikipedia: no\n---\n"})
        self.assertEqual(people["entries"], [])
        self.assertIs(info["people"]["W. G. Grace"]["wikipedia"], False)

    def test_quotes(self):
        _, (civic, people) = load({"people/A.md": "---\ntype: person\nsource: he:1\nquote:\n  - Paid for by A.\n"
                                                         "  - \"1908\"\nat:\n  - P, 52.9, -1.1\n---\nText.\n"})
        self.assertEqual(people["entries"][0]["quote"], ["Paid for by A.", "1908"])

    def test_person_text_with_no_place(self):
        _, (civic, people) = load({"people/A.md": "---\ntype: person\nsource: en:A\n---\nWho they were.\n"})
        (p,) = people["entries"]
        self.assertTrue(p["unplaced"])
        self.assertNotIn("at", p)

    def test_index_groups(self):
        idx = ("---\ntype: index\narea: The city\nid: civic\norder: 1\n---\nThe council.\n\n## Old\n- [[The castle burned]]\n"
               "\n## New\n- [[B]]\n")
        b = EVENT.replace("check: 8 October 1831 | Duke of Newcastle\n", "")
        _, (civic, people) = load({"indexes/Civic.md": idx, "events/The castle burned.md": EVENT, "stories/B.md": b})
        self.assertEqual(civic["groups"], [["civic-old", "Old"], ["civic-new", "New"]])     # id-heading
        self.assertEqual({(e["name"], e["group"]) for e in civic["entries"]}, {("The castle burned", "civic-old"), ("B", "civic-new")})

    def test_a_story_in_two_places(self):
        """A story listed in two Places indexes is told in both (Trent Bridge: West Bridgford and the Meadows)."""
        _, (other, civic, people) = load({"events/The castle burned.md": EVENT,
                                                 "indexes/Civic.md": "---\ntype: index\narea: The city\norder: 2\n---\n- [[The castle burned]]\n",
                                                 "indexes/Other.md": "---\ntype: index\narea: The city\norder: 1\n---\n- [[The castle burned]]\n"})
        self.assertEqual([e["name"] for e in civic["entries"]], [e["name"] for e in other["entries"]])
        self.assertTrue(civic["entries"])

    def test_a_story_in_no_index(self):
        with self.assertRaisesRegex(notes.NoteError, r"no Places index lists it: add - \[\[The castle burned\]\]"):
            load({"events/The castle burned.md": EVENT, "indexes/Civic.md": "---\ntype: index\narea: The city\n---\n"})
        with self.assertRaisesRegex(notes.NoteError, "layer: and group: are not used"):
            load({"events/The castle burned.md": EVENT.replace("type: event\n", "type: event\nlayer: civic\n")})

    def test_problems(self):
        for text, want in [
            ("---\ntype: thing\n---\n", "type: must be one of"),
            ("---\ntype: event\nsource: en:A\n---\nNo places.\n", "no at:"),
            ("---\ntype: event\nat:\n  - https://www.openstreetmap.org/way/1\n---\nNo source.\n", "no source:"),
            ("---\ntype: event\nsource: en:A\nat:\n  - The moon\n---\nText.\n", "'The moon' is not"),
            ("---\ntype: event\nsource: en:A\nat:\n  - Pin, 52.9, -1.1\n---\nText.[^x]\n", "[^x] has no line"),
            ("---\ntype: event\nsource: en:A\nat:\n  - Pin, -100.1, 52.9\n---\nText.\n", "latitude, then longitude"),
            ("---\ntype: index\nsection: Elsewhere\n---\n", "section: is no longer used"),
            ("---\ntype: [\n---\n", "not valid YAML"),
        ]:
            with self.subTest(want=want), self.assertRaisesRegex(notes.NoteError, re.escape(want)):
                load({"events/The castle burned.md": text})

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
