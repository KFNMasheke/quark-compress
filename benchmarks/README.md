# Reproduce the public-corpus comparison

```sh
python -m pip install -e .
python -c "from quarkcompress.qcore import BACKEND; assert BACKEND == 'native'"
python tools/fetch_canterbury.py
python benchmarks/run_suite.py
```

A C compiler and Python development headers are required for the optional native
extension. If unavailable, normal installation falls back to Python; the native
benchmark deliberately refuses to silently substitute that slower backend.
On hosts with an unusable configured compiler, explicitly select a working
compiler using the build environment (for example `CC=cc` on Linux).

The manifest pins all 11 Canterbury files through a zlib-ng/corpora Git commit,
SHA-256 checksums and Git blob identifiers. Corpus bytes are excluded from this
repository; consult original terms before redistributing them. An integrity
mismatch is fatal. Do not normalize line endings or text encodings.

Each file/codec combination runs in a separate child process, sequentially.
One warm-up and three timed repetitions verify exact recovery. The report
records median and min/max encode/decode times, versions, source hashes and peak
process RSS when supported. RSS includes the interpreter, input and warm-up;
it is not an isolated allocation count. File reads, subprocess startup and
disk output are outside the timed codec sections. No CPU frequency or cold-cache
control is applied, so timings should be repeated independently.

QCore Python-v1, native-v1 and native-v2 are distinct configurations. Native-v2
includes block-size trials and all entropy candidates in its encoding time.
Native-v1's matcher differs from the original Python matcher as documented in
the format notes; native speedups are not a comparison of identical machine
instructions. The `complete` field is set only after every file finishes.

Run native parser checks under sanitizers on Linux/GCC with:

```sh
python tools/sanitize.py
```

That builds an isolated instrumented extension and runs the test suite with
AddressSanitizer and UndefinedBehaviorSanitizer. Interpreter leak detection is
disabled. Passing this finite suite is not coverage-guided fuzzing or a security
certification. Ordinary and reference-only tests also run in GitHub CI.
