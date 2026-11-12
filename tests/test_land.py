"""The land's shapes (pipeline/s06_land.py): which layer an OpenStreetMap element goes to, outlines joined from
their parts, and a line's years from the hand-checked table, Wikidata or OpenStreetMap."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import s06_land as L


def way(i, tags, pts):
    return {"type": "way", "id": i, "tags": tags, "geometry": [{"lon": x, "lat": y} for x, y in pts]}


class Kinds(unittest.TestCase):
    def test_kinds(self):
        k = L.kind
        self.assertEqual(k({"railway": "abandoned"}), "rail")
        self.assertEqual(k({"highway": "cycleway", "abandoned:railway": "rail"}), "rail")
        self.assertIsNone(k({"railway": "rail", "disused:railway": "rail"}))        # still a working line
        self.assertIsNone(k({"abandoned:railway": "station"}))
        self.assertEqual(k({"waterway": "canal", "disused": "yes"}), "canal")
        self.assertEqual(k({"abandoned:waterway": "canal"}), "canal")
        self.assertIsNone(k({"waterway": "canal"}))                                    # in use: the main map has it
        self.assertEqual(k({"waterway": "stream"}), "brook")
        self.assertEqual(k({"natural": "water", "water": "pond"}), "pond")
        self.assertEqual(k({"landuse": "forest"}), "wood")
        self.assertEqual(k({"historic": "archaeological_site"}), "oldsite")
        self.assertEqual(k({"natural": "cave_entrance"}), "oldsite")
        self.assertEqual(k({"amenity": "grave_yard"}), "cemetery")
        self.assertEqual(k({"landuse": "allotments"}), "allot")
        self.assertEqual(k({"landuse": "orchard"}), "orchard")
        self.assertIsNone(k({"building": "yes"}))

    def test_join_rings(self):
        a, b = [[0, 0], [1, 0], [1, 1]], [[0, 0], [0, 1], [1, 1]]     # two halves, the second the wrong way round
        rings = L.join([a, b])
        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0][0], rings[0][-1])

    def test_geometry(self):
        sq = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
        self.assertEqual(L.geometry(way(1, {}, sq), {}, "wood")["type"], "Polygon")
        self.assertEqual(L.geometry(way(2, {}, sq), {}, "rail")["type"], "LineString")
        walls = {"historic": "citywalls"}
        self.assertEqual(L.geometry(way(3, walls, sq), walls, "oldsite")["type"], "LineString")


class Years(unittest.TestCase):
    def test_years_and_entries(self):
        line1 = way(10, {"railway": "abandoned", "name": "Old Line", "start_date": "1880"}, [(0, 0), (0.01, 0)])
        line2 = way(11, {"railway": "abandoned", "name": "Old Line", "end_date": "1960"}, [(0.01, 0), (0.02, 0)])
        canal = way(12, {"abandoned:waterway": "canal", "name": "Lost Cut", "wikidata": "Q1"}, [(0, 1), (0.01, 1)])
        checked = way(13, {"railway": "dismantled", "name": "Checked Line", "start_date": "1800"}, [(0, 2), (0.01, 2)])
        brook = way(14, {"waterway": "brook", "tunnel": "culvert"}, [(0, 3), (0.01, 3)])
        saved = {}
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                Path("stories/x").mkdir(parents=True)
                Path("stories/x/old-lines.md").write_text(
                    "| Name in OpenStreetMap | Opened | Closed | Source | Note |\n|---|---|---|---|---|\n"
                    "| Checked Line | 1850 | 1951 | https://en.wikipedia.org/wiki/X | |\n")
                with mock.patch.object(L, "city", return_value={}), \
                        mock.patch.object(L, "work", return_value=mock.Mock(exists=lambda: True)), \
                        mock.patch.object(L, "load", side_effect=lambda c, n: {"elements": [line1, line2, canal, checked, brook]}
                                          if n == "land_osm" else {"elements": []}), \
                        mock.patch.object(L, "wikidata_years", return_value={"Q1": (1796, 1937)}), \
                        mock.patch.object(L, "save", side_effect=lambda c, n, o: saved.update(o)):
                    L.main("x")
            finally:
                os.chdir(cwd)
        es = {e["name"]: e for e in saved["entries"]}
        self.assertEqual((es["Old Line"]["from"], es["Old Line"]["to"]), (1880, 1960))     # OpenStreetMap, both parts
        self.assertEqual(es["Old Line"]["fromSrc"], "OpenStreetMap")
        self.assertEqual((es["Lost Cut"]["from"], es["Lost Cut"]["to"], es["Lost Cut"]["toSrc"]), (1796, 1937, "Wikidata"))
        self.assertEqual((es["Checked Line"]["from"], es["Checked Line"]["to"]), (1850, 1951))   # the table first
        parts = [f["properties"] for f in saved["features"] if f["properties"]["t"] == "rail"]
        self.assertTrue(all(p.get("y0") and p.get("y1") for p in parts))
        b = next(f["properties"] for f in saved["features"] if f["properties"]["t"] == "brook")
        self.assertEqual((b.get("u"), b.get("k")), (1, "Brook"))
        groups = {g["key"]: g for m in saved["meta"] for g in m["groups"]}
        self.assertEqual(groups["rail"]["count"], 3)
        self.assertEqual([it[0] for it in groups["rail"]["items"]], ["Checked Line", "Old Line"])
        json.dumps(saved)          # what the package writes


if __name__ == "__main__":
    unittest.main()
