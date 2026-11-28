"""The hills' tiles: heights written as lossless WebP come back exactly (pipeline/s09_ground.py)."""
import io
import tempfile
import unittest
from pathlib import Path

from pipeline.s09_ground import kept_squares

try:
    import numpy as np
    from PIL import Image, features
    from pipeline.s09_ground import encode, terrarium
    HAVE = features.check("webp")
except ImportError:       # numpy or Pillow is not installed here (the build installs them for the ground's step)
    HAVE = False


@unittest.skipUnless(HAVE, "numpy or a Pillow with WebP is not installed")
class GroundTiles(unittest.TestCase):
    def test_heights_survive_webp(self):
        # awkward heights: below sea level, whole metres, the 0.1 m steps, the byte boundaries of the encoding
        edge = np.array([-5.0, -0.1, 0.0, 0.1, 25.6, 25.5, 131.9, 255.9, 256.0, 256.1, 1000.0, 0.05, 0.04])
        rng = np.random.default_rng(1)
        h = np.concatenate([edge, rng.uniform(-10, 300, 256 * 256 - len(edge))]).reshape(256, 256).astype("float32")
        pixels = terrarium(h)
        back = np.array(Image.open(io.BytesIO(encode(pixels))).convert("RGB"))
        self.assertTrue(np.array_equal(pixels, back), "WebP changed a pixel")
        # and the heights the map reads from the pixels are the heights to 0.1 m
        heights = back[..., 0] * 256.0 + back[..., 1] + back[..., 2] / 256.0 - 32768.0
        self.assertTrue(np.allclose(heights, np.round(h, 1), atol=0.01))

    def test_smaller_than_png(self):
        x, y = np.meshgrid(np.arange(256), np.arange(256))
        pixels = terrarium((60 + 0.04 * x + 0.02 * y).astype("float32"))
        png = io.BytesIO()
        Image.fromarray(pixels, "RGB").save(png, "PNG", optimize=True)
        self.assertLess(len(encode(pixels)), png.tell())


class KeptSquares(unittest.TestCase):
    def test_latest_year_of_each_square(self):
        # the survey catalogue has been unreachable before: the squares kept from earlier stand in, named as it named them
        with tempfile.TemporaryDirectory() as d:
            for name in ("lidar_composite_dtm-2021-2m-SK54aa", "lidar_composite_dtm-2022-2m-SK54aa",
                         "lidar_composite_dtm-2022-2m-SK55bb", "lidar_composite_dtm-2022-1m-SK54aa", "web-open.tar.00"):
                (Path(d) / f"ground-{name}.zip" if name.startswith("lidar") else Path(d) / name).write_bytes(b"x")
            got = kept_squares(d)
        self.assertEqual([s["label"] for s in got],
                         ["lidar_composite_dtm-2022-2m-SK54aa", "lidar_composite_dtm-2022-2m-SK55bb"])
        self.assertTrue(all(s["uri"] is None for s in got))


class KeepLast(unittest.TestCase):
    def test_keeps_last_hills_when_they_cannot_be_built(self):
        import os
        from unittest import mock
        from pipeline import s09_ground as g
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                (Path(d) / "tiles").mkdir()
                g.save("x", "ground", {"tiles": str(Path(d) / "tiles"), "meta": {"ext": "webp"}, "rise": {"1": 2}})
                g.keep_last("x")
                self.assertEqual(g.load("x", "ground")["rise"], {"1": 2})       # untouched
                g.save("x", "ground", {"tiles": str(Path(d) / "gone"), "meta": {}})
                g.keep_last("x")
                self.assertEqual(g.load("x", "ground"), {})                      # its tiles are gone: no hills
            finally:
                os.chdir(cwd)


class SquaresAnswer(unittest.TestCase):
    def test_reads_the_catalogue_answer(self):
        import json
        from unittest import mock
        from pipeline import s09_ground as g

        def hit(product, res, year, tile, label):
            return {"product": {"id": product}, "resolution": {"label": res}, "year": {"id": year},
                    "tile": {"id": tile}, "label": label, "uri": f"https://environment.data.gov.uk/tiles/{label}"}
        answer = {"count": 3, "results": [hit("lidar_composite_dtm", "2m", "2021", "SK5035", "a21"),
                                          hit("lidar_composite_dtm", "2m", "2022", "SK5035", "a22"),
                                          hit("lidar_composite_dtm", "1m", "2022", "SK5035", "a1m")]}
        with mock.patch.object(g, "fetch", return_value=json.dumps(answer).encode()) as f:
            got = g.squares({"w": -1.2, "s": 52.9, "e": -1.1, "n": 53.0})
        self.assertEqual([s["label"] for s in got], ["a22"])
        self.assertTrue(f.call_args[0][0].startswith("https://environment.data.gov.uk/tiles/collections/survey/"))
