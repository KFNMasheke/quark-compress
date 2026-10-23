"""Real concurrent codec and exclusive-output regression tests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from quarkcompress.core import decode, encode, publish


class ConcurrencyTests(unittest.TestCase):
    def test_parallel_codec_round_trips_do_not_share_mutable_state(self):
        tasks = [("store", b"raw" * 2048), ("gzip-9", b"gzip" * 4096),
                 ("zstd-3", bytes(range(256)) * 64),
                 ("xz-6", b"archive" * 2048),
                 ("qcore-1", b"QCore candidate " * 512)] * 2
        gate = threading.Barrier(len(tasks))

        def run(task):
            codec, payload = task
            gate.wait(timeout=15)
            packed = encode(payload, codec)
            return decode(packed, codec) == payload

        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            self.assertTrue(all(pool.map(run, tasks)))

    def test_simultaneous_publication_has_exactly_one_winner(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "shared.qkc"
            workers = 12
            gate = threading.Barrier(workers)

            def publish_once(number):
                gate.wait(timeout=15)
                try:
                    publish(target, f"worker-{number}".encode())
                    return number
                except FileExistsError:
                    return None

            with ThreadPoolExecutor(max_workers=workers) as pool:
                winners = [x for x in pool.map(publish_once, range(workers)) if x is not None]
            self.assertEqual(len(winners), 1)
            self.assertEqual(target.read_bytes(), f"worker-{winners[0]}".encode())


if __name__ == "__main__":
    unittest.main()
