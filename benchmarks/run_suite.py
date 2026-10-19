"""Isolated-process Canterbury comparisons with exact-byte input verification.

Run from repository root. Source data are downloaded separately and never
redistributed by this repository. Results do not establish world-best parity.
"""
import argparse
import bz2
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CODECS = ("qcore-python-v1", "qcore-native-v1", "qcore-native-v2", "gzip-9", "zstd-3", "zstd-19",
          "zstd-22", "xz-9", "xz-9e", "bzip2-9")


def peak_rss():
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak if sys.platform == "darwin" else peak * 1024
    except ImportError:
        return None


def worker(codec, path, repeats):
    import gzip
    import zstandard as zstd
    from quarkcompress import qcore
    data = path.read_bytes()
    if codec.startswith("qcore-native") and qcore.BACKEND != "native":
        raise RuntimeError("Native extension must be built to benchmark native codec")
    if codec.startswith("qcore"):
        version = 2 if codec.endswith("v2") else 1
        encode = lambda value: qcore.compress(value, format_version=version)
        decode = qcore.decompress
    elif codec.startswith("zstd-"):
        def encode(value):
            return zstd.ZstdCompressor(level=int(codec.split("-")[1]),
                                      write_checksum=True).compress(value)
        decode = zstd.ZstdDecompressor().decompress
    elif codec == "gzip-9":
        encode = lambda value: gzip.compress(value, compresslevel=9, mtime=0)
        decode = gzip.decompress
    elif codec.startswith("xz-"):
        preset = 9 | (lzma.PRESET_EXTREME if codec.endswith("e") else 0)
        encode = lambda value: lzma.compress(value, preset=preset)
        decode = lzma.decompress
    else:
        encode = lambda value: bz2.compress(value, compresslevel=9)
        decode = bz2.decompress
    encodes, decodes = [], []
    output_size = None
    for index in range(repeats + 1):
        start = time.perf_counter()
        packed = encode(data)
        encoding = time.perf_counter() - start
        start = time.perf_counter()
        restored = decode(packed)
        decoding = time.perf_counter() - start
        if restored != data:
            raise RuntimeError("Byte-exact recovery failed")
        if output_size is not None and output_size != len(packed):
            raise RuntimeError("Nondeterministic compressed size")
        output_size = len(packed)
        if index:
            encodes.append(encoding)
            decodes.append(decoding)
        del packed, restored
    return {"codec": codec, "input_bytes": len(data), "output_bytes": output_size,
            "encode_seconds_median": statistics.median(encodes),
            "decode_seconds_median": statistics.median(decodes),
            "encode_seconds_range": [min(encodes), max(encodes)],
            "decode_seconds_range": [min(decodes), max(decodes)],
            "process_peak_rss_bytes": peak_rss(), "verified": True}


def run(args):
    import zstandard as zstd
    from quarkcompress import __version__
    manifest = json.loads((ROOT / "benchmarks/canterbury_manifest.json").read_text())
    report = {"suite": "Canterbury (all 11 files)", "manifest": manifest,
              "quark_version": __version__, "python": sys.version,
              "platform": platform.platform(), "processor": platform.processor(),
              "zstandard_binding": zstd.__version__, "zstd": zstd.ZSTD_VERSION,
              "repetitions": args.repeats, "warmups": 1,
              "qcore_source_sha256": hashlib.sha256((ROOT / "quarkcompress/qcore.py").read_bytes()).hexdigest(),
              "native_source_sha256": hashlib.sha256((ROOT / "native/qcore_native.c").read_bytes()).hexdigest(),
              "split_source_sha256": hashlib.sha256((ROOT / "quarkcompress/split.py").read_bytes()).hexdigest(),
              "measurement": "Sequential isolated child process per file and codec; in-memory codec work only. Peak RSS includes interpreter, input and warmup; it is not incremental codec allocation. No cold-disk throughput measurement or 7-Zip/native XZ equivalence claim.",
              "files": []}
    for item in manifest["files"]:
        path = ROOT / "corpora/canterbury" / item["name"]
        data = path.read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise RuntimeError(f"Corpus hash mismatch: {path.name}")
        row = {"name": path.name, "input_bytes": len(data), "trials": []}
        for codec in CODECS:
            env = dict(os.environ, QUARK_PURE_PYTHON="1" if codec == "qcore-python-v1" else "0")
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     "--worker", codec, str(path), str(args.repeats)],
                                    env=env, capture_output=True, text=True, check=True, timeout=120)
            row["trials"].append(json.loads(result.stdout))
        report["files"].append(row)
        # Checkpoint only completed files; final report marks completion.
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Verified {path.name}", flush=True)
    report["complete"] = True
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        print(json.dumps(worker(sys.argv[2], Path(sys.argv[3]), int(sys.argv[4]))))
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--repeats", type=int, default=3)
        parser.add_argument("--output", type=Path, default=ROOT / "results/canterbury.json")
        arguments = parser.parse_args()
        if arguments.repeats < 1:
            parser.error("--repeats must be positive")
        run(arguments)
