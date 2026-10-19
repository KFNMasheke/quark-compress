# Third-party components

The MIT license in `LICENSE` covers original Quark Compress source and
documentation. It does not relicense dependencies or research references.

- Python `zstandard` 0.25.0 provides bindings to Zstandard. Consult its exact
  distribution's license files before redistribution:
  https://github.com/indygreg/python-zstandard
- The Zstandard reference implementation documents BSD-or-GPLv2 licensing:
  https://github.com/facebook/zstd
- Python's gzip, lzma, zlib and other standard-library components retain their
  upstream licenses and are supplied by the user's Python installation.

No source or binaries from other repositories in `docs/RESEARCH.md` are bundled.
Review complete dependency trees and preserve applicable notices before future
integration. This initial inventory is not a completed dependency audit or a
substitute for the upstream license texts.
