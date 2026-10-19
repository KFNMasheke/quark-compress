# ADR 001: Build QCore inside Quark Compress

Status: accepted for experimental research, 19 October 2026.

## Decision

Add `quarkcompress.qcore` as an independent codec module. Quark Compress remains
the orchestrator and benchmarks `qcore-1` beside established engines. A module
API keeps codec work separate from the CLI and allows future native bindings.
No new repository or external service is needed.

Use established, explainable primitives: LZ77, static canonical Huffman,
reversible byte deltas, fixed-block duplicate references, and raw fallback.
Prefer a small specified format to opaque dependencies. The first goal is
correctness and inspectability, not performance leadership.

## Consequences

The project now owns a parser and compatibility surface. Exact restoration,
malformed-input tests, size bounds, format documentation and no-overwrite
behavior ship with the first codec implementation. Checksums are integrity
checks, not encryption or sender authentication.

Python provides a readable reference implementation but is slower than native
codecs and buffers whole files. Exhaustive candidate trials also add overhead.
Do not hide those costs in benchmarks. Native implementation, content-defined
chunking, improved match finding, dynamic entropy models and streaming are
future experiments, contingent on profiling and held-out benchmarks.

Standard-engine selection can beat this codec. Keep that result visible;
do not force QCore as the default winner or rename upstream algorithms as ours.
