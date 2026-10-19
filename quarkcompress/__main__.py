import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .core import CODECS, SUFFIX, publish, read_input, select, trial


def main():
    parser = argparse.ArgumentParser(description="Quark Compress experimental lab")
    parser.add_argument("command", choices=["analyze", "compress"])
    parser.add_argument("input", type=Path)
    parser.add_argument("--codec", choices=("auto",) + CODECS, default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "compress" and args.output is None:
            parser.error("compress requires --output (extension added automatically)")
        data = read_input(args.input)
        if args.codec == "auto":
            best, payload, trials, wall = select(data)
        else:
            best, payload = trial(data, args.codec)
            trials, wall = [best], best.encode_seconds + best.decode_seconds
        report = {"schema_version": 1, "selection": "exhaustive" if args.codec == "auto" else "fixed",
                  "selected": asdict(best), "trials": [asdict(t) for t in trials],
                  "trial_and_verification_wall_seconds": wall}
        if args.command == "compress":
            output = Path(str(args.output) + SUFFIX[best.codec])
            publish(output, payload)
            report["output"] = str(output)
        print(json.dumps(report, indent=2))
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
