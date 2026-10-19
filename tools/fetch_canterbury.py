"""Fetch pinned corpus bytes, with bounded reads and mandatory SHA-256 checks."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "benchmarks/canterbury_manifest.json").read_text())
    destination = ROOT / "corpora/canterbury"
    destination.mkdir(parents=True, exist_ok=True)
    commit = manifest["mirror_commit"]
    for item in manifest["files"]:
        name, size = item["name"], item["bytes"]
        if Path(name).name != name or not 0 < size <= 32 * 1024 * 1024:
            raise ValueError("Invalid corpus filename or size")
        expected_url = f"https://raw.githubusercontent.com/zlib-ng/corpora/{commit}/canterbury/{name}"
        if item["url"] != expected_url:
            raise ValueError("Unexpected corpus origin")
        target = destination / name
        if target.exists():
            with target.open("rb") as stream:
                data = stream.read(size + 1)
        else:
            with urllib.request.urlopen(expected_url, timeout=30) as response:
                data = response.read(size + 1)
        if len(data) != size or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Corpus integrity check failed: {name}")
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(data)
        print(f"Verified {name}: {size} bytes")


if __name__ == "__main__":
    main()
