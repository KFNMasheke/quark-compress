# Contributing to Quark Compress

Start with the [roadmap](docs/ROADMAP.md) and [benchmark protocol](docs/BENCHMARKS.md).
For large features, open an issue with a workload, baseline, proposed change and
measurable acceptance criterion.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python benchmark.py
```

Include exact round-trip tests for compression changes and regression tests for
parser/output safety changes. Preserve counterexamples and upstream notices.
Never commit private support tickets, customer documents, financial records,
secrets, or unlicensed datasets.

Report hardware, versions, input hashes and end-to-end planning costs for
performance claims. Synthetic smoke tests alone do not justify broad claims.
Original contributions are accepted under the repository's MIT license;
third-party material must retain its own license.
