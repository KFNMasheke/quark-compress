# QCore v1: local synthetic smoke results

These measurements validate the prototype, not general performance leadership.
Inputs are deterministic synthetic data. One warm-up and three repetitions;
encode/decode times are medians. Disk I/O and peak RSS are not measured.
QCore includes its frame and block metadata. Standard codecs are single streams.
Every trial verifies byte-exact recovery. Raw input sizes are shown for context.

| Workload | Input bytes | QCore bytes | Zstd-19 bytes | XZ-9 bytes | Smallest tested candidate |
|---|---:|---:|---:|---:|---|
| repetitive-json | 456,000 | 584 | 109 | 252 | zstd-19 |
| random-binary | 400,000 | 400,143 | 400,025 | 400,080 | store |
| already-deflated | 1,407 | 158 | 109 | 172 | zstd-3 |
| mixed | 400,000 | 200,881 | 200,179 | 201,076 | zstd-3 |
| empty | 0 | 52 | 13 | 32 | store |
| synthetic-numeric-ramp | 131,072 | 90 | 283 | 396 | qcore-1 |
| synthetic-duplicate-blocks | 262,144 | 65,652 | 65,614 | 65,768 | zstd-3 |

## Time cost

QCore timings below cover only QCore encoding and decoding, not the outer
exhaustive selector. Its end-to-end time is recorded separately in the JSON.

| Workload | QCore encode ms | QCore decode ms | Zstd-19 encode ms | Zstd-19 decode ms |
|---|---:|---:|---:|---:|
| repetitive-json | 270.363 | 21.264 | 0.881 | 0.109 |
| random-binary | 1118.757 | 0.453 | 18.457 | 0.098 |
| already-deflated | 1.588 | 0.067 | 0.025 | 0.011 |
| mixed | 704.554 | 10.159 | 9.027 | 0.105 |
| empty | 0.013 | 0.007 | 0.013 | 0.009 |
| synthetic-numeric-ramp | 40.185 | 6.148 | 0.255 | 0.025 |
| synthetic-duplicate-blocks | 205.615 | 0.343 | 3.932 | 0.068 |

## Interpretation

- Small inputs and random data pay frame overhead; the parent selector can choose raw storage.
- The numeric ramp deliberately favors a reversible byte-delta transform. Any win here is narrow and synthetic.
- Fixed-block references recognize exact aligned duplicates, not shifted/edited content.
- QCore loses to native engines on several samples and generally takes more CPU time.
- These results do not establish benefits on real GIS data, compressed imagery, game assets, or public corpora.

Raw measurements, hashes and environment: [results/smoke.json](../results/smoke.json).
Reproduce from the repository root with `python benchmark.py`.

## Next experiments

1. Profile match finding and Huffman decoding before a native implementation.
2. Test held-out public datasets and native 7-Zip; report memory and all planning costs.
3. Evaluate content-defined chunking and dictionary reuse across blocks.
4. Run coverage-guided parser fuzzing and request an independent format review.
