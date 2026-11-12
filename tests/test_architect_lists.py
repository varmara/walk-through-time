import unittest

from pipeline.architect_lists import architect_lists, names_in, numbers, tables

TABLE = """{| class="wikitable sortable"
! Name !! Street and number !! Photograph !! Date !! Architect !! Notes and refs
|-
| Hine House || Castle Grove, 1 || [[File:Hine House.jpg|100px|Hine [[House]]]] || 1856 || [[Thomas Chambers Hine]] || listed<ref>{{cite web|url=x}}</ref>
|-
| || Lenton Road, 1–7 || — || 1850 || [[Thomas Chambers Hine|T. C. Hine]]? ||
|-
| Tower House
| Park Row, 53
|
| 1827
| [[Peter Frederick Robinson]]; [[Watson Fothergill]] (added tower)
|
|-
| Gladstone House || Lincoln Circus || || 1876–77 || Edwin Loverseed ||
|}"""


class ArchitectLists(unittest.TestCase):
    def test_table(self):
        t = tables(TABLE)[0]
        self.assertEqual(t[0][1], "Street and number")
        self.assertEqual(len(t), 5)

    def test_names(self):
        self.assertEqual(names_in("Thomas Chambers Hine?"), [("Thomas Chambers Hine", True)])
        self.assertEqual(names_in("Peter Frederick Robinson; Watson Fothergill (added tower)"),
                         [("Peter Frederick Robinson", False), ("Watson Fothergill", False)])
        self.assertEqual(names_in("Robert Evans JP"), [("Robert Evans JP", False)])
        self.assertEqual(numbers("1–3"), ["1", "2", "3"])
        self.assertEqual(numbers("18 and 20"), ["18", "20"])

    def test_match(self):
        b = lambda **t: {"bb": [0, 0, 1, 1], "tags": t}
        bs = [b(**{"addr:street": "Castle Grove", "addr:housenumber": "1"}), b(**{"addr:street": "Lenton Road", "addr:housenumber": "3;5"}),
              b(name="Gladstone House"), b(**{"addr:street": "Park Row", "addr:housenumber": "53"})]
        got = architect_lists({"architect_lists": [{"article": "X"}]}, bs, [], lambda titles: {"X": TABLE})
        self.assertEqual(got[0], [("Thomas Chambers Hine", False, "X")])
        self.assertEqual(got[1], [("Thomas Chambers Hine", True, "X")])          # the piped link's article, unsure
        self.assertEqual([w[0] for w in got[3]], ["Peter Frederick Robinson", "Watson Fothergill"])
        self.assertIn(2, got)


if __name__ == "__main__":
    unittest.main()
