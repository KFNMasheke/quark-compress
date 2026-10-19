"""Regression checks for experiment accounting and routing counterexamples."""
import random
import unittest
import importlib.util
from pathlib import Path

# Load the lab script without putting the source tree ahead of an isolated
# sanitizer installation of quarkcompress on sys.path.
spec = importlib.util.spec_from_file_location(
    "quark_adaptive_lab", Path(__file__).resolve().parents[1] / "benchmarks/adaptive_experiment.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
BLOCK, CODECS, FRAME, POLICIES = lab.BLOCK, lab.CODECS, lab.FRAME, lab.POLICIES
choose, compress = lab.choose, lab.compress
restore_local, sample_block = lab.restore_local, lab.sample_block
from quarkcompress.core import encode


class AdaptiveTests(unittest.TestCase):
    def test_mixed_regions_restore_and_frame_accounting(self):
        data = b"mapping\n" * 10000 + random.Random(71).randbytes(65536)
        for policy in POLICIES:
            packed, counts = compress(data, policy, 65536)
            self.assertEqual(restore_local(packed), data)
            self.assertEqual(sum(counts.values()), 3)
        raw, counts = compress(random.Random(71).randbytes(65536), "oracle", 65536)
        self.assertEqual(counts, {"store": 1})
        self.assertEqual(len(raw), FRAME.size + BLOCK.size + 65536)

    def test_oracle_is_smallest_for_same_partition(self):
        data = b"water inspection\n" * 300
        codec, payload = choose(data, "oracle")
        self.assertEqual(len(payload), min(len(encode(data, c)) for c in CODECS))
        for policy in POLICIES:
            self.assertLessEqual(len(compress(data, "oracle", 65536)[0]),
                                 len(compress(data, policy, 65536)[0]))

    def test_sample_miss_is_preserved_as_counterexample(self):
        data = bytearray(65536)
        noise = random.Random(17).randbytes(4096)
        positions = (0, (len(data)-1024)//3, 2*(len(data)-1024)//3, len(data)-1024)
        for index, position in enumerate(positions):
            data[position:position+1024] = noise[index*1024:(index+1)*1024]
        data = bytes(data)
        self.assertEqual(len(sample_block(data)), 4096)
        codec, payload = choose(data, "fast-sample")
        self.assertEqual(codec, "store")
        self.assertLess(len(choose(data, "oracle")[1]), len(payload)//2)
        self.assertEqual(restore_local(compress(data, "fast-sample", 65536)[0]), data)

    def test_integrity_and_invalid_experiment_options(self):
        packed, _ = compress(b"", "oracle", 65536)
        self.assertEqual(restore_local(packed), b"")
        for bad in (packed + b"x", packed[:-1], b"invalid"):
            with self.assertRaises(ValueError):
                restore_local(bad)
        for policy, size in (("unknown", 65536), ("oracle", 1)):
            with self.assertRaises(ValueError):
                compress(b"abc", policy, size)


if __name__ == "__main__":
    unittest.main()
