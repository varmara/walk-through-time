"""A story's footnotes: each sentence to the page holding its check words, each date to the page giving it
(pipeline/s04_curated.footnoted, date_page)."""
import unittest

from pipeline.s04_curated import date_page, footnoted

LEGEND = {"url": "https://en.wikipedia.org/wiki/Robin_Hood", "text": "robin hood is a legendary heroic outlaw ... sherwood forest ... the sheriff of nottingham"}
STATUE = {"url": "https://en.wikipedia.org/wiki/Statue_of_Robin_Hood", "text": "the sculpture was unveiled in 1952 and is the work of james woodford"}


class Footnotes(unittest.TestCase):
    def test_each_sentence_its_page(self):
        story, new = footnoted("Robin Hood is a legendary outlaw. In the stories his enemy is the Sheriff of Nottingham.\n\n"
                               "James Woodford's statue was unveiled in 1952.",
                               ["outlaw", "Sheriff of Nottingham", "James Woodford", "1952"], [LEGEND, STATUE], {})
        self.assertEqual(story, "Robin Hood is a legendary outlaw.[^s1] In the stories his enemy is the Sheriff of Nottingham.[^s1]\n\n"
                                "James Woodford's statue was unveiled in 1952.[^s2]")
        self.assertEqual({k: p["url"] for k, p in new.items()}, {"s1": LEGEND["url"], "s2": STATUE["url"]})

    def test_left_alone(self):
        one = "Unveiled in 1952."
        self.assertEqual(footnoted(one, ["1952"], [STATUE], {}), (one, {}))                    # one page: its end
        mine = "Unveiled in 1952.[^own] A sentence with no check word."
        self.assertEqual(footnoted(mine, ["1952"], [LEGEND, STATUE], {})[0], mine)            # footnoted by the writer

    def test_not_a_sentence_end(self):
        story, _ = footnoted("Built c. 1450 for D. H. Lawrence's family. Moved in 1952.", ["1450", "1952"],
                             [{"url": "a", "text": "1450"}, STATUE], {})
        self.assertEqual(story, "Built c. 1450 for D. H. Lawrence's family.[^s1] Moved in 1952.[^s2]")

    def test_date_page(self):
        self.assertIs(date_page("c. 1450", [LEGEND, {"url": "x", "text": "built around 1450"}])["url"], "x")
        self.assertEqual(date_page("11th century", [{"url": "y", "text": "in the 11th century"}])["url"], "y")
        self.assertIsNone(date_page("1770", [LEGEND, STATUE]))


if __name__ == "__main__":
    unittest.main()


def test_a_century_in_words_is_found():
    from pipeline.s04_curated import date_page
    page = {"text": "mentioned as early as the fifteenth century"}
    assert date_page("15th century", [page]) is page
    assert date_page("16th century", [page]) is None


def test_a_century_joined_to_another_is_found():
    from pipeline.s04_curated import date_page
    page = {"text": "the tower was built in stages between the 12th and 14th century"}
    assert date_page("12th century", [page]) is page
    assert date_page("13th century", [page]) is None      # (a century between them is not given)
    assert date_page("13th century", [{"text": "built in the 13th–14th centuries"}])
