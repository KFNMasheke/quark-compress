import hashlib
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import zlib

from quarkcompress import qcore as q


class QCoreTests(unittest.TestCase):
    def test_roundtrip_corpus(self):
        rng = random.Random(22)
        inputs = [b"", b"a", b"a" * 10000, bytes(range(256)) * 500,
                  "Water access 社区 南非\n".encode() * 1000,
                  rng.randbytes(70000), bytes(rng.randrange(8) for _ in range(10000))]
        for data in inputs:
            with self.subTest(size=len(data)):
                frame = q.compress(data)
                self.assertEqual(q.decompress(frame), data)
                self.assertTrue(q.inspect(frame)["verified"])

    def test_seeded_property_roundtrips(self):
        rng = random.Random(515)
        for _ in range(100):
            alphabet = rng.randrange(1, 257)
            data = bytes(rng.randrange(alphabet) for _ in range(rng.randrange(513)))
            self.assertEqual(q.decompress(q.compress(data)), data)

    def test_block_boundaries(self):
        for size in (q.BLOCK_SIZE - 1, q.BLOCK_SIZE, q.BLOCK_SIZE + 1):
            data = b"x" * size
            self.assertEqual(q.decompress(q.compress(data)), data)

    def test_exact_duplicate_reference(self):
        block = random.Random(67).randbytes(q.BLOCK_SIZE)
        frame = q.compress(block * 3)
        info = q.inspect(frame)
        self.assertEqual([b["method"] for b in info["blocks"]],
                         ["raw", "reference", "reference"])
        self.assertLess(len(frame), len(block) + 200)
        self.assertEqual(q.decompress(frame), block * 3)

    def test_numeric_delta_is_useful(self):
        data = bytes((i * 7) & 255 for i in range(q.BLOCK_SIZE))
        info = q.inspect(q.compress(data))
        self.assertTrue(info["blocks"][0]["method"].startswith("delta-"))

    def test_huffman_is_used(self):
        rng = random.Random(14)
        data = bytes(rng.randrange(8) for _ in range(20000))
        info = q.inspect(q.compress(data))
        self.assertIn("huffman", info["blocks"][0]["method"])

    def test_deterministic_encoding(self):
        data = b"quark" * 500
        self.assertEqual(q.compress(data), q.compress(data))

    def test_golden_raw_frame(self):
        # Independently assembled fixture, not produced by compress().
        data = b"abc"
        frame = (struct.pack(">4sQII32s", b"QKC1", 3, 65536, 1, hashlib.sha256(data).digest())
                 + struct.pack(">BIII", 0, 3, 3, zlib.crc32(data)) + data)
        self.assertEqual(q.decompress(frame), data)

    def test_overlapping_lz_match(self):
        self.assertEqual(q._lz_decode(b"\x00a\x80\x00\x01", 4), b"aaaa")

    def test_invalid_lz_tokens(self):
        for payload, size in [(b"\x80\x00\x00", 3), (b"\x80\x00\x01", 3),
                              (b"\x80", 3), (b"\x7fabc", 128), (b"\x00a", 0),
                              (b"\x00a\xff\x00\x01", 1000),
                              (b"\x00a\xff\x00\x01\x00\x01", 1000)]:
            with self.assertRaises(q.FormatError):
                q._lz_decode(payload, size)

    def test_extended_lz_match(self):
        self.assertEqual(q._lz_decode(b"\x00a\xff\x00\x01\x03\xe7", 1000),
                         b"a" * 1000)

    def test_golden_huffman_frame(self):
        data = b"a" * 1000
        lengths = bytearray(256)
        lengths[97] = 1
        payload = struct.pack(">I", 1000) + bytes(lengths) + bytes(125)
        frame = (q.FRAME.pack(q.MAGIC, 1000, q.BLOCK_SIZE, 1,
                              hashlib.sha256(data).digest())
                 + q.BLOCK.pack(q.HUFFMAN, 1000, len(payload), zlib.crc32(data))
                 + payload)
        self.assertEqual(q.decompress(frame), data)

    def test_huffman_trees_rejected(self):
        for lengths in ([0] * 256, [1, 1, 1] + [0] * 253,
                        [2, 2] + [0] * 254, [25] + [0] * 255):
            payload = struct.pack(">I", 1) + bytes(lengths) + b"\x00"
            with self.assertRaises(q.FormatError):
                q._huff_decode(payload, 100)

    def test_huffman_padding_and_trailing_data(self):
        packed = q._huff_encode(b"a")
        for bad in (packed[:-1], packed + b"\x00", packed[:-1] + b"\x01"):
            with self.assertRaises(q.FormatError):
                q._huff_decode(bad, 10)

    def test_every_truncation_rejected(self):
        frame = q.compress(b"abc" * 100)
        for end in range(len(frame)):
            with self.assertRaises(q.FormatError):
                q.decompress(frame[:end])

    def test_mutations_rejected(self):
        frame = q.compress(b"payload" * 100)
        for index in range(len(frame)):
            bad = bytearray(frame)
            bad[index] ^= 128
            with self.assertRaises(q.FormatError):
                q.decompress(bytes(bad))

    def test_trailing_and_concatenated_frames_rejected(self):
        frame = q.compress(b"abc")
        for bad in (frame + b"\x00", frame + frame):
            with self.assertRaises(q.FormatError):
                q.decompress(bad)

    def test_output_budget(self):
        frame = q.compress(b"a" * 1000)
        with self.assertRaises(q.FormatError):
            q.decompress(frame, max_output=999)
        self.assertEqual(q.decompress(q.compress(b""), max_output=0), b"")

    def test_header_budgets(self):
        for size, block_size, count in [(q.MAX_INPUT + 1, q.BLOCK_SIZE, 513),
                                        (1, 1, 1), (1, q.BLOCK_SIZE, 1000000)]:
            frame = q.FRAME.pack(q.MAGIC, size, block_size, count, b"\x00" * 32)
            with self.assertRaises(q.FormatError):
                q.decompress(frame)

    def test_forward_reference_rejected(self):
        data = b"abcd"
        frame = (q.FRAME.pack(q.MAGIC, 4, q.BLOCK_SIZE, 1, hashlib.sha256(data).digest())
                 + q.BLOCK.pack(q.REFERENCE, 4, 4, zlib.crc32(data))
                 + struct.pack(">I", 0))
        with self.assertRaises(q.FormatError):
            q.decompress(frame)

    def test_random_malformed_frames(self):
        rng = random.Random(901)
        for _ in range(1000):
            bad = rng.randbytes(rng.randrange(512))
            with self.assertRaises(q.FormatError):
                q.decompress(bad)

    def test_cli_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, packed, restored = [Path(folder) / n for n in ("in", "archive", "restored")]
            source.write_bytes(b"QCore lossless codec\n" * 100)
            cmd = [sys.executable, "-m", "quarkcompress"]
            encoded = subprocess.run(cmd + ["compress", str(source), "--codec", "qcore-1",
                                            "--output", str(packed)], capture_output=True)
            self.assertEqual(encoded.returncode, 0, encoded.stderr)
            decoded = subprocess.run(cmd + ["decompress", str(packed) + ".qkc",
                                            "--output", str(restored)], capture_output=True)
            self.assertEqual(decoded.returncode, 0, decoded.stderr)
            self.assertEqual(restored.read_bytes(), source.read_bytes())
            again = subprocess.run(cmd + ["decompress", str(packed) + ".qkc",
                                          "--output", str(restored)], capture_output=True)
            self.assertEqual(again.returncode, 1)
            self.assertEqual(restored.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
