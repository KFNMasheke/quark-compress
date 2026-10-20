# External corpus evaluation

Keep evaluation data outside this repository. Obtain permission to use each file.
Freeze the manifest before tuning; keep development and evaluation corpora separate.
The tool verifies sizes, SHA-256 and safe paths, but cannot prove dataset independence.

Create a UTF-8 JSON manifest with this shape (replace the illustrative digest):

```json
{"split":"held-out","files":[{"name":"sample.txt","bytes":123,"sha256":"<64-character SHA-256>"}]}
```

Names are unique relative POSIX paths within the corpus root. Absolute paths,
traversal and symlinks escaping the root are rejected. Each input retains the
normal compressor input limit. Corpus files and private filenames are not uploaded.
Reports include supplied relative filenames, so inspect them before sharing.

```sh
python benchmarks/adaptive_experiment.py --corpus-root /path/to/evaluation --manifest /path/to/frozen-manifest.json --output /path/to/evaluation-results.json --repeats 3
```

The default Canterbury experiment is unchanged. External evaluation must use a
different output path. Native QCore and all existing codecs remain prerequisites.
Results record the manifest digest and the operator-declared split. No external
corpus has been evaluated merely by adding this harness; parity remains unproven.
