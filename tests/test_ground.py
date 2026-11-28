"""The hills' tiles: heights written as lossless WebP come back exactly (pipeline/s09_ground.py)."""
import io
import unittest

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
