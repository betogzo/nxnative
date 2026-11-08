"""NSP script --icon (scripts/build_ipa_from_nsp.py custom_icon): the player's image becomes the 1024x1024 JPEG the app's icon is made from, cropped to its centre square, and a
missing or unreadable file stops the build. Needs macOS's sips; no game files."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('build_ipa_from_nsp', REPO / 'scripts/build_ipa_from_nsp.py')
assert spec and spec.loader
nsp = importlib.util.module_from_spec(spec); spec.loader.exec_module(nsp)


def png(path, w, h, pixel):   # an RGB PNG whose pixel(x, y) gives each (r, g, b)
    rows = b''.join(b'\0' + bytes(c for x in range(w) for c in pixel(x, y)) for y in range(h))
    def chunk(kind, data): return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def size(path):
    out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', '-g', 'format', str(path)], capture_output=True, text=True).stdout
    return {k: v for k, _, v in (line.strip().partition(': ') for line in out.splitlines()[1:])}


@unittest.skipUnless(sys.platform == 'darwin', 'sips is macOS only')
class CustomIcon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
        quiet = mock.patch.object(nsp, 'say', lambda msg: None); quiet.start(); self.addCleanup(quiet.stop)

    def tearDown(self): self.tmp.cleanup()

    def test_a_wide_image_becomes_its_centre_square_at_1024(self):
        src = self.dir / 'wide.png'
        png(src, 300, 200, lambda x, y: (255, 0, 0) if x < 50 or x >= 250 else (0, 200, 0))   # red bars outside the centre 200x200
        out = nsp.custom_icon(src, self.dir / 'work')
        self.assertEqual(out, self.dir / 'work/app/icon.jpg')
        self.assertEqual(size(out), {'pixelWidth': '1024', 'pixelHeight': '1024', 'format': 'jpeg'})
        self.assertFalse((self.dir / 'work/app/icon.part.jpg').exists())
        try: from PIL import Image   # pyright: ignore[reportMissingImports]  # in the tools venv (tools.txt), not the lint one
        except ImportError: return
        with Image.open(out) as im:
            for xy in ((4, 4), (1019, 4), (4, 1019), (1019, 1019), (512, 512)):   # corners and centre: the red bars were cut away
                r, g, b = im.convert('RGB').getpixel(xy)
                self.assertGreater(g, 150, xy); self.assertLess(r, 60, xy)

    def test_a_tall_image_is_cropped_too(self):
        src = self.dir / 'tall.png'
        png(src, 120, 400, lambda x, y: (10, 20, 30))
        self.assertEqual(size(nsp.custom_icon(src, self.dir / 'work'))['pixelWidth'], '1024')

    def test_a_missing_file_stops_the_build(self):
        with self.assertRaises(nsp.BuildError): nsp.custom_icon(self.dir / 'none.png', self.dir / 'work')

    def test_a_file_that_is_no_image_stops_the_build(self):
        src = self.dir / 'notes.png'; src.write_text('not an image')
        with self.assertRaises(nsp.BuildError): nsp.custom_icon(src, self.dir / 'work')


if __name__ == '__main__':
    unittest.main()
