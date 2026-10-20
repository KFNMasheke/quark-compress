"""Lab-only block routing experiment. Not an archive API or QKC format change.

Decode ONLY locally generated experiment frames: external codecs use the trusted
trial decoders in core.py. Selection, discarded trials, framing and hashing are
all inside the encoding timer. Verification is outside both codec timers.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import random
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
from quarkcompress.core import MAX_INPUT, encode, decode

CODECS = ("store", "zstd-3", "zstd-19", "xz-6", "qcore-2")
POLICIES = ("oracle", "fast-sample", "portfolio-sample", "fixed-zstd-3")
FRAME = struct.Struct(">6sQI32s")
BLOCK = struct.Struct(">BII")
MAGIC = b"QLAB01"


def sample_block(data):
    """At most 4096 bytes, from four separated contiguous windows.

    Joining windows introduces artificial adjacency; this is a deliberately
    simple baseline and can miss patterns between windows or rare regions.
    """
    if len(data) <= 4096:
        return data
    return b"".join(data[i:i + 1024]
                    for i in (0, (len(data)-1024)//3,
                              2*(len(data)-1024)//3, len(data)-1024))


def choose(data, policy):
    if policy == "oracle":
        return min(((codec, encode(data, codec)) for codec in CODECS),
                   key=lambda item: len(item[1]))
    if policy == "fixed-zstd-3":
        codec = "zstd-3"
    elif policy in ("fast-sample", "portfolio-sample"):
        sample = sample_block(data)
        candidates = CODECS if policy == "portfolio-sample" else CODECS[:2]
        codec, packed_sample = min(((c, encode(sample, c)) for c in candidates),
                                   key=lambda item: len(item[1]))
        if len(sample) == len(data):
            return codec, packed_sample  # Reuse complete trials on small blocks.
    else:
        raise ValueError("Unknown policy")
    packed = encode(data, codec)
    # A wrong prediction must never cause payload expansion. This full-block
    # fallback cannot recover compressibility missed by a 'store' prediction.
    return (codec, packed) if len(packed) < len(data) else ("store", data)


def compress(data, policy, block_size):
    if len(data) > MAX_INPUT or block_size not in (65536, 262144):
        raise ValueError("Experiment input/block-size limit")
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    count = (len(data) + block_size - 1) // block_size
    chunks = [FRAME.pack(MAGIC, len(data), count, hashlib.sha256(data).digest())]
    decisions = Counter()
    for start in range(0, len(data), block_size):
        block = data[start:start + block_size]
        codec, packed = choose(block, policy)
        chunks.extend((BLOCK.pack(CODECS.index(codec), len(block), len(packed)), packed))
        decisions[codec] += 1
    return b"".join(chunks), dict(decisions)


def restore_local(frame):
    """Trusted benchmark artifacts only; do not expose to uploaded archives."""
    if len(frame) < FRAME.size:
        raise ValueError("Truncated experiment")
    magic, size, count, digest = FRAME.unpack_from(frame)
    if magic != MAGIC or size > MAX_INPUT or count > (size + 65535)//65536:
        raise ValueError("Invalid experiment header")
    position, output = FRAME.size, bytearray()
    for _ in range(count):
        if position + BLOCK.size > len(frame):
            raise ValueError("Truncated block")
        codec_id, raw_size, packed_size = BLOCK.unpack_from(frame, position)
        position += BLOCK.size
        if (codec_id >= len(CODECS) or not 0 < raw_size <= 262144
                or packed_size > raw_size or position + packed_size > len(frame)
                or len(output) + raw_size > size):
            raise ValueError("Invalid block")
        restored = decode(frame[position:position+packed_size], CODECS[codec_id])
        if len(restored) != raw_size:
            raise ValueError("Block size mismatch")
        output.extend(restored)
        position += packed_size
    if (position != len(frame) or len(output) != size
            or hashlib.sha256(output).digest() != digest):
        raise ValueError("Experiment integrity mismatch")
    return bytes(output)


def external_inputs(corpus_root, manifest_path):
    """Integrity-checked operator-supplied corpus; independence is not inferred."""
    root, manifest_file = Path(corpus_root).resolve(), Path(manifest_path)
    if manifest_file.stat().st_size > 1024 * 1024:
        raise ValueError('Corpus manifest exceeds 1 MiB')
    manifest = json.loads(manifest_file.read_text())
    if not isinstance(manifest, dict) or manifest.get('split') != 'held-out':
        raise ValueError('External manifest must declare split: held-out')
    files = manifest.get('files')
    if not isinstance(files, list) or not 1 <= len(files) <= 10000:
        raise ValueError('External manifest needs 1-10000 files')
    seen = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str):
            raise ValueError('Invalid corpus entry')
        name = item['name']
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or '..' in relative.parts
                or '\\' in name or str(relative) != name or name in seen):
            raise ValueError('Unsafe or duplicate corpus path')
        seen.add(name)
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Corpus path must remain inside root')
        size = item.get('bytes')
        if type(size) is not int or not 0 <= size <= MAX_INPUT or path.stat().st_size != size:
            raise ValueError('Corpus size mismatch or input limit')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item.get('sha256'):
            raise ValueError('Corpus integrity mismatch')
        yield name, 'external held-out (operator-declared)', data


def inputs(corpus_root=None, manifest_path=None):
    if corpus_root is not None or manifest_path is not None:
        if corpus_root is None or manifest_path is None:
            raise ValueError('Supply both corpus root and manifest')
        yield from external_inputs(corpus_root, manifest_path)
        return
    manifest = json.loads((ROOT / "benchmarks/canterbury_manifest.json").read_text())
    for item in manifest["files"]:
        data = (ROOT / "corpora/canterbury" / item["name"]).read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Corpus integrity mismatch")
        yield item["name"], "Canterbury development", data
    rng = random.Random(20261019)
    text = (b"community water school road infrastructure inspection\n" * 6000)[:262144]
    noise = rng.randbytes(262144)
    numbers = b"".join(struct.pack("<I", i) for i in range(65536))
    mixed = text + noise + numbers + encode(text, "zstd-3")
    yield "mixed-aligned", "synthetic diagnostic", mixed
    yield "mixed-offset", "synthetic diagnostic", b"offset" * 123 + mixed
    yield "sample-trap", "synthetic diagnostic", noise[:1024] + bytes(260096) + noise[-1024:]


def worker(name, config, repeats, corpus_root=None, manifest_path=None):
    from benchmarks.run_suite import peak_rss
    data = next(data for key, _, data in inputs(corpus_root, manifest_path) if key == name)
    encodes, decodes, expected = [], [], None
    for iteration in range(repeats + 1):
        start = time.perf_counter()
        if config.startswith("whole:"):
            codec = config.split(":")[1]
            packed, decisions = encode(data, codec), {codec: 1}
        else:
            policy, block_size = config.split(":")
            packed, decisions = compress(data, policy, int(block_size))
        enc = time.perf_counter() - start
        start = time.perf_counter()
        restored = decode(packed, codec) if config.startswith("whole:") else restore_local(packed)
        dec = time.perf_counter() - start
        if restored != data or (expected is not None and len(packed) != expected):
            raise RuntimeError("Restoration or deterministic-size failure")
        expected = len(packed)
        if iteration:
            encodes.append(enc)
            decodes.append(dec)
    return {"config": config, "output_bytes": expected, "decisions": decisions,
            "encode_seconds": statistics.median(encodes),
            "decode_seconds": statistics.median(decodes),
            "encode_range": [min(encodes), max(encodes)],
            "decode_range": [min(decodes), max(decodes)],
            "peak_process_rss_bytes": peak_rss(), "verified": True}


def main():
    import zstandard
    from quarkcompress import qcore
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "results/adaptive.json")
    parser.add_argument('--corpus-root', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if bool(args.corpus_root) != bool(args.manifest):
        parser.error('Supply both --corpus-root and --manifest')
    if args.manifest and args.output.resolve() == (ROOT / 'results/adaptive.json').resolve():
        parser.error('Use a separate --output for external evaluation')
    if args.repeats < 1 or qcore.BACKEND != "native":
        parser.error("Positive repetitions and native QCore are required")
    configs = [f"whole:{c}" for c in CODECS[1:]]
    configs += [f"{p}:{b}" for b in (65536, 262144) for p in POLICIES]
    sources = ("benchmarks/adaptive_experiment.py", "quarkcompress/core.py",
               "quarkcompress/qcore.py", "quarkcompress/split.py", "native/qcore_native.c")
    report = {"complete": False, "python": sys.version, "platform": platform.platform(),
              "zstandard_binding": zstandard.__version__, "zstd": zstandard.ZSTD_VERSION,
              "qcore_backend": qcore.BACKEND, "repetitions": args.repeats, "warmups": 1,
              "sources": {s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
              "portfolio": CODECS, "sample_bytes": 4096,
              "measurement": "Sequential isolated child per input/config. Full selection, discarded trials, SHA-256 and actual lab framing inside encode timer. Decode includes integrity check. Byte comparison outside timers. I/O and startup excluded. Whole baselines retain native stream framing. No memory cap; RSS includes process/input/warmup. The default corpus is development data; external split is operator-declared. Oracle optimal only for this portfolio, partition and frame.",
              "files": []}
    if args.manifest:
        report['external_manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
        report['split_note'] = 'Held-out is operator-declared. This harness cannot establish that no tuning used these files.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name, group, data in inputs(args.corpus_root, args.manifest):
        row = {"name": name, "group": group, "input_bytes": len(data),
               "sha256": hashlib.sha256(data).hexdigest(), "trials": []}
        for config in configs:
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--worker', name, config, str(args.repeats)]
            if args.manifest:
                command.extend([str(args.corpus_root.resolve()), str(args.manifest.resolve())])
            result = subprocess.run(command,
                                    capture_output=True, text=True, check=True, timeout=180)
            row["trials"].append(json.loads(result.stdout))
        report["files"].append(row)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Verified {name}", flush=True)
    report["complete"] = True
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        print(json.dumps(worker(sys.argv[2], sys.argv[3], int(sys.argv[4]), *sys.argv[5:])))
    else:
        main()
