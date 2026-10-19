# Benchmark protocol

Measure lossless recovery first, then final output size, compression wall time,
decompression wall time, peak resident memory, CPU time, index overhead, and
selective extraction cost. Report planner and preprocessing costs separately
and in the end-to-end total. Do not report the selected codec's speed as the
speed of a planner which ran multiple codecs.

Use identical input bytes, hardware, thread count and resource constraints.
Record OS, CPU, codec/binding versions, dependency/build flags, source commit,
corpus versions/licenses and hashes. Separate warm-cache/in-memory trials from
cold-disk end-to-end tests. Perform warm-ups, multiple repetitions and report
median plus variation. Isolate runs for meaningful peak memory measurements.

Baseline matrix: ZIP/Deflate, 7z/LZMA2, fixed Zstd levels, tar plus Zstd/XZ,
Precomp plus downstream codec, DwarFS and ZPAQ for applicable directory workloads.
Similar-file archives must use the same file set and restore semantics. Do not
compare raw codec bytes against archive bytes without calling out metadata.

Report workload families separately: text/JSON/logs, binary/numeric GIS,
compressed images/video, embedded compressed streams, duplicate project versions,
random bytes, and mixed folders. Include sample-selection failures. Hold out
datasets from planner tuning.

Current `benchmark.py` runs seven deterministic synthetic inputs, one warm-up
and three repetitions, with byte-exact verification for every codec. It measures
in-memory encoding/decoding only, excludes file I/O and does not measure RSS.
It is a smoke test, not a publishable performance study. QCore output includes
frame, checksum and block metadata; standard codec outputs are single streams,
not directory archives. No native 7-Zip result is inferred from Python XZ.
