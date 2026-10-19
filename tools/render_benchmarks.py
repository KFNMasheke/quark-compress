"""Render the complete verified Canterbury run without cherry-picking samples."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "results/canterbury.json"
    report = json.loads(path.read_text())
    if not report.get("complete") or len(report["files"]) != 11:
        raise ValueError("Only a completed 11-file run can be rendered")
    for key, source in (("qcore_source_sha256", "quarkcompress/qcore.py"),
                        ("native_source_sha256", "native/qcore_native.c"),
                        ("split_source_sha256", "quarkcompress/split.py")):
        if report[key] != hashlib.sha256((ROOT / source).read_bytes()).hexdigest():
            raise ValueError(f"Measured source changed: {source}")
    compiler = shutil.which("cc")
    if compiler:
        version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
        report["local_native_build"] = {
            "compiler_version": version,
            "command": "CC=cc LDSHARED='cc -shared' python setup.py build_ext --inplace",
            "optimization": "setuptools/CPython supplied -O3 and host hardening flags; see build instructions",
        }
    path.write_text(json.dumps(report, indent=2) + "\n")
    totals = {}
    baseline_best = 0
    passing_files = 0
    lines = ["# QCore v2: Canterbury results", "",
             "All 11 pinned Canterbury inputs were tested, with exact recovery on every trial.",
             "One warm-up and three timed repetitions ran sequentially in isolated child processes.",
             "Times below sum each file's median; peak RSS is the largest per-file process peak.",
             "It includes interpreter/data memory. Timings exclude file I/O and process startup.", "",
             "| Configuration | Total output bytes | Encode seconds | Decode seconds | Peak process MiB |",
             "|---|---:|---:|---:|---:|"]
    for codec in [trial["codec"] for trial in report["files"][0]["trials"]]:
        trials = [next(t for t in file["trials"] if t["codec"] == codec) for file in report["files"]]
        total = {"bytes": sum(t["output_bytes"] for t in trials),
                 "encode": sum(t["encode_seconds_median"] for t in trials),
                 "decode": sum(t["decode_seconds_median"] for t in trials),
                 "rss": max(t["process_peak_rss_bytes"] or 0 for t in trials)}
        totals[codec] = total
        lines.append(f"| {codec} | {total['bytes']:,} | {total['encode']:.6f} | {total['decode']:.6f} | {total['rss']/1048576:.2f} |")
    old, new = totals["qcore-python-v1"], totals["qcore-native-v2"]
    lines += ["", "## Improvement over the original Python v1 reference", "",
              f"- Output reduction: {100*(1-new['bytes']/old['bytes']):.2f}%.",
              f"- Encoding speedup: {old['encode']/new['encode']:.2f}x.",
              f"- Decoding speedup: {old['decode']/new['decode']:.2f}x.",
              "", "This combines new parsing/model choices and native implementation changes; it is",
              "not an identical-instruction language comparison. Native-v1 isolates the earlier",
              "format configuration. All v2 block-size/model trials count in encoding time.", "",
              "## Per-file sizes", "",
              "| File | Original bytes | Python v1 bytes | Native v2 bytes | Best fixed baseline | Baseline bytes |",
              "|---|---:|---:|---:|---|---:|"]
    for file in report["files"]:
        rows = {t["codec"]: t for t in file["trials"]}
        best = min((t for t in file["trials"] if not t["codec"].startswith("qcore")), key=lambda t: t["output_bytes"])
        baseline_best += best["output_bytes"]
        if rows["qcore-native-v2"]["output_bytes"] <= 1.05 * best["output_bytes"]:
            passing_files += 1
        lines.append(f"| {file['name']} | {file['input_bytes']:,} | {rows['qcore-python-v1']['output_bytes']:,} | {rows['qcore-native-v2']['output_bytes']:,} | {best['codec']} | {best['output_bytes']:,} |")
    zstd = totals["zstd-3"]
    lines += ["", "## Parity status", "",
              f"Size within 5% of the best tested fixed baseline: **{passing_files}/11 files** (target: at least 9/11).",
              f"Aggregate size versus the per-file best baseline: **{new['bytes']/baseline_best:.3f}x** (target: at most 1.05x).",
              f"Encode throughput versus Zstd-3: **{zstd['encode']/new['encode']:.3f}x** (target: at least 0.8x at comparable size).",
              f"Decode throughput versus Zstd-3: **{zstd['decode']/new['decode']:.3f}x**.",
              "", "**General parity has not been reached.** Zstandard and XZ remain stronger on",
              "important size/speed measures. These are local results with timing variation,",
              "not claims about every machine or workload. Native 7-Zip, Brotli, LZ4, Silesia,",
              "GIS and compressed media are not covered by this run. Canterbury was used during",
              "iteration, so it is no longer a held-out evaluation set.", "",
              "A separate 2/4/8-byte shuffle experiment was rejected: all projected variants",
              "were larger on the three tested binary inputs. No transform method was added.",
              "See [experiment measurements](../results/shuffle_experiment.json) and reproduce",
              "with `python benchmarks/shuffle_experiment.py`. This does not rule out shuffling",
              "on other numeric datasets.", "",
              "See [parity gates](PARITY_GATES.md), [raw measurements](../results/canterbury.json),",
              "[input manifest](../benchmarks/canterbury_manifest.json), and",
              "[reproduction instructions](../benchmarks/README.md).", ""]
    (ROOT / "docs/QCORE_RESULTS.md").write_text("\n".join(lines))
    print(json.dumps({"output_reduction_percent": 100*(1-new['bytes']/old['bytes']),
                      "encode_speedup": old['encode']/new['encode'],
                      "decode_speedup": old['decode']/new['decode'],
                      "size_parity_files": passing_files, "aggregate_size_ratio": new['bytes']/baseline_best}, indent=2))


if __name__ == "__main__":
    main()
