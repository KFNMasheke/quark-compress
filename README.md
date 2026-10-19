# Quark Compress

**Smaller files. Every bit preserved.**

[![Tests](https://github.com/KFNMasheke/quark-compress/actions/workflows/test.yml/badge.svg)](https://github.com/KFNMasheke/quark-compress/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An open-source lossless compression project with **QCore**, an independent
experimental codec, and a lab comparing it against established engines.

Working project by Kaziwale Masheke. Version 0.4 is a research implementation,
not a finished desktop archiver. QCore implements established techniques in
original code; it does not claim a novel algorithm or general superiority.

## What works today

- QCore: LZ77 matching, canonical Huffman coding, reversible byte deltas,
  exact duplicate-block references, raw fallback, CRC32 and SHA-256 verification.
- QCore v2: separately coded token fields and complete-frame selection between
  64 KiB and 256 KiB blocks, with compact Huffman model headers.
  QKC1 files remain readable.
- Optional original C acceleration, with a pure-Python reference fallback.
- Trials of QCore, Zstandard 3/19, XZ/LZMA2 6/9, gzip 9, and raw storage.
- Exhaustive smallest-output selection, including a no-compression fallback.
- Byte-for-byte restoration checks, SHA-256 reporting, encode/decode timings.
- Standard `.zst`, `.xz`, `.gz` outputs; `.raw` means an unchanged copy.
- QCore `.qkc` encoding, bounded decoding and verified block inspection.
- Exclusive output creation: existing files and symlinks are not overwritten.
- Unit tests and a Windows/Linux/macOS CI matrix.

The exhaustive selector compresses the entire input with every candidate. This
gives a smallest-size baseline among those candidates, at substantial CPU cost.
It is not yet a smart predictor, directory archiver, or improvement to Zstd.
Trial timings include codec work; total selection wall time includes all trials
and verification. Reports explicitly distinguish these quantities.

## Quick start

Python 3.11 or newer:

```sh
git clone https://github.com/KFNMasheke/quark-compress.git
cd quark-compress
python -m pip install -e .
python -m unittest discover -s tests -v
python -m quarkcompress analyze example.txt
python -m quarkcompress compress example.txt --output example
python -m quarkcompress compress example.txt --codec zstd-3 --output quick
python -m quarkcompress compress example.txt --codec qcore-2 --output packed
python -m quarkcompress inspect packed.qkc
python -m quarkcompress decompress packed.qkc --output restored.txt
python benchmark.py
```

With a C compiler and Python development headers, installation builds the
accelerator. Confirm with `python -c "from quarkcompress.qcore import BACKEND; print(BACKEND)"`.
Without a working compiler, the package falls back to Python. To force the
reference backend for comparisons, set `QUARK_PURE_PYTHON=1` before launching.

The output suffix is added automatically, e.g. `example.xz`. Inputs remain
unchanged. Extract with an appropriate standard XZ, gzip, or Zstandard tool.
The `decompress` command accepts QCore frames only. It verifies the full frame
before creating the output exclusively. Inspect performs a full verified decode
and reports the selected method for each block.

## QCore engine

`quarkcompress/qcore.py` implements the codec directly; it does not delegate
compression to Zstd, XZ, gzip or Deflate. It chooses block size and transformations
and records the decisions in a versioned frame. The parent application
can still choose another engine when it produces a smaller output.

```python
from quarkcompress.qcore import compress, decompress

original = b"Community mapping data\n" * 1000
packed = compress(original)
assert decompress(packed) == original
```

Read the [v2 format specification](docs/QCORE_V2_FORMAT.md),
[retained v1 specification](docs/QCORE_FORMAT.md),
[architecture decision](docs/ADR-001-QCORE.md), and
[measured results](docs/QCORE_RESULTS.md).

## Benchmarking against established engines

The [Canterbury comparison](docs/QCORE_RESULTS.md) covers all 11 verified files,
including text, source code, a spreadsheet, a bitmap and a binary sample.
It measures QCore alongside gzip, Zstd-3/19/22, XZ-9/9e and bzip2-9 in separate
processes, with exact restoration and peak-RSS reporting.
See [reproduction instructions](benchmarks/README.md) and
[explicit parity gates](docs/PARITY_GATES.md). These results do not establish
general parity or include a native 7-Zip comparison.

## Current boundaries

32 MiB input limit per file; whole-file buffers; codec working memory is additional
and may substantially exceed input size. No enforced RAM budget or peak-RSS
measurement. No directory archives, permissions restoration, resume, GUI,
embedded-stream precompression, encryption, content-defined deduplication,
or mobile app yet. QCore's fixed-block references operate within a single file.
Files must be stable while being read. Interrupted output writes can leave an
incomplete file; crash-safe atomic publication is a future gate.

Synthetic smoke results are in `results/smoke.json`; reproduce with `benchmark.py`.
These are synthetic local checks, not evidence of general superiority over
Zstd, XZ, 7-Zip or game repackers. QCore's Python implementation is expected
to be slower than native engines; an optional C backend accelerates its hot
loops. The results report losses as well as wins.
The cross-platform CI workflow reports its status through the badge above.

## Direction

Build an adaptive packing pipeline on established engines, with bounded resource
use, reversible preprocessing, content-defined deduplication, and transparent
benchmarks. First target workloads: project folders, support logs, community GIS
datasets and versioned document collections. Already compressed drone imagery
and video are a hard case and must be tested separately.

See [research](docs/RESEARCH.md), [roadmap](docs/ROADMAP.md), and
[benchmark protocol](docs/BENCHMARKS.md).

## Author and contributions

Created by [Kaziwale Masheke](https://github.com/KFNMasheke).
Read [CONTRIBUTING.md](CONTRIBUTING.md) for development and benchmark standards,
and [SECURITY.md](SECURITY.md) for the current safety boundaries.

## License

Original Quark Compress code uses the [MIT License](LICENSE).
Dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
