"""Topics (Threads indexes, notes/indexes/*.md: pipeline/notes.index_layer and topic, s06_layers.topic_layers) and
the date order of numbered cards (pipeline/layerdata.in_date_order)."""
import unittest

from pipeline import notes
from pipeline.layerdata import Collector, in_date_order, year_in
from pipeline.s06_layers import topic_layers

TOPIC = """
The intro,
in two lines.

## The Civil War
- [[The storming of Shelford House]]
- [[Charles I]]

## Riots
- [[The castle burned]]
- plaque: Plaque to Albert Ball
- [A building](https://www.openstreetmap.org/way/7)
"""
KINDS = {"The storming of Shelford House": "event", "The castle burned": "story"}


def parsed(body, props=None):
    return notes.topic(notes.index_layer("Riot and war", props or {"type": "index", "id": "war"}, body), KINDS)


class Parse(unittest.TestCase):
    def test_index(self):
        T = parsed(TOPIC)
        self.assertEqual((T["id"], T["title"], T["intro"]), ("war", "Riot and war", "The intro, in two lines."))
        self.assertEqual(T["groups"], ["The Civil War", "Riots"])
        self.assertEqual([(m["kind"], m["name"], m["group"]) for m in T["members"]],
                         [("story", "The storming of Shelford House", "The Civil War"), ("person", "Charles I", "The Civil War"),
                          ("story", "The castle burned", "Riots"), ("plaque", "Plaque to Albert Ball", "Riots"),
                          ("building", "way/7", "Riots")])

    def test_a_date_on_a_line(self):
        T = parsed("- c. 1200: [[The castle burned]]\n- 1930s: [[Charles I]]\n- 13th century: plaque: Plaque to Albert Ball\n- [[The storming of Shelford House]]\n")
        self.assertEqual([m.get("when") for m in T["members"]], ["c. 1200", "1930s", "13th century", None])
        self.assertEqual([m["kind"] for m in T["members"]], ["story", "person", "plaque", "story"])

    def test_bad_lines(self):
        for body, want in [("## A\n- place: Shelford\n", "is not a member"),
                           ("## A\n- [x](https://example.org)\n", "OpenStreetMap"),
                           ("## A\n- [[X]]\nWords after the members.\n", "only ## groups")]:
            with self.subTest(want=want), self.assertRaisesRegex(notes.NoteError, want):
                parsed(body)


class Resolve(unittest.TestCase):
    def setUp(self):
        self.entries = [{"layer": "rushcliffe", "name": "The storming of Shelford House", "note": "The storming of Shelford House", "b": 3},
                        {"layer": "culture", "name": "The castle burned", "note": "The castle burned", "b": 4},
                        {"layer": "civic", "name": "The castle burned", "b": "p1"}]
        self.people = {"groups": [{"key": "people-public", "items": [["Charles I", ["p0", 5]]]},
                                  {"key": "people-events", "items": [["Moot Hall", ["p2"]]]}]}
        self.out = Collector({"pins": [{"name": "Plaque to Albert Ball", "layer": "people", "text": ""},
                                       {"name": "Castle", "layer": "civic", "text": ""}]})
        self.buildings = [{"osm": f"way/{i}"} for i in range(8)]

    def run_(self, text):
        return topic_layers([text if isinstance(text, dict) else parsed(text)], self.entries, self.people, self.out, self.buildings,
                            lambda i: f"Building {i}", {"rushcliffe", "culture", "civic"})

    def test_members(self):
        (L,) = self.run_(TOPIC)
        self.assertEqual((L["section"], L["kind"]), ("Threads", "topics"))
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
        (L,) = self.run_(notes.topic(notes.index_layer("Boots", {}, "- [[Charles I]]\n"), {}))
        self.assertEqual([g["key"] for g in L["groups"]], ["boots"])

    def test_problems_name_the_line(self):
        members = [("story", "Nowhere"), ("story", "castle burned"), ("person", "Nobody"), ("plaque", "Moot Hall"),
                   ("building", "way/99")]
        self.entries.append({"layer": "civic", "name": "castle burned", "b": 8})
        self.entries.append({"layer": "culture", "name": "castle burned", "b": 9})
        T = {"id": "war", "title": "War", "groups": [], "members": [{"kind": k, "name": n, "group": None, "line": f"War:{i}"}
                                                                   for i, (k, n) in enumerate(members, 1)]}
        with self.assertRaises(SystemExit) as e:
            self.run_(T)
        msg = str(e.exception)
        for bit in ("War:1: no story", "War:2: story 'castle burned' is in more than one layer",
                    "War:3: no one called 'Nobody'", "War:4: no plaque titled 'Moot Hall'",
                    "War:5: no building 'way/99'"):
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

    def test_dates_given(self):
        """A note's when: comes before the years in its text; a thread's own date for it before both; a building's
        two stories of one layer are each dated by their own."""
        stories = {"1": [{"layer": "s", "nm": "Statue", "text": "Unveiled in 1952.", "when": "c. 1200", "made": "1952"}],
                   "2": [{"layer": "s", "nm": "Castle", "text": "Burned in 1831.", "when": "11th century"},
                         {"layer": "s", "nm": "Fire", "text": "Burned in 1831."}],
                   "3": [{"layer": "s", "nm": "Inn", "text": "Built around 1360."}]}
        place = [{"id": "s", "kind": "stories", "groups": [{"key": "s", "items": [["Fire", [2]], ["Inn", [3]], ["Statue", [1]], ["Castle", [2]]]}]}]
        in_date_order(place, stories, [], {}, {"P": {"life": "1796–1855"}})
        self.assertEqual([it[0] for it in place[0]["groups"][0]["items"]], ["Castle", "Statue", "Inn", "Fire"])
        thread = [{"id": "t", "kind": "topics", "groups": [{"key": "t", "items": [
            ["Statue", [1], {"layer": "s", "when": "1952"}], ["P", [3], {"person": 1, "when": "1847"}], ["Inn", [3], {"layer": "s"}]]}]}]
        in_date_order(thread, stories, [], {}, {"P": {"life": "1796–1855"}})
        self.assertEqual([it[0] for it in thread[0]["groups"][0]["items"]], ["Inn", "P", "Statue"])   # P by 1847, not 1796

    def test_when_year(self):
        from pipeline.layerdata import when_year
        self.assertEqual([when_year(w) for w in ("c. 1200", "1930s", "13th century", "1952", None)], [1200, 1930, 1200, 1952, None])


if __name__ == "__main__":
    unittest.main()


class ChapterIntros(unittest.TestCase):
    def test_a_chapter_takes_the_prose_before_its_first_member(self):
        L = notes.index_layer("T", {"type": "index", "id": "t"},
                              "Intro.\n\n## One\nAbout one,\nin two lines.\n- [[A]]\n\n## Two\n- [[B]]\n")
        self.assertEqual(L["groupIntros"], {"One": "About one, in two lines."})
        self.assertEqual(notes.topic(L, {})["intros"], {"One": "About one, in two lines."})

    def test_prose_among_the_members_is_still_an_error(self):
        with self.assertRaises(notes.NoteError):
            notes.index_layer("T", {"type": "index", "id": "t"}, "## One\n- [[A]]\nstray prose\n")

    def test_every_chapter_of_a_thread_of_several_has_an_introduction(self):
        # (places and themes alike)
        import glob
        missing = []
        for folder in glob.glob("stories/*/notes"):
            for name, props, body in notes.read_notes(folder):
                if props.get("type") != "index":
                    continue
                L = notes.index_layer(name, props, body)
                if len(L.get("groups", [])) > 1:
                    missing += [f"{name}: {g}" for _, g in L["groups"] if g not in L.get("groupIntros", {})]
        self.assertEqual(missing, [], "chapters without an introduction")

    def test_a_place_is_a_thread_with_an_area(self):
        self.assertEqual(notes.index_layer("W", {"area": "South of the Trent"}, "- [[A]]\n")["section"], "Places")
        self.assertEqual(notes.index_layer("T", {}, "- [[A]]\n")["section"], "Threads")
        with self.assertRaises(notes.NoteError):
            notes.index_layer("T", {"section": "Threads"}, "- [[A]]\n")
