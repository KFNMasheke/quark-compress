# GitHub landscape and build decision

Reviewed 19 October 2026 through primary repository pages and documentation.
This is a repository/documentation review, not a complete source audit. No upstream
repository has been forked or patched. QCore was subsequently implemented as an
independent research codec; it does not incorporate code from these repositories.

| Repository | Existing capability | Role in Quark Compress |
|---|---|---|
| [facebook/zstd](https://github.com/facebook/zstd) | Fast lossless codec, compression-level trade-offs, dictionaries | Preferred everyday engine; currently used through Python binding |
| [ip7z/7zip](https://github.com/ip7z/7zip) | Mature archiver and LZMA2/solid compression | Required future end-to-end baseline; not installed or tested here |
| [mcmilk/7-Zip-zstd](https://github.com/mcmilk/7-Zip-zstd) | Multiple codecs in 7-Zip | Integration reference and competitor; multi-codec support alone is not novel |
| [conor42/fast-lzma2](https://github.com/conor42/fast-lzma2) | Parallel LZMA2 implementation | Evaluate as an optional high-ratio engine |
| [schnaader/precomp-cpp](https://github.com/schnaader/precomp-cpp) | Reversible reconstruction of supported compressed streams | Most direct research lead for recompressing supported PDFs/ZIPs/PNGs |
| [Razor12911/xtool](https://github.com/Razor12911/xtool) | Preprocessing/repacking tools and stream handling | Explore adapters for supported formats after build and dependency audit |
| [mhx/dwarfs](https://github.com/mhx/dwarfs) | Deduplicating read-only filesystem with similarity grouping | Strong reference and baseline for similar/versioned file collections |
| [zpaq/zpaq](https://github.com/zpaq/zpaq) | Journaling backups and fragment deduplication | Baseline for repeated backup generations |
| [peazip/PeaZip](https://github.com/peazip/PeaZip) | Cross-platform archive manager | UX and archive-workflow reference |
| [inikep/lzbench](https://github.com/inikep/lzbench) | Codec benchmark harness | Independent codec evaluation |
| [powturbo/TurboBench](https://github.com/powturbo/TurboBench) | Broad codec benchmark harness | Secondary validation; inspect build and codec licensing individually |

## Recommendation

Build a new orchestration project using established libraries. Do not start by
forking all of 7-Zip: a large legacy UI/codebase dilutes the original engineering
work and introduces broad compatibility responsibilities. Keep upstream adapters
replaceable; contribute engine-specific fixes upstream when supported by profiling.

The proposed contribution is a planner that chooses a pipeline for the dataset
and resource budget, with evidence explaining each choice. DwarFS and other
projects already cover parts of this territory. Novelty must come from a measured
implementation and useful workflow, not the mere combination of familiar ideas.

## High-impact experiments

1. Sample multiple regions, predict size/time, and select near-oracle compression
   without the exhaustive trial cost. Compare to fixed Zstd and fixed XZ modes.
2. Content-defined chunking and deduplication across edited project versions;
   compare against DwarFS/ZPAQ, not just ZIP.
3. Similarity-aware solid groups, balancing ratio with selective extraction cost.
4. Reversible preprocessing of supported embedded streams. Verify exact original
   bytes; include reconstruction metadata in final archive size and restore time.
5. GIS-specific reversible transforms for suitable numeric data. Start with known
   public datasets and compare against their native compressed formats.

These remain research hypotheses. QCore adds an independent codec, with
synthetic results in QCORE_RESULTS.md. No drastic general improvement is
established yet.

## Dependency and licensing boundary

Upstream Zstd documents BSD-or-GPLv2 licensing; Fast LZMA2 documents BSD/GPLv2
dual licensing; Precomp's top-level project says Apache-2.0 and lists bundled
components; XTool's top-level license is MIT. 7-Zip documents a mixture of LGPL,
BSD, public-domain files and an unRAR restriction. Preserve exact applicable
licenses and notices before distributing each selected component. A top-level
license does not settle the status of every dependency or plugin. No proprietary
game codec or third-party binary is bundled in this package.

## Compression reality

Reversible preprocessing can expose redundancy inside some compressed streams;
it does not guarantee reductions on arbitrary compressed media. Distinguish
lossless recovery from transcoding, deleting files, stripping languages, or
lowering quality. This project requires exact original bytes.
