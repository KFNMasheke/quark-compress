# QCore v2: Canterbury results

All 11 pinned Canterbury inputs were tested, with exact recovery on every trial.
One warm-up and three timed repetitions ran sequentially in isolated child processes.
Times below sum each file's median; peak RSS is the largest per-file process peak.
It includes interpreter/data memory. Timings exclude file I/O and process startup.

| Configuration | Total output bytes | Encode seconds | Decode seconds | Peak process MiB |
|---|---:|---:|---:|---:|
| qcore-python-v1 | 910,363 | 6.243671 | 1.769621 | 27.69 |
| qcore-native-v1 | 885,004 | 0.118295 | 0.018241 | 17.37 |
| qcore-native-v2 | 675,846 | 0.302017 | 0.016838 | 18.52 |
| gzip-9 | 724,185 | 0.638467 | 0.008767 | 16.75 |
| zstd-3 | 630,554 | 0.010644 | 0.002630 | 16.62 |
| zstd-19 | 514,042 | 0.806990 | 0.003466 | 32.57 |
| zstd-22 | 513,922 | 1.254769 | 0.003172 | 32.57 |
| xz-9 | 489,616 | 0.970236 | 0.021601 | 87.88 |
| xz-9e | 490,436 | 1.658043 | 0.021710 | 87.88 |
| bzip2-9 | 542,520 | 0.137620 | 0.051324 | 20.88 |

## Improvement over the original Python v1 reference

- Output reduction: 25.76%.
- Encoding speedup: 20.67x.
- Decoding speedup: 105.10x.

This combines new parsing/model choices and native implementation changes; it is
not an identical-instruction language comparison. Native-v1 isolates the earlier
format configuration. All v2 block-size/model trials count in encoding time.

## Per-file sizes

| File | Original bytes | Python v1 bytes | Native v2 bytes | Best fixed baseline | Baseline bytes |
|---|---:|---:|---:|---|---:|
| alice29.txt | 148,481 | 71,139 | 53,570 | bzip2-9 | 43,102 |
| asyoulik.txt | 125,179 | 63,593 | 49,188 | bzip2-9 | 39,569 |
| cp.html | 24,603 | 10,067 | 8,502 | bzip2-9 | 7,624 |
| fields.c | 11,150 | 4,199 | 3,505 | zstd-19 | 3,019 |
| grammar.lsp | 3,721 | 1,781 | 1,536 | zstd-19 | 1,215 |
| kennedy.xls | 1,029,744 | 229,283 | 150,357 | xz-9 | 49,116 |
| lcet10.txt | 419,235 | 189,498 | 142,874 | bzip2-9 | 107,648 |
| plrabn12.txt | 471,162 | 257,010 | 193,577 | bzip2-9 | 145,545 |
| ptt5 | 513,216 | 65,580 | 56,402 | xz-9e | 39,860 |
| sum | 38,240 | 15,794 | 14,270 | xz-9 | 9,452 |
| xargs.1 | 4,227 | 2,419 | 2,065 | zstd-19 | 1,728 |

## Parity status

Size within 5% of the best tested fixed baseline: **0/11 files** (target: at least 9/11).
Aggregate size versus the per-file best baseline: **1.509x** (target: at most 1.05x).
Encode throughput versus Zstd-3: **0.035x** (target: at least 0.8x at comparable size).
Decode throughput versus Zstd-3: **0.156x**.

**General parity has not been reached.** Zstandard and XZ remain stronger on
important size/speed measures. These are local results with timing variation,
not claims about every machine or workload. Native 7-Zip, Brotli, LZ4, Silesia,
GIS and compressed media are not covered by this run. Canterbury was used during
iteration, so it is no longer a held-out evaluation set.

A separate 2/4/8-byte shuffle experiment was rejected: all projected variants
were larger on the three tested binary inputs. No transform method was added.
See [experiment measurements](../results/shuffle_experiment.json) and reproduce
with `python benchmarks/shuffle_experiment.py`. This does not rule out shuffling
on other numeric datasets.

See [parity gates](PARITY_GATES.md), [raw measurements](../results/canterbury.json),
[input manifest](../benchmarks/canterbury_manifest.json), and
[reproduction instructions](../benchmarks/README.md).
