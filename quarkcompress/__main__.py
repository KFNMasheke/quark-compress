import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .core import CODECS, SUFFIX, publish, read_input, select, trial
from . import qcore


def main():
    parser = argparse.ArgumentParser(description="Quark Compress experimental lab")
    parser.add_argument("command", choices=["analyze", "compress", "decompress", "inspect"])
    parser.add_argument("input", type=Path)
    parser.add_argument("--codec", choices=("auto",) + CODECS, default="auto")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-output", type=int, default=qcore.MAX_INPUT,
                        help="QCore decode output budget in bytes, at most 33554432")
    args = parser.parse_args()
    try:
        if args.command in ("compress", "decompress") and args.output is None:
            parser.error("compress/decompress requires --output")
        if args.command in ("decompress", "inspect"):
            with args.input.open("rb") as stream:
                frame = stream.read(qcore.MAX_CONTAINER + 1)
            if args.command == "inspect":
                print(json.dumps(qcore.inspect(frame), indent=2))
            else:
                recovered = qcore.decompress(frame, max_output=args.max_output)
                publish(args.output, recovered)
                print(json.dumps({"output": str(args.output), "bytes": len(recovered),
                                  "verified": True}))
            return 0
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
