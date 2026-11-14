"""Topics (stories/<city>/topics/*.md, pipeline/stories_md.topic and s06_layers.topic_layers) and the date order of
numbered cards (pipeline/layerdata.in_date_order)."""
import tempfile
import unittest
from pathlib import Path

from pipeline.layerdata import Collector, in_date_order, year_in
from pipeline.s06_layers import topic_layers
from pipeline.stories_md import topic

ROOT = Path(__file__).resolve().parent.parent

TOPIC = """# Riot and war
id: war

The intro,
in two lines.

## The Civil War
- story: The storming of Shelford House
- person: Charles I
- note: for editors

## Riots
- story: culture/The castle burned
- plaque: Plaque to Albert Ball
- building: way/7
"""


def parsed(text):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "war.md"
        f.write_text(text)
        return topic(f)


class Parse(unittest.TestCase):
    def test_file(self):
        T = parsed(TOPIC)
        self.assertEqual((T["id"], T["title"], T["intro"]), ("war", "Riot and war", "The intro, in two lines."))
        self.assertEqual(T["groups"], ["The Civil War", "Riots"])
        self.assertEqual([(m["kind"], m["name"], m["group"]) for m in T["members"]],
                         [("story", "The storming of Shelford House", "The Civil War"), ("person", "Charles I", "The Civil War"),
                          ("story", "culture/The castle burned", "Riots"), ("plaque", "Plaque to Albert Ball", "Riots"),
                          ("building", "way/7", "Riots")])

    def test_bad_line(self):
        with self.assertRaisesRegex(ValueError, "war.md:3: 'place:' is not one of"):
            parsed("# War\n\n- place: Shelford\n")

    def test_city_topics_parse(self):
        for f in (ROOT / "stories").glob("*/topics/*.md"):
            T = topic(f)
            self.assertTrue(T["members"], f.name)
            self.assertEqual(T["id"], f.stem)


class Resolve(unittest.TestCase):
    def setUp(self):
        self.entries = [{"layer": "rushcliffe", "name": "The storming of Shelford House", "b": 3},
                        {"layer": "culture", "name": "The castle burned", "b": 4},
                        {"layer": "civic", "name": "The castle burned", "b": "p1"}]
        self.people = {"groups": [{"key": "people-public", "items": [["Charles I", ["p0", 5]]]},
                                  {"key": "people-events", "items": [["Moot Hall", ["p2"]]]}]}
        self.out = Collector({"pins": [{"name": "Plaque to Albert Ball", "layer": "people", "text": ""},
                                       {"name": "Castle", "layer": "civic", "text": ""}]})
        self.buildings = [{"osm": f"way/{i}"} for i in range(8)]

    def run_(self, text):
        return topic_layers([parsed(text)], self.entries, self.people, self.out, self.buildings,
                            lambda i: f"Building {i}", {"rushcliffe", "culture", "civic"})

    def test_members(self):
        (L,) = self.run_(TOPIC)
        self.assertEqual((L["section"], L["kind"]), ("Topics", "topics"))
        g1, g2 = L["groups"]
        self.assertEqual(g1["key"], "war-the-civil-war")
        self.assertEqual(g1["items"], [["The storming of Shelford House", [3], {"layer": "rushcliffe"}],
                                       ["Charles I", ["p0", 5], {"person": 1}]])
        self.assertEqual(g2["items"], [["The castle burned", [4], {"layer": "culture"}],
                                       ["Plaque to Albert Ball", ["p0"], {"plaque": 1}],
                                       ["Building 7", [7], {"building": 1}]])
        self.assertEqual(g1["count"], 3)
        # ticking the topic marks its buildings, and its pins carry its groups
        self.assertIn("war-the-civil-war", self.out.member["3"])
        self.assertIn("war-riots", self.out.member["7"])
        self.assertEqual(self.out.pins[0]["T"], ",war-the-civil-war,war-riots,")

    def test_no_groups(self):
        (L,) = self.run_("# Boots\nid: boots\n\n- person: Charles I\n")
        self.assertEqual([g["key"] for g in L["groups"]], ["boots"])

    def test_problems_name_the_line(self):
        with self.assertRaises(SystemExit) as e:
            self.run_("# War\nid: war\n\n- story: Nowhere\n- story: The castle burned\n- person: Nobody\n"
                      "- plaque: Moot Hall\n- building: way/99\n")
        msg = str(e.exception)
        for bit in ("war.md:4: no story", "war.md:5: story 'The castle burned' is in more than one layer",
                    "war.md:6: no one called 'Nobody'", "war.md:7: no plaque titled 'Moot Hall'",
                    "war.md:8: no building 'way/99'"):
            self.assertIn(bit, msg)


class DateOrder(unittest.TestCase):
    def test_year_in(self):
        self.assertEqual(year_in("Built in 1876–1877 of wrought iron; closed in 1968."), 1876)
        self.assertEqual(year_in("Wesley preached here in 1774, it was built in 1782"), 1774)
        self.assertEqual(year_in("Plaque put up in 1990 by the society: “Bendigo was born here 1811”"), 1811)
        self.assertEqual(year_in("The church dates from the late 14th century"), 1300)
        self.assertEqual(year_in("It holds 2,000 people and 1,500 seats"), None)
        self.assertIsNone(year_in(None))

    def test_order(self):
        pins = [{"text": "Plaque: “born here 1811”"}, {"text": "no year"}]
        stories = {"1": [{"layer": "s", "text": "Opened in 1930."}], "2": [{"layer": "s", "text": "Opened in 1850."}],
                   "3": [{"layer": "people", "who": "A", "text": "A lived here in 1900."}]}
        dates = {"4": {"y": 1700}, "3": {"y": 1850}}
        about = {"B": {"life": "1820–1890"}}
        meta = [{"id": "s", "kind": "stories", "groups": [{"key": "s", "items": [["New", [1]], ["Undated", ["p1"]], ["Old", [2]]]}]},
                {"id": "people", "kind": "people", "groups": [{"key": "people-x", "items": [["A", [3, "p0"]], ["B", [4]]]}]},
                {"id": "rule", "kind": "rule", "groups": [{"key": "r", "items": [["Z", [1]], ["A", [2]]]}]}]
        in_date_order(meta, stories, pins, dates, about)
        self.assertEqual([it[0] for it in meta[0]["groups"][0]["items"]], ["Old", "New", "Undated"])
        # B was born in 1820; A has no birth year, so their first place's year (the plaque, 1811)
        self.assertEqual([it[0] for it in meta[1]["groups"][0]["items"]], ["A", "B"])
        self.assertEqual(meta[1]["groups"][0]["items"][0][1], ["p0", 3])
        self.assertEqual([it[0] for it in meta[2]["groups"][0]["items"]], ["Z", "A"])     # lists A to Z stay


if __name__ == "__main__":
    unittest.main()
