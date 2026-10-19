# Quark Compress

**Smaller files. Every bit preserved.**

[![Tests](https://github.com/KFNMasheke/quark-compress/actions/workflows/test.yml/badge.svg)](https://github.com/KFNMasheke/quark-compress/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An open-source lossless compression lab exploring adaptive codec selection,
with reproducible benchmarks and byte-exact restoration checks.

Working project by Kaziwale Masheke. Milestone 0.1 is a compression lab,
not a finished desktop archiver or a new compression algorithm.

## What works today

- Trials of Zstandard 3/19, XZ/LZMA2 6/9, gzip 9, and raw storage.
- Exhaustive smallest-output selection, including a no-compression fallback.
- Byte-for-byte restoration checks, SHA-256 reporting, encode/decode timings.
- Standard `.zst`, `.xz`, `.gz` outputs; `.raw` means an unchanged copy.
- Exclusive output creation: existing files and symlinks are not overwritten.
- Unit tests and a proposed Windows/Linux/macOS CI matrix.

The exhaustive selector compresses the entire input with every candidate. This
gives a smallest-size baseline among those candidates, at substantial CPU cost.
It is not yet a smart predictor, deduplicating archiver, or improvement to Zstd.
Trial timings include codec work; total selection wall time includes all trials
and verification. Reports explicitly distinguish these quantities.

## Quick start

Python 3.11 or newer:

```sh
git clone https://github.com/KFNMasheke/quark-compress.git
cd quark-compress
python -m pip install .
python -m unittest discover -s tests -v
python -m quarkcompress analyze example.txt
python -m quarkcompress compress example.txt --output example
python -m quarkcompress compress example.txt --codec zstd-3 --output quick
python benchmark.py
```

The output suffix is added automatically, e.g. `example.xz`. Inputs remain
unchanged. Extract with an appropriate standard XZ, gzip, or Zstandard tool.
The lab has no untrusted archive extraction command.

## Current boundaries

32 MiB input limit per file; whole-file buffers; codec working memory is additional
and may substantially exceed input size. No enforced RAM budget or peak-RSS
measurement. No directory archives, permissions restoration, resume, GUI,
precompression, encryption, content-defined deduplication, or mobile app yet.
Files must be stable while being read. Interrupted output writes can leave an
incomplete file; crash-safe atomic publication is a future gate.

Synthetic smoke results are in `results/smoke.json`; reproduce with `benchmark.py`.
These are local checks, not evidence of beating 7-Zip or game repackers.
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
