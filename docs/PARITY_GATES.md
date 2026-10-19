# Defining parity before claiming it

There is no single best compressor across all data, ratios, speeds and memory
budgets. The current reference set is gzip-9, Zstd-3/19/22, XZ-9/9e and bzip2-9.
It is a strong initial comparison, not an exhaustive state-of-the-art survey.
Python XZ output is not a measured native 7-Zip result. Future gates must add
native 7-Zip, Brotli, LZ4 and appropriate specialized codecs/corpora.

## Current acceptance targets (not achieved or certified)

| Axis | Proposed gate | Measurement |
|---|---|---|
| Size | At most 5% above the smallest tested baseline on at least 9/11 Canterbury files, and on the aggregate | Complete compressed frames; all metadata included |
| Speed | At least 80% of Zstd-3 throughput, while output is no more than 5% larger | Separate encode/decode totals; same data and machine |
| Memory | At most 1.25x Zstd-3 peak process RSS on the same bounded workload | Isolated child processes; includes interpreter and data |
| Reliability | Exact recovery, retained QKC1 compatibility, passing malformed-input tests, sanitizer runs and all supported platform checks | Evidence gates, not a proof of absence of vulnerabilities |
| Generality | Repeat on held-out Silesia, binary GIS and compressed media workloads | Canterbury alone cannot establish general parity |

These thresholds define engineering goals, not universal standards. Do not
combine a size win on one file with a speed win on a different file to claim
parity. CPU time and output size from candidate trials count in total encoding.
The parent application's exhaustive `auto` mode selects the smallest tested
candidate, but its selection cost prevents interpreting this as a new winning
codec or a speed improvement.

## Next algorithm experiments

1. Measure split-field gains by file type and retain counterexamples.
2. Compare greedy, lazy and bounded-cost parsing rather than changing match
   search depths without reporting the CPU trade-off.
3. Prototype stronger context/range or rANS entropy models for literals and
   match metadata; include model overhead and decoding complexity.
4. Evaluate content-defined chunks and dictionary reuse without weakening
   decoding budgets, compatibility or integrity checks.
5. Add native 7-Zip and larger held-out corpora before revisiting parity claims.
