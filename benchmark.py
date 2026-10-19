"""Reproducible synthetic smoke corpus; not evidence of real-world superiority."""
from dataclasses import asdict
import hashlib
import json
import platform
import random
from pathlib import Path
import statistics
import sys
import zlib

import zstandard
from quarkcompress import __version__
from quarkcompress.qcore import BACKEND
from quarkcompress.core import select

rng = random.Random(20261019)
text = (b'{"ward":12,"issue":"water","status":"open","lat":-26.12}\n' * 8000)
corpus = {
    "repetitive-json": text,
    "random-binary": rng.randbytes(400000),
    "already-deflated": zlib.compress(text, 9),
    "mixed": text[:200000] + rng.randbytes(200000),
    "empty": b"",
    "synthetic-numeric-ramp": bytes((i * 7) & 255 for i in range(131072)),
    "synthetic-duplicate-blocks": random.Random(61).randbytes(65536) * 4,
}
report = {"notice": "Synthetic smoke test, including experimental QCore v1. No public corpus, native 7-Zip, or external preprocessing tested. In-memory timings exclude disk I/O. No peak-memory measurement. QCore frame overhead is included; standard codec outputs are single streams, not directory archives.",
          "environment": {"python": sys.version, "platform": platform.platform(),
                          "quark_compress": __version__,
                          "qcore_backend": BACKEND,
                          "qcore_source_sha256": hashlib.sha256(Path("quarkcompress/qcore.py").read_bytes()).hexdigest(),
                          "qcore_native_source_sha256": hashlib.sha256(Path("native/qcore_native.c").read_bytes()).hexdigest(),
                          "qcore_split_source_sha256": hashlib.sha256(Path("quarkcompress/split.py").read_bytes()).hexdigest(),
                          "zstandard_binding": zstandard.__version__,
                          "zstd": zstandard.ZSTD_VERSION, "zlib": zlib.ZLIB_RUNTIME_VERSION},
          "repetitions": 3, "warmups": 1, "files": []}
for name, data in corpus.items():
    select(data)  # warm-up
    runs = [select(data) for _ in range(3)]
    best, _, trials, _ = runs[0]
    rows = []
    for index, row in enumerate(trials):
        record = asdict(row)
        record["encode_seconds"] = statistics.median(r[2][index].encode_seconds for r in runs)
        record["decode_seconds"] = statistics.median(r[2][index].decode_seconds for r in runs)
        rows.append(record)
    report["files"].append({"name": name, "input_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "selected": best.codec,
                            "all_trials_wall_seconds_median": statistics.median(r[3] for r in runs),
                            "trials": rows})
Path("results/smoke.json").write_text(json.dumps(report, indent=2) + "\n")
print("Wrote results/smoke.json")
