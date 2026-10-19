"""QCore v1: independent experimental lossless block codec.

Original implementation of established LZ77, canonical Huffman and delta coding
techniques. No third-party compression engine is called by this module.
Not a claim of algorithmic novelty. See docs/QCORE_FORMAT.md.
"""
from collections import defaultdict, deque
import hashlib
import heapq
import struct
import zlib  # CRC32 only; never used for compression here.

MAGIC = b"QKC1"
BLOCK_SIZE = 65536
MAX_INPUT = 32 * 1024 * 1024
FRAME = struct.Struct(">4sQII32s")
BLOCK = struct.Struct(">BIII")
RAW, LZ, DELTA_LZ, REFERENCE, HUFFMAN, LZ_HUFFMAN, DELTA_LZ_HUFFMAN = range(7)
METHODS = ("raw", "lz77", "delta-lz77", "reference", "huffman",
           "lz77-huffman", "delta-lz77-huffman")
MAX_CONTAINER = FRAME.size + MAX_INPUT + (MAX_INPUT // BLOCK_SIZE) * BLOCK.size


class FormatError(ValueError):
    """Invalid, corrupt, unsupported, or over-budget QCore input."""


def _delta(data: bytes) -> bytes:
    out = bytearray(len(data))
    previous = 0
    for i, value in enumerate(data):
        out[i] = (value - previous) & 255
        previous = value
    return bytes(out)


def _undelta(data: bytes) -> bytes:
    out = bytearray(len(data))
    previous = 0
    for i, value in enumerate(data):
        previous = (previous + value) & 255
        out[i] = previous
    return bytes(out)


def _lz_encode(data: bytes) -> bytes:
    chains = defaultdict(lambda: deque(maxlen=16))
    out, literals = bytearray(), bytearray()

    def flush():
        if literals:
            out.append(len(literals) - 1)
            out.extend(literals)
            literals.clear()

    pos, size = 0, len(data)
    while pos < size:
        length, distance = 0, 0
        if pos + 3 <= size:
            key = data[pos:pos + 3]
            for start in reversed(chains.get(key, ())):
                if pos - start > 65535:
                    continue
                end = min(65535, size - pos)
                match = 3
                while match < end and data[start + match] == data[pos + match]:
                    match += 1
                if match > length:
                    length, distance = match, pos - start
                    if match == end:
                        break
        if length >= 4:  # a 3-byte match costs 3 bytes before entropy coding
            flush()
            out.append(255 if length >= 130 else 128 | (length - 3))
            out.extend(struct.pack(">H", distance))
            if length >= 130:
                out.extend(struct.pack(">H", length))
            advance = length
        else:
            literals.append(data[pos])
            if len(literals) == 128:
                flush()
            advance = 1
        for inserted in range(pos, pos + advance):
            if inserted + 3 <= size:
                chains[data[inserted:inserted + 3]].append(inserted)
        pos += advance
    flush()
    return bytes(out)


def _lz_decode(data: bytes, expected: int) -> bytes:
    out, pos = bytearray(), 0
    while pos < len(data):
        token = data[pos]
        pos += 1
        if token < 128:
            length = token + 1
            if pos + length > len(data) or len(out) + length > expected:
                raise FormatError("Invalid LZ literal")
            out.extend(data[pos:pos + length])
            pos += length
        else:
            length = (token & 127) + 3
            if pos + 2 > len(data) or len(out) + length > expected:
                raise FormatError("Invalid LZ match length")
            distance = int.from_bytes(data[pos:pos + 2], "big")
            pos += 2
            if token == 255:
                if pos + 2 > len(data):
                    raise FormatError("Truncated extended LZ length")
                length = int.from_bytes(data[pos:pos + 2], "big")
                pos += 2
                if length < 130 or len(out) + length > expected:
                    raise FormatError("Invalid extended LZ length")
            if not 1 <= distance <= len(out):
                raise FormatError("Invalid LZ match distance")
            for _ in range(length):
                out.append(out[-distance])  # overlapping matches are permitted
    if len(out) != expected:
        raise FormatError("LZ output size mismatch")
    return bytes(out)


def _codes(lengths: list[int]) -> dict[int, tuple[int, int]]:
    ordered = sorted((length, symbol) for symbol, length in enumerate(lengths) if length)
    if not ordered or any(length > 24 for length, _ in ordered):
        raise FormatError("Invalid Huffman code lengths")
    codes, code, previous = {}, 0, 0
    for length, symbol in ordered:
        code <<= length - previous
        if code >= 1 << length:
            raise FormatError("Oversubscribed Huffman tree")
        codes[symbol] = (code, length)
        code += 1
        previous = length
    if len(ordered) == 1:
        if ordered[0][0] != 1:
            raise FormatError("Invalid single-symbol Huffman tree")
    elif code != 1 << previous:
        raise FormatError("Incomplete Huffman tree")
    return codes


def _huff_encode(data: bytes) -> bytes | None:
    if not data:
        return None
    frequencies = [0] * 256
    for value in data:
        frequencies[value] += 1
    heap = [(count, symbol, symbol) for symbol, count in enumerate(frequencies) if count]
    heapq.heapify(heap)
    serial = 256
    while len(heap) > 1:
        left, right = heapq.heappop(heap), heapq.heappop(heap)
        heapq.heappush(heap, (left[0] + right[0], serial, (left[2], right[2])))
        serial += 1
    lengths = [0] * 256
    stack = [(heap[0][2], 0)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, int):
            lengths[node] = max(1, depth)
        else:
            stack.extend([(node[0], depth + 1), (node[1], depth + 1)])
    if max(lengths) > 24:
        return None  # do not emit unsupported trees
    codes = _codes(lengths)
    out = bytearray(struct.pack(">I", len(data)) + bytes(lengths))
    accumulator, bits = 0, 0
    for symbol in data:
        code, length = codes[symbol]
        accumulator = (accumulator << length) | code
        bits += length
        while bits >= 8:
            bits -= 8
            out.append((accumulator >> bits) & 255)
        accumulator &= (1 << bits) - 1
    if bits:
        out.append(accumulator << (8 - bits))
    return bytes(out)


def _huff_decode(data: bytes, limit: int) -> bytes:
    if len(data) < 261:
        raise FormatError("Truncated Huffman stream")
    expected = int.from_bytes(data[:4], "big")
    if not 1 <= expected <= limit:
        raise FormatError("Huffman expansion exceeds budget")
    lengths = list(data[4:260])
    codes = _codes(lengths)
    reverse = {(length, code): symbol for symbol, (code, length) in codes.items()}
    longest = max(lengths)
    bitpos, out = 0, bytearray()
    encoded = data[260:]
    for _ in range(expected):
        code = 0
        for length in range(1, longest + 1):
            if bitpos >= len(encoded) * 8:
                raise FormatError("Truncated Huffman bits")
            code = (code << 1) | ((encoded[bitpos // 8] >> (7 - bitpos % 8)) & 1)
            bitpos += 1
            symbol = reverse.get((length, code))
            if symbol is not None:
                out.append(symbol)
                break
        else:
            raise FormatError("Invalid Huffman code")
    if (bitpos + 7) // 8 != len(encoded):
        raise FormatError("Trailing Huffman data")
    if bitpos % 8 and encoded[-1] & ((1 << (8 - bitpos % 8)) - 1):
        raise FormatError("Nonzero Huffman padding")
    return bytes(out)


def compress(data: bytes) -> bytes:
    if len(data) > MAX_INPUT:
        raise ValueError("QCore input exceeds 32 MiB lab budget")
    count = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE
    out = bytearray(FRAME.pack(MAGIC, len(data), BLOCK_SIZE, count,
                               hashlib.sha256(data).digest()))
    seen = {}
    for index in range(count):
        raw = data[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]
        previous = seen.get(raw)
        candidates = [(RAW, raw)]
        if previous is not None:
            candidates.append((REFERENCE, struct.pack(">I", previous)))
        else:
            lz = _lz_encode(raw)
            delta_lz = _lz_encode(_delta(raw))
            candidates.extend([(LZ, lz), (DELTA_LZ, delta_lz)])
            for method, value in ((HUFFMAN, raw), (LZ_HUFFMAN, lz),
                                  (DELTA_LZ_HUFFMAN, delta_lz)):
                encoded = _huff_encode(value)
                if encoded is not None:
                    candidates.append((method, encoded))
            seen[raw] = index
        method, payload = min(candidates, key=lambda item: len(item[1]))
        out.extend(BLOCK.pack(method, len(raw), len(payload), zlib.crc32(raw)))
        out.extend(payload)
    return bytes(out)


def _unpack(data: bytes, max_output: int, materialize: bool):
    if not 0 <= max_output <= MAX_INPUT:
        raise ValueError("Output budget must be between zero and 32 MiB")
    if not FRAME.size <= len(data) <= MAX_CONTAINER:
        raise FormatError("Invalid QCore frame size")
    magic, total, block_size, count, digest = FRAME.unpack_from(data)
    if magic != MAGIC or block_size != BLOCK_SIZE:
        raise FormatError("Unsupported QCore format")
    if total > max_output or count != (total + BLOCK_SIZE - 1) // BLOCK_SIZE:
        raise FormatError("Invalid or over-budget output size")
    out, pos, metadata = bytearray(), FRAME.size, []
    for index in range(count):
        if pos + BLOCK.size > len(data):
            raise FormatError("Truncated block header")
        method, raw_size, packed_size, checksum = BLOCK.unpack_from(data, pos)
        pos += BLOCK.size
        expected = min(BLOCK_SIZE, total - index * BLOCK_SIZE)
        if method >= len(METHODS) or raw_size != expected:
            raise FormatError("Invalid block method or output size")
        if not 1 <= packed_size <= raw_size or pos + packed_size > len(data):
            raise FormatError("Invalid block payload size")
        payload = data[pos:pos + packed_size]
        pos += packed_size
        metadata.append({"index": index, "method": METHODS[method],
                         "raw_bytes": raw_size, "payload_bytes": packed_size})
        if method == RAW:
            if packed_size != raw_size:
                raise FormatError("Raw block length mismatch")
            raw = payload
        elif method == REFERENCE:
            if packed_size != 4:
                raise FormatError("Invalid reference size")
            target = int.from_bytes(payload, "big")
            if target >= index:
                raise FormatError("Reference must point to an earlier block")
            raw = bytes(out[target * BLOCK_SIZE:target * BLOCK_SIZE + raw_size])
            if len(raw) != raw_size:
                raise FormatError("Invalid reference range")
        else:
            if method in (HUFFMAN, LZ_HUFFMAN, DELTA_LZ_HUFFMAN):
                payload = _huff_decode(payload, raw_size + (raw_size + 127) // 128)
            raw = payload if method == HUFFMAN else _lz_decode(payload, raw_size)
            if method in (DELTA_LZ, DELTA_LZ_HUFFMAN):
                raw = _undelta(raw)
        if len(raw) != raw_size or zlib.crc32(raw) != checksum:
            raise FormatError("Block checksum or length mismatch")
        out.extend(raw)
    if pos != len(data):
        raise FormatError("Trailing frame data")
    if len(out) != total or hashlib.sha256(out).digest() != digest:
        raise FormatError("Frame digest mismatch")
    if materialize:
        return bytes(out)
    return {"format": "QKC1", "input_bytes": total, "frame_bytes": len(data),
            "verified": True, "blocks": metadata}


def decompress(data: bytes, *, max_output: int = MAX_INPUT) -> bytes:
    """Decode with strict bounds and corruption checks; still experimental."""
    return _unpack(data, max_output, True)


def inspect(data: bytes) -> dict:
    """Fully decode and verify before returning block statistics."""
    return _unpack(data, MAX_INPUT, False)
