# Flagship delivery roadmap

## 0.1: Evidence foundation (published)

Bounded codec trials, standard-format output, exhaustive size oracle, synthetic
smoke benchmark, eight unit tests, and CI configuration. Initial cross-platform
CI passed. No packaged desktop release yet.

## 0.2: QCore experimental codec (implemented)

Independent LZ77 and canonical Huffman implementations, reversible byte deltas,
fixed-block references, a specified `.qkc` format, bounded decoding, corruption
checks, CLI integration, malformed-input tests and updated synthetic benchmarks.
This establishes a reference engine; it does not establish performance leadership.

## 0.3: Native acceleration (implemented)

An optional original C extension accelerates matching, entropy models, bit
coding, delta transforms and token reconstruction. Python reference decoding
and cross-backend tests remain. Sanitizer checks and compiler builds run in CI.

## 0.4: Factored entropy and verified public benchmarks (implemented)

QKC2 adds separately modeled literal/match fields and full-frame selection
between 64 KiB and 256 KiB blocks. The decoder retains QKC1 compatibility.
All 11 exact Canterbury inputs now run through isolated, reproducible codec
comparisons, including peak RSS. The parity gates remain explicit research
targets, not a claim that the project has reached them.

## 0.5: Broader representative benchmarks

Fetch version-pinned Silesia and Canterbury corpora, add licensed public GIS and
project-version datasets, record corpus hashes and licenses. Add native 7-Zip,
Zstd, Precomp and DwarFS adapters where supported. Use isolated processes for
time, peak RSS, CPU and restore checks. Publish regressions as prominently as wins.

Exit: reproducible size/time/RAM results on at least three workload families,
without an unsupported claim of general superiority.

## 0.6: Adaptive engine and stronger parsing/entropy models

Multi-region sampling, held-out evaluation, compressibility estimation, early
abort, explicit size/speed objectives, and memory-aware job scheduling.
Profile lazy/cost-based parsing and context/range or rANS models against the
current factored-Huffman baseline before changing the format again.

Research target: within 5% of the exhaustive oracle's size while reducing
selection overhead by at least 80% on held-out workloads. These are unproven
targets; revise or reject the design if measurements fail them.

## 0.7: Directory archive and deduplication

Versioned manifest schema, content-defined chunks, checksums, similarity grouping,
bounded streaming, deterministic manifests, extraction budgets, path safety,
duplicate/path collision rejection, atomic output publication and cancellation.
Compare fixed and content-defined chunking; include index overhead in size.

Exit: exact content recovery and defined metadata behavior, fuzzed parsers,
corruption/truncation handling, no path traversal or unintended overwrite, and
bounded extraction memory/disk usage. Metadata support must be explicit.

## 0.8: Embedded-stream preprocessing

Sandboxed adapters for supported streams, bounded recursion, recovery metadata,
and content hashes. Never install arbitrary codecs from archive metadata.
Test encoder/version dependence and portability before enabling a transform.

## 0.9: Desktop product

Profile before deciding whether to move orchestration to Rust/C++. Evaluate
Tauri for a desktop UI: drop files, size/time/RAM controls, queue, cancellation,
recovery instructions and benchmark explanations. Start on Windows, then
Linux/macOS after compatibility checks. No backend or account required.

## Portfolio release

Publish architecture decisions, profiler traces, CI results, fuzz corpus policy,
dependency audit, reproducible builds, signed release process, versioned format
specification and a narrated case study. Showcase original contributions with
before/after measurements against named upstream versions. Keep raw local user
files and financial/support data out of the public repository.
