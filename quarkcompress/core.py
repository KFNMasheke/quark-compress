"""Bounded whole-file trials of standard engines and experimental QCore."""
from dataclasses import dataclass
import gzip
import hashlib
import lzma
from pathlib import Path
import time

import zstandard as zstd

from . import qcore

MAX_INPUT = 32 * 1024 * 1024
CODECS = ("store", "gzip-9", "zstd-3", "zstd-19", "xz-6", "xz-9", "qcore-1", "qcore-2")
SUFFIX = {"store": ".raw", "gzip-9": ".gz", "zstd-3": ".zst",
          "zstd-19": ".zst", "xz-6": ".xz", "xz-9": ".xz", "qcore-1": ".qkc", "qcore-2": ".qkc"}


@dataclass
class Trial:
    codec: str
    input_bytes: int
    output_bytes: int
    encode_seconds: float
    decode_seconds: float
    sha256: str
    verified: bool


def read_input(path: Path) -> bytes:
    # Read one extra byte so changing files cannot bypass the allocation bound.
    with path.open("rb") as stream:
        data = stream.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError("Lab limit is 32 MiB per file; streaming is a later milestone")
    return data


def encode(data: bytes, codec: str) -> bytes:
    if codec in ("qcore-1", "qcore-2"):
        return qcore.compress(data, format_version=int(codec[-1]))
    if codec == "store":
        return data
    if codec == "gzip-9":
        return gzip.compress(data, compresslevel=9, mtime=0)
    if codec.startswith("zstd-") and codec in CODECS:
        return zstd.ZstdCompressor(level=int(codec.split("-")[1]),
                                  write_checksum=True).compress(data)
    if codec.startswith("xz-") and codec in CODECS:
        return lzma.compress(data, preset=int(codec.split("-")[1]))
    raise ValueError("Unknown codec")


def decode(data: bytes, codec: str) -> bytes:
    """Trusted locally generated trial data only. Not an untrusted archive API."""
    if codec in ("qcore-1", "qcore-2"):
        return qcore.decompress(data)
    if codec == "store":
        return data
    if codec == "gzip-9":
        return gzip.decompress(data)
    if codec.startswith("zstd-") and codec in CODECS:
        return zstd.ZstdDecompressor().decompress(data, max_output_size=MAX_INPUT)
    if codec.startswith("xz-") and codec in CODECS:
        return lzma.decompress(data, memlimit=256 * 1024 * 1024)
    raise ValueError("Unknown codec")


def trial(data: bytes, codec: str) -> tuple[Trial, bytes]:
    if len(data) > MAX_INPUT:
        raise ValueError("Input exceeds lab limit")
    start = time.perf_counter()
    packed = encode(data, codec)
    encoded = time.perf_counter() - start
    start = time.perf_counter()
    recovered = decode(packed, codec)
    decoded = time.perf_counter() - start
    if recovered != data:
        raise ValueError(f"Round-trip mismatch: {codec}")
    return Trial(codec, len(data), len(packed), encoded, decoded,
                 hashlib.sha256(data).hexdigest(), True), packed


def select(data: bytes) -> tuple[Trial, bytes, list[Trial], float]:
    """Exhaustive size oracle, NOT a fast predictive selector.

    Runs all codecs, includes raw storage, holds only the best payload.
    Wall time includes every trial and round-trip verification.
    """
    start = time.perf_counter()
    best, payload = None, b""
    results = []
    for codec in CODECS:
        result, candidate = trial(data, codec)
        results.append(result)
        if best is None or result.output_bytes < best.output_bytes:
            best, payload = result, candidate
    return best, payload, results, time.perf_counter() - start


def publish(output: Path, data: bytes) -> None:
    """Exclusive creation, including protection against existing symlinks."""
    with output.open("xb") as stream:
        try:
            stream.write(data)
        except BaseException:
            stream.close()
            output.unlink(missing_ok=True)
            raise
