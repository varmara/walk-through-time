"""The graph's layout worked out in the build (pipeline/graph_layout.mjs, with the page's app/city/graphlayout.js),
the pages' file version (pipeline/pages.py) and which step a change to the layout code rebuilds (pipeline/plan.py)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline import pages
from pipeline.plan import needs_build, start_for

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "needs Node")
class Layout(unittest.TestCase):
    def test_positions(self):
        nodes = [{"id": "t:inns", "type": "theme", "label": "Old inns"},
                 {"id": "x", "type": "architects", "label": "An Architect"},
                 {"id": "b1", "type": "place", "label": "Shared"},
                 {"id": "b2", "type": "place", "label": "Only the architect's"}]
        links = [{"s": "t:inns", "t": "b1"}, {"s": "x", "t": "b1"}, {"s": "x", "t": "b2"}]
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "g.json"
            f.write_text(json.dumps({"nodes": nodes, "links": links}))
            subprocess.run(["node", str(ROOT / "pipeline" / "graph_layout.mjs"), str(f)], check=True, capture_output=True)
            out = {n["id"]: n for n in json.loads(f.read_text())["nodes"]}
        for i in ("t:inns", "x", "b1"):
            self.assertIsInstance(out[i]["x"], (int, float))
        self.assertNotIn("x", out["b2"])           # folded into its architect: placed when spread out
        self.assertEqual(len(links), 3)


class Pages(unittest.TestCase):
    def test_version_follows_content(self):
        v = pages.version()
        self.assertRegex(v, r"^[0-9a-f]{10}$")
        self.assertEqual(v, pages.version())

    def test_plan(self):
        self.assertTrue(needs_build("app/city/graphlayout.js"))
        self.assertFalse(needs_build("app/city/graph.js"))
        self.assertEqual(start_for(["app/city/graphlayout.js"]), "s08_graph")
        self.assertEqual(start_for(["pipeline/graph_layout.mjs"]), "s08_graph")


if __name__ == "__main__":
    unittest.main()
