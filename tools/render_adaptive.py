"""Render every adaptive measurement, preserving unsuccessful configurations."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / "results/adaptive.json").read_text())
    if not report.get("complete") or len(report["files"]) != 14:
        raise ValueError("Require all 11 corpus files and three diagnostics")
    for source, digest in report["sources"].items():
        if hashlib.sha256((ROOT/source).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Measured source changed: {source}")
    lines = ["# Adaptive selection: first experiment", "",
             "Question: can a cheap selector approach exhaustive selection size while",
             "taking close to the encoding time of a single well-chosen compressor?", "",
             "Five candidates: raw storage, Zstd-3, Zstd-19, XZ-6, and original QCore-2.",
             "Oracle tries every candidate on every block. Fast-sample compares raw and",
             "Zstd-3 on four 1 KiB windows. Portfolio-sample tries all five on those windows.",
             "The predicted winner encodes the complete block, with raw fallback if it grows.",
             "Blocks <=4 KiB reuse their complete sample trials. No learned model or tuning.", "",
             "Frames contain a 50-byte header (magic, original size, block count, SHA-256)",
             "and nine bytes per block (codec ID and raw/packed lengths). Actual frames",
             "are decoded and verified. This lab format is not QKC and is not a public",
             "untrusted-archive decoder. QCore itself is unchanged.", "",
             "Sequential isolated processes; one warm-up, three timed repetitions.",
             "Times below sum per-file medians. Encode includes all selection, discarded",
             "trials, hashing and framing; decode includes integrity verification.",
             "Input loading/startup/I/O and final byte comparison are outside the timers.",
             "Whole-file baselines use their own stream framing; identical framing is",
             "used for every block policy. Peak RSS includes interpreter/input/warm-up.",
             "Canterbury is a development set. Synthetic diagnostics are not held-out data.",
             "The oracle is optimal only for this candidate set and fixed partition.", ""]
    for group in dict.fromkeys(f["group"] for f in report["files"]):
        files = [f for f in report["files"] if f["group"] == group]
        configs = [t["config"] for t in files[0]["trials"]]
        totals = {}
        for config in configs:
            rows = [next(t for t in f["trials"] if t["config"] == config) for f in files]
            totals[config] = {"bytes": sum(t["output_bytes"] for t in rows),
                              "encode": sum(t["encode_seconds"] for t in rows),
                              "decode": sum(t["decode_seconds"] for t in rows),
                              "rss": max(t["peak_process_rss_bytes"] or 0 for t in rows)}
        lines += [f"## {group}", "", f"{len(files)} files; {sum(f['input_bytes'] for f in files):,} input bytes.", "",
                  "| Configuration | Output bytes | Encode s | Decode s | Peak process MiB |",
                  "|---|---:|---:|---:|---:|"]
        for config, value in totals.items():
            lines.append(f"| {config} | {value['bytes']:,} | {value['encode']:.6f} | {value['decode']:.6f} | {value['rss']/1048576:.2f} |")
        lines += ["", "Router ratios compare against the oracle at the SAME block size.",
                  "Time ratios above one mean slower. These ratios do not prove general parity.", "",
                  "| Router | Bytes / oracle | Time / oracle | Time / whole Zstd-3 | Time / whole XZ-6 | Files within 5% oracle size |",
                  "|---|---:|---:|---:|---:|---:|"]
        for size in (65536, 262144):
            oracle = totals[f"oracle:{size}"]
            for policy in ("fast-sample", "portfolio-sample"):
                config = f"{policy}:{size}"
                value = totals[config]
                count = sum(next(t for t in f["trials"] if t["config"] == config)["output_bytes"] <=
                            1.05 * next(t for t in f["trials"] if t["config"] == f"oracle:{size}")["output_bytes"] for f in files)
                lines.append(f"| {config} | {value['bytes']/oracle['bytes']:.3f}x | {value['encode']/oracle['encode']:.3f}x | {value['encode']/totals['whole:zstd-3']['encode']:.2f}x | {value['encode']/totals['whole:xz-6']['encode']:.2f}x | {count}/{len(files)} |")
        selected = totals["portfolio-sample:262144"]
        oracle = totals["oracle:262144"]
        xz = totals["whole:xz-6"]
        lines += ["", f"At 256 KiB, portfolio sampling produces {100*(selected['bytes']/oracle['bytes']-1):.2f}% more bytes",
                  f"than exhaustive selection using {100*selected['encode']/oracle['encode']:.1f}% of its encoding time.",
                  f"Against whole-file XZ-6 it uses {selected['bytes']/xz['bytes']:.3f}x the output bytes",
                  f"and {selected['encode']/xz['encode']:.3f}x the encoding time.", ""]
    lines += ["## Every input at 256 KiB", "",
              "| Input | Whole Zstd-3 bytes | Whole XZ-6 bytes | Oracle bytes | Fast sample bytes | Portfolio sample bytes |",
              "|---|---:|---:|---:|---:|---:|"]
    for file in report["files"]:
        rows = {t["config"]: t for t in file["trials"]}
        configs = ("whole:zstd-3", "whole:xz-6", "oracle:262144", "fast-sample:262144", "portfolio-sample:262144")
        lines.append("| " + file["name"] + " | " + " | ".join(f"{rows[c]['output_bytes']:,}" for c in configs) + " |")
    lines += ["", "## Interpretation and next experiment", "",
              "Do not infer routing value from speed versus exhaustive search alone.",
              "Compare output against whole-file codecs: resetting dictionaries may",
              "cost more than codec switching saves. Sample prediction errors and codec",
              "initialization costs must also count. Mixed synthetic success would not",
              "establish general success on ordinary files.", "",
              "Next: test context-preserving segmentation and a budgeted selector with",
              "cheap features, then evaluate on unseen Silesia and real GIS/media files.",
              "Keep sample counterexamples. Do not optimize or claim held-out accuracy",
              "on this development set. External codec routing is distinct from improving",
              "the original QCore algorithm.", "",
              "Reproduce: `python benchmarks/adaptive_experiment.py` followed by",
              "`python tools/render_adaptive.py`. See [raw results](../results/adaptive.json)",
              "for source/input hashes, decisions, timing ranges and environment.", ""]
    (ROOT / "docs/ADAPTIVE_RESULTS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
