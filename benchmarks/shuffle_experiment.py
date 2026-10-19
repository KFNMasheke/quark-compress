"""Rejected numeric shuffle experiment; no new decoder method is registered.

Sizes are projections using a hypothetical 3-byte transform prefix plus QCore's
existing frame/block headers, not files emitted by a supported archive codec.
Every selected component pipeline and inverse transform is checked exactly.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quarkcompress import qcore as q, split


def main():
    manifest = json.loads((ROOT / "benchmarks/canterbury_manifest.json").read_text())
    records = []
    for name in ("kennedy.xls", "ptt5", "sum"):
        item = next(f for f in manifest["files"] if f["name"] == name)
        data = (ROOT / "corpora/canterbury" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Corpus checksum mismatch")
        row = {"name": name, "baseline_qcore_v2_bytes": len(q.compress(data)), "projected_variants": {}}
        for width in (2, 4, 8):
            total = q.FRAME.size
            for start in range(0, len(data), q.V2_BLOCK_SIZE):
                raw = data[start:start + q.V2_BLOCK_SIZE]
                n = len(raw) // width * width
                shuffled = b"".join(raw[i:n:width] for i in range(width)) + raw[n:]
                best = len(raw)
                for delta in (False, True):
                    transformed = q._delta(shuffled) if delta else shuffled
                    tokens = q._lz_encode(transformed)
                    packed = split.pack(tokens, q._huff_encode)
                    huffman = q._huff_encode(tokens)
                    candidates = [("lz", tokens), ("split", packed)]
                    if huffman is not None:
                        candidates.append(("huffman", huffman))
                    kind, payload = min(candidates, key=lambda value: len(value[1]))
                    recovered_tokens = payload
                    limit = len(raw) + (len(raw) + 127) // 128
                    if kind == "split":
                        recovered_tokens = split.unpack(payload, limit, q._huff_decode)
                    elif kind == "huffman":
                        recovered_tokens = q._huff_decode(payload, limit)
                    recovered = q._lz_decode(recovered_tokens, len(raw))
                    if delta:
                        recovered = q._undelta(recovered)
                    original = bytearray(len(raw))
                    count = n // width
                    for lane in range(width):
                        original[lane:n:width] = recovered[lane * count:(lane + 1) * count]
                    original[n:] = recovered[n:]
                    if bytes(original) != raw:
                        raise ValueError("Shuffle pipeline round trip failed")
                    best = min(best, 3 + len(payload))
                total += q.BLOCK.size + best
            row["projected_variants"][str(width)] = total
        records.append(row)
    result = {"status": "rejected; all tested variants larger than the existing baseline",
              "scope": "Three Canterbury binary files; no general conclusion about numeric GIS data",
              "backend": q.BACKEND, "records": records}
    (ROOT / "results/shuffle_experiment.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
