# Adaptive selection: first experiment

Question: can a cheap selector approach exhaustive selection size while
taking close to the encoding time of a single well-chosen compressor?

Five candidates: raw storage, Zstd-3, Zstd-19, XZ-6, and original QCore-2.
Oracle tries every candidate on every block. Fast-sample compares raw and
Zstd-3 on four 1 KiB windows. Portfolio-sample tries all five on those windows.
The predicted winner encodes the complete block, with raw fallback if it grows.
Blocks <=4 KiB reuse their complete sample trials. No learned model or tuning.

Frames contain a 50-byte header (magic, original size, block count, SHA-256)
and nine bytes per block (codec ID and raw/packed lengths). Actual frames
are decoded and verified. This lab format is not QKC and is not a public
untrusted-archive decoder. QCore itself is unchanged.

Sequential isolated processes; one warm-up, three timed repetitions.
Times below sum per-file medians. Encode includes all selection, discarded
trials, hashing and framing; decode includes integrity verification.
Input loading/startup/I/O and final byte comparison are outside the timers.
Whole-file baselines use their own stream framing; identical framing is
used for every block policy. Peak RSS includes interpreter/input/warm-up.
Canterbury is a development set. Synthetic diagnostics are not held-out data.
The oracle is optimal only for this candidate set and fixed partition.

## Canterbury development

11 files; 2,788,958 input bytes.

| Configuration | Output bytes | Encode s | Decode s | Peak process MiB |
|---|---:|---:|---:|---:|
| whole:zstd-3 | 630,554 | 0.011905 | 0.002973 | 18.75 |
| whole:zstd-19 | 514,042 | 0.882770 | 0.004099 | 35.41 |
| whole:xz-6 | 489,616 | 0.767168 | 0.020518 | 45.37 |
| whole:qcore-2 | 675,846 | 0.314900 | 0.015867 | 21.18 |
| oracle:65536 | 557,210 | 1.475552 | 0.024292 | 38.98 |
| fast-sample:65536 | 666,240 | 0.015569 | 0.005858 | 19.37 |
| portfolio-sample:65536 | 588,994 | 0.898098 | 0.008529 | 41.32 |
| fixed-zstd-3:65536 | 666,240 | 0.013433 | 0.005725 | 19.30 |
| oracle:262144 | 511,227 | 1.866627 | 0.022818 | 47.47 |
| fast-sample:262144 | 652,429 | 0.017168 | 0.005585 | 20.30 |
| portfolio-sample:262144 | 526,904 | 0.930532 | 0.010003 | 48.45 |
| fixed-zstd-3:262144 | 652,429 | 0.014194 | 0.005186 | 20.31 |

Router ratios compare against the oracle at the SAME block size.
Time ratios above one mean slower. These ratios do not prove general parity.

| Router | Bytes / oracle | Time / oracle | Time / whole Zstd-3 | Time / whole XZ-6 | Files within 5% oracle size |
|---|---:|---:|---:|---:|---:|
| fast-sample:65536 | 1.196x | 0.011x | 1.31x | 0.02x | 1/11 |
| portfolio-sample:65536 | 1.057x | 0.609x | 75.44x | 1.17x | 10/11 |
| fast-sample:262144 | 1.276x | 0.009x | 1.44x | 0.02x | 1/11 |
| portfolio-sample:262144 | 1.031x | 0.499x | 78.16x | 1.21x | 10/11 |

At 256 KiB, portfolio sampling produces 3.07% more bytes
than exhaustive selection using 49.9% of its encoding time.
Against whole-file XZ-6 it uses 1.076x the output bytes
and 1.213x the encoding time.

## synthetic diagnostic

3 files; 1,835,930 input bytes.

| Configuration | Output bytes | Encode s | Decode s | Peak process MiB |
|---|---:|---:|---:|---:|
| whole:zstd-3 | 849,727 | 0.002001 | 0.000525 | 24.02 |
| whole:zstd-19 | 618,204 | 0.155538 | 0.001903 | 37.59 |
| whole:xz-6 | 565,284 | 0.266670 | 0.013153 | 53.36 |
| whole:qcore-2 | 843,348 | 0.095087 | 0.005512 | 24.02 |
| oracle:65536 | 573,517 | 0.360895 | 0.009692 | 39.54 |
| fast-sample:65536 | 842,365 | 0.003230 | 0.002054 | 24.02 |
| portfolio-sample:65536 | 673,782 | 0.109324 | 0.005318 | 40.12 |
| fixed-zstd-3:65536 | 842,365 | 0.003485 | 0.002433 | 24.02 |
| oracle:262144 | 563,351 | 0.360356 | 0.008613 | 47.54 |
| fast-sample:262144 | 850,554 | 0.002588 | 0.001939 | 24.02 |
| portfolio-sample:262144 | 563,351 | 0.103972 | 0.008933 | 44.10 |
| fixed-zstd-3:262144 | 850,554 | 0.003571 | 0.002323 | 24.02 |

Router ratios compare against the oracle at the SAME block size.
Time ratios above one mean slower. These ratios do not prove general parity.

| Router | Bytes / oracle | Time / oracle | Time / whole Zstd-3 | Time / whole XZ-6 | Files within 5% oracle size |
|---|---:|---:|---:|---:|---:|
| fast-sample:65536 | 1.469x | 0.009x | 1.61x | 0.01x | 1/3 |
| portfolio-sample:65536 | 1.175x | 0.303x | 54.63x | 0.41x | 1/3 |
| fast-sample:262144 | 1.510x | 0.007x | 1.29x | 0.01x | 1/3 |
| portfolio-sample:262144 | 1.000x | 0.289x | 51.96x | 0.39x | 3/3 |

At 256 KiB, portfolio sampling produces 0.00% more bytes
than exhaustive selection using 28.9% of its encoding time.
Against whole-file XZ-6 it uses 0.997x the output bytes
and 0.390x the encoding time.

## Every input at 256 KiB

| Input | Whole Zstd-3 bytes | Whole XZ-6 bytes | Oracle bytes | Fast sample bytes | Portfolio sample bytes |
|---|---:|---:|---:|---:|---:|
| alice29.txt | 56,258 | 47,876 | 47,935 | 56,317 | 48,714 |
| asyoulik.txt | 50,328 | 44,536 | 44,595 | 50,387 | 45,200 |
| cp.html | 8,468 | 7,644 | 7,703 | 8,527 | 7,776 |
| fields.c | 3,384 | 3,028 | 3,078 | 3,443 | 3,078 |
| grammar.lsp | 1,295 | 1,292 | 1,274 | 1,354 | 1,274 |
| kennedy.xls | 111,831 | 49,116 | 55,214 | 111,543 | 64,043 |
| lcet10.txt | 139,166 | 118,052 | 125,492 | 147,606 | 127,608 |
| plrabn12.txt | 190,218 | 164,816 | 172,056 | 202,275 | 174,234 |
| ptt5 | 54,424 | 41,992 | 42,582 | 55,677 | 43,679 |
| sum | 13,379 | 9,452 | 9,511 | 13,438 | 9,511 |
| xargs.1 | 1,803 | 1,812 | 1,787 | 1,862 | 1,787 |
| mixed-aligned | 423,784 | 281,512 | 280,435 | 423,836 | 280,435 |
| mixed-offset | 423,852 | 281,520 | 280,770 | 424,568 | 280,770 |
| sample-trap | 2,091 | 2,252 | 2,146 | 2,150 | 2,146 |

## Interpretation and next experiment

Do not infer routing value from speed versus exhaustive search alone.
Compare output against whole-file codecs: resetting dictionaries may
cost more than codec switching saves. Sample prediction errors and codec
initialization costs must also count. Mixed synthetic success would not
establish general success on ordinary files.

Next: test context-preserving segmentation and a budgeted selector with
cheap features, then evaluate on unseen Silesia and real GIS/media files.
Keep sample counterexamples. Do not optimize or claim held-out accuracy
on this development set. External codec routing is distinct from improving
the original QCore algorithm.

Reproduce: `python benchmarks/adaptive_experiment.py` followed by
`python tools/render_adaptive.py`. See [raw results](../results/adaptive.json)
for source/input hashes, decisions, timing ranges and environment.
