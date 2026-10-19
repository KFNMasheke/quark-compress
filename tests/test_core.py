import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quarkcompress.core import CODECS, decode, encode, publish, read_input, select, trial


class CompressionTests(unittest.TestCase):
    def test_all_codecs_roundtrip(self):
        rng = random.Random(81)
        for data in (b"", b"a", bytes(range(256)) * 30,
                     "Community GIS 南非\n".encode() * 100,
                     rng.randbytes(16384)):
            for codec in CODECS:
                with self.subTest(codec=codec, size=len(data)):
                    self.assertEqual(decode(encode(data, codec), codec), data)

    def test_auto_is_smallest_tested_candidate(self):
        data = b"Mapping community infrastructure\n" * 1000
        best, packed, trials, wall = select(data)
        self.assertEqual(len(packed), min(t.output_bytes for t in trials))
        self.assertTrue(all(t.verified for t in trials))
        self.assertGreater(wall, 0)
        self.assertEqual(decode(packed, best.codec), data)

    def test_incompressible_data_stored(self):
        data = random.Random(42).randbytes(65536)
        best, packed, _, _ = select(data)
        self.assertEqual(best.codec, "store")
        self.assertEqual(packed, data)

    def test_unknown_codec_rejected(self):
        with self.assertRaises(ValueError):
            trial(b"test", "unknown")

    def test_corrupt_stream_rejected(self):
        for codec in CODECS[1:]:
            packed = bytearray(encode(b"important payload" * 100, codec))
            packed[len(packed) // 2] ^= 255
            try:
                recovered = decode(bytes(packed), codec)
            except Exception:
                continue
            self.assertNotEqual(recovered, b"important payload" * 100)

    def test_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "existing"
            path.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                publish(path, b"replacement")
            self.assertEqual(path.read_bytes(), b"original")

    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            target, link = Path(folder) / "target", Path(folder) / "link"
            target.write_bytes(b"original")
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(FileExistsError):
                publish(link, b"replacement")
            self.assertEqual(target.read_bytes(), b"original")

    def test_input_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "oversize"
            path.write_bytes(b"12345")
            with patch("quarkcompress.core.MAX_INPUT", 4):
                with self.assertRaises(ValueError):
                    read_input(path)


if __name__ == "__main__":
    unittest.main()
