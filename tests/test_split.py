import random
import struct
import unittest

from quarkcompress import qcore as q, split


class SplitTests(unittest.TestCase):
    def test_factor_join_roundtrip(self):
        rng = random.Random(93)
        for data in (b"", b"a", b"mapping\n" * 5000, rng.randbytes(65536)):
            tokens = q._lz_encode(data)
            fields = split.factor(tokens)
            self.assertEqual(split.join(fields, 66048), tokens)
            encoded = split.pack(tokens, q._huff_encode)
            self.assertEqual(split.unpack(encoded, 66048, q._huff_decode), tokens)

    def test_v1_and_v2_read_compatibility(self):
        data = b"mapping\n" * 10000
        for version, magic in ((1, b"QKC1"), (2, b"QKC2")):
            packed = q.compress(data, format_version=version)
            self.assertEqual(packed[:4], magic)
            self.assertEqual(q.decompress(packed), data)

    def test_v1_never_emits_new_methods(self):
        data = (b"hello community mapping ward water road school\n" * 1000)
        self.assertTrue(all(b["method"] not in ("split-lz77", "delta-split-lz77")
                            for b in q.inspect(q.compress(data, format_version=1))["blocks"]))

    def test_dense_block_boundaries(self):
        for size in (q.V2_BLOCK_SIZE - 1, q.V2_BLOCK_SIZE, q.V2_BLOCK_SIZE + 1):
            data = b"quark mapping\n" * (size // 14) + b"x" * (size % 14)
            self.assertEqual(len(data), size)
            self.assertEqual(q.decompress(q.compress(data)), data)

    def test_truncations_rejected(self):
        tokens = q._lz_encode(b"a" * 1000)
        encoded = split.pack(tokens, q._huff_encode)
        for end in range(len(encoded)):
            with self.assertRaises(ValueError):
                split.unpack(encoded[:end], 66048, q._huff_decode)

    def test_trailing_and_unused_fields_rejected(self):
        encoded = split.pack(q._lz_encode(b"abc"), q._huff_encode)
        with self.assertRaises(ValueError):
            split.unpack(encoded + b"\x00", 66048, q._huff_decode)
        with self.assertRaises(ValueError):
            split.join((b"", b"a", b"", b"", b"", b""), 100)

    def test_invalid_field_budgets(self):
        for method, raw, packed in ((3, 1, 1), (0, 1000000, 1), (0, 1, 2), (1, 0, 0)):
            data = split.STREAM.pack(method, raw, packed) + b"a" * min(packed, 2)
            with self.assertRaises(ValueError):
                split.unpack(data, 66048, q._huff_decode)

    def test_compact_huffman_roundtrip(self):
        for data in (b"a" * 1000, bytes(range(256)) * 20, b"community mapping\n" * 500):
            dense = q._huff_encode(data)
            compact = split.compact_huffman(dense)
            self.assertEqual(split.expand_huffman(compact), dense)
            self.assertEqual(q._huff_decode(split.expand_huffman(compact), len(data)), data)
        self.assertLess(len(split.compact_huffman(q._huff_encode(b"a" * 1000))), 200)

    def test_bad_compact_huffman_runs(self):
        for data in (b"", bytes(6), bytes(4) + b"\xff\x19\x00",
                     bytes(4) + b"\x00\x01\xff\x01\x00",
                     bytes(4) + b"\xff\x01"):
            with self.assertRaises(ValueError):
                split.expand_huffman(data)

    def test_join_rejects_missing_components(self):
        for fields in [(b"\x00", b"", b"", b"", b"", b""),
                       (b"\x80", b"", b"", b"", b"", b""),
                       (b"\xff", b"", b"\x00", b"\x01", b"", b"")]:
            with self.assertRaises(ValueError):
                split.join(fields, 66048)

    def test_legacy_frame_rejects_v2_method(self):
        # Independent malformed header: old decoders cannot reinterpret v2 method.
        frame = (q.FRAME.pack(b"QKC1", 100, q.BLOCK_SIZE, 1, bytes(32))
                 + q.BLOCK.pack(q.SPLIT_LZ, 100, 1, 0) + b"x")
        with self.assertRaises(q.FormatError):
            q.decompress(frame)


if __name__ == "__main__":
    unittest.main()
