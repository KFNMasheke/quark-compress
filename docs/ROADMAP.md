# Flagship delivery roadmap

## 0.1: Evidence foundation (implemented locally)

Bounded codec trials, standard-format output, exhaustive size oracle, synthetic
smoke benchmark, eight unit tests, and CI configuration. No public release yet.

## 0.2: Representative benchmarks

Fetch version-pinned Silesia and Canterbury corpora, add licensed public GIS and
project-version datasets, record corpus hashes and licenses. Add native 7-Zip,
Zstd, Precomp and DwarFS adapters where supported. Use isolated processes for
time, peak RSS, CPU and restore checks. Publish regressions as prominently as wins.

Exit: reproducible size/time/RAM results on at least three workload families,
without an unsupported claim of general superiority.

## 0.3: Adaptive engine

Multi-region sampling, held-out evaluation, compressibility estimation, early
abort, explicit size/speed objectives, and memory-aware job scheduling.

Research target: within 5% of the exhaustive oracle's size while reducing
selection overhead by at least 80% on held-out workloads. These are unproven
targets; revise or reject the design if measurements fail them.

## 0.4: Directory archive and deduplication

Versioned manifest schema, content-defined chunks, checksums, similarity grouping,
bounded streaming, deterministic manifests, extraction budgets, path safety,
duplicate/path collision rejection, atomic output publication and cancellation.
Compare fixed and content-defined chunking; include index overhead in size.

Exit: exact content recovery and defined metadata behavior, fuzzed parsers,
corruption/truncation handling, no path traversal or unintended overwrite, and
bounded extraction memory/disk usage. Metadata support must be explicit.

## 0.5: Reversible preprocessing

Sandboxed adapters for supported streams, bounded recursion, recovery metadata,
and content hashes. Never install arbitrary codecs from archive metadata.
Test encoder/version dependence and portability before enabling a transform.

## 0.6: Desktop product

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
