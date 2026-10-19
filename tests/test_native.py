import random
import struct
import unittest
from unittest.mock import patch

from quarkcompress import qcore as q, split


@unittest.skipIf(q._native is None, "Optional native accelerator not active")
class NativeTests(unittest.TestCase):
    def test_lz_cross_decode(self):
        rng = random.Random(98)
        for data in (b"", b"a", b"a" * 65536, bytes(range(256)) * 256,
                     rng.randbytes(65536), b"mapping data\n" * 1000):
            for encoder in (q._python_lz_encode, q._native.lz_encode):
                encoded = encoder(data)
                self.assertEqual(q._python_lz_decode(encoded, len(data)), data)
                self.assertEqual(q._native.lz_decode(encoded, len(data)), data)

    def test_delta_compatibility(self):
        data = random.Random(19).randbytes(65536)
        self.assertEqual(q._native.delta(data), q._python_delta(data))
        self.assertEqual(q._native.undelta(data), q._python_undelta(data))

    def test_huffman_cross_decode(self):
        rng = random.Random(16)
        for data in (b"a", b"a" * 65536, bytes(range(256)) * 50,
                     bytes(rng.randrange(8) for _ in range(30000))):
            encoded = q._huff_encode(data)
            self.assertEqual(q._python_huff_decode(encoded, len(data)), data)
            self.assertEqual(q._native.huff_decode(encoded, len(data)), data)

    def test_native_huffman_matches_reference_bytes(self):
        rng = random.Random(59)
        native = q._native
        samples = [b"", b"a", bytes(range(256)) * 10]
        samples += [bytes(rng.randrange(rng.randrange(1, 257)) for _ in range(2000))
                    for _ in range(30)]
        for data in samples:
            with patch.object(q, "_native", None):
                reference = q._huff_encode(data)
            self.assertEqual(native.huff_encode(data), reference)

    def test_native_input_bounds(self):
        too_large = bytes(q.V2_BLOCK_SIZE + 1)
        for name in ("lz_encode", "delta", "undelta"):
            with self.assertRaises(ValueError):
                getattr(q._native, name)(too_large)
        for size in (-1, q.V2_BLOCK_SIZE + 1):
            with self.assertRaises(ValueError):
                q._native.lz_decode(b"", size)

    def test_reject_missing_huffman_symbols(self):
        lengths = bytearray(256)
        lengths[97] = 1
        with self.assertRaises(ValueError):
            q._native.huff_pack(b"b", bytes(lengths))

    def test_native_parser_mutations(self):
        rng = random.Random(56)
        for _ in range(1000):
            payload = rng.randbytes(rng.randrange(300))
            expected = rng.randrange(512)
            for decoder in (q._native.lz_decode, q._python_lz_decode):
                try:
                    result = decoder(payload, expected)
                except ValueError:
                    continue
                self.assertEqual(len(result), expected)

    def test_huffman_rejection_matches_reference(self):
        rng = random.Random(57)
        seed = q._huff_encode(bytes(range(256)) * 8)
        for _ in range(300):
            data = bytearray(seed)
            pos = rng.randrange(len(data))
            data[pos] ^= 1 << rng.randrange(8)
            outcomes = []
            for decoder in (q._native.huff_decode, q._python_huff_decode):
                try:
                    outcomes.append((True, decoder(bytes(data), 2048)))
                except ValueError:
                    outcomes.append((False, None))
            self.assertEqual(outcomes[0], outcomes[1])

    def test_factoring_cross_compatibility(self):
        data = (b"Community infrastructure dataset\n" * 4000)
        tokens = q._native.lz_encode(data)
        fields = split._python_factor(tokens)
        self.assertEqual(q._native.factor(tokens), fields)
        self.assertEqual(q._native.join(fields, 264192), tokens)
        self.assertEqual(split._python_join(fields, 264192), tokens)

    def test_factor_rejection_matches_reference(self):
        rng = random.Random(58)
        for _ in range(1000):
            data = rng.randbytes(rng.randrange(512))
            results = []
            for func in (q._native.factor, split._python_factor):
                try:
                    results.append((True, func(data)))
                except ValueError:
                    results.append((False, None))
            self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
