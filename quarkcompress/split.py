"""QCore v2 LZ token factoring. Independent of a particular entropy backend."""
import struct
import os

STREAM = struct.Struct(">BII")
COUNT = 6


def compact_huffman(payload: bytes) -> bytes:
    """RLE the 256 code lengths, leaving the canonical bitstream unchanged."""
    if len(payload) < 261:
        raise ValueError("Truncated Huffman payload")
    lengths = payload[4:260]
    out = bytearray(payload[:4])
    pos = 0
    while pos < 256:
        end = pos + 1
        while end < 256 and lengths[end] == lengths[pos]:
            end += 1
        out.extend((end - pos - 1, lengths[pos]))
        pos = end
    out.extend(payload[260:])
    return bytes(out)


def expand_huffman(payload: bytes) -> bytes:
    if len(payload) < 7:
        raise ValueError("Truncated compact Huffman payload")
    lengths, pos = bytearray(), 4
    while len(lengths) < 256:
        if pos + 2 > len(payload):
            raise ValueError("Truncated compact Huffman lengths")
        run, length = payload[pos] + 1, payload[pos + 1]
        pos += 2
        if length > 24 or len(lengths) + run > 256:
            raise ValueError("Invalid compact Huffman run")
        lengths.extend(bytes([length]) * run)
    if pos == len(payload):
        raise ValueError("Missing compact Huffman bits")
    return payload[:4] + bytes(lengths) + payload[pos:]


def factor(tokens: bytes) -> tuple[bytes, ...]:
    """Separate controls, literals, distance high/low and long-length high/low."""
    fields = [bytearray() for _ in range(COUNT)]
    pos = 0
    while pos < len(tokens):
        token = tokens[pos]
        pos += 1
        fields[0].append(token)
        if token < 128:
            length = token + 1
            if pos + length > len(tokens):
                raise ValueError("Truncated factored literals")
            fields[1].extend(tokens[pos:pos + length])
            pos += length
        else:
            if pos + 2 > len(tokens):
                raise ValueError("Truncated factored distance")
            fields[2].append(tokens[pos])
            fields[3].append(tokens[pos + 1])
            pos += 2
            if token == 255:
                if pos + 2 > len(tokens):
                    raise ValueError("Truncated factored long length")
                fields[4].append(tokens[pos])
                fields[5].append(tokens[pos + 1])
                pos += 2
    return tuple(bytes(field) for field in fields)


def join(fields: tuple[bytes, ...], limit: int) -> bytes:
    if len(fields) != COUNT or sum(map(len, fields)) > limit:
        raise ValueError("Factored stream budget exceeded")
    controls, literals, dist_hi, dist_lo, len_hi, len_lo = fields
    if len(dist_hi) != len(dist_lo) or len(len_hi) != len(len_lo):
        raise ValueError("Factored field length mismatch")
    literal_pos, distance_pos, length_pos = 0, 0, 0
    out = bytearray()
    for token in controls:
        out.append(token)
        if token < 128:
            length = token + 1
            if literal_pos + length > len(literals):
                raise ValueError("Truncated factored literals")
            out.extend(literals[literal_pos:literal_pos + length])
            literal_pos += length
        else:
            if distance_pos >= len(dist_hi):
                raise ValueError("Truncated factored distance")
            out.extend((dist_hi[distance_pos], dist_lo[distance_pos]))
            distance_pos += 1
            if token == 255:
                if length_pos >= len(len_hi):
                    raise ValueError("Truncated factored long length")
                out.extend((len_hi[length_pos], len_lo[length_pos]))
                length_pos += 1
    if literal_pos != len(literals) or distance_pos != len(dist_hi) or length_pos != len(len_hi):
        raise ValueError("Unused factored field data")
    return bytes(out)


def pack(tokens: bytes, huff_encode) -> bytes:
    out = bytearray()
    for raw in factor(tokens):
        encoded = huff_encode(raw) if raw else None
        candidates = [(0, raw)]
        if encoded is not None:
            candidates.extend(((1, encoded), (2, compact_huffman(encoded))))
        method, payload = min(candidates, key=lambda candidate: len(candidate[1]))
        out.extend(STREAM.pack(method, len(raw), len(payload)))
        out.extend(payload)
    return bytes(out)


def unpack(data: bytes, limit: int, huff_decode) -> bytes:
    pos, remaining, fields = 0, limit, []
    for _ in range(COUNT):
        if pos + STREAM.size > len(data):
            raise ValueError("Truncated factored field header")
        method, raw_size, packed_size = STREAM.unpack_from(data, pos)
        pos += STREAM.size
        if method > 2 or raw_size > remaining or packed_size > raw_size:
            raise ValueError("Invalid factored field size or method")
        if pos + packed_size > len(data):
            raise ValueError("Truncated factored field")
        payload = data[pos:pos + packed_size]
        pos += packed_size
        if method == 0:
            if packed_size != raw_size:
                raise ValueError("Raw factored field size mismatch")
            raw = payload
        else:
            if raw_size == 0:
                raise ValueError("Empty Huffman field")
            if method == 2:
                payload = expand_huffman(payload)
            raw = huff_decode(payload, raw_size)
            if len(raw) != raw_size:
                raise ValueError("Huffman field size mismatch")
        fields.append(raw)
        remaining -= raw_size
    if pos != len(data):
        raise ValueError("Trailing factored data")
    return join(tuple(fields), limit)


_python_factor = factor
_python_join = join
if os.environ.get("QUARK_PURE_PYTHON") != "1":
    try:
        from . import _qcore_native
    except ImportError:
        pass
    else:
        factor = _qcore_native.factor
        join = _qcore_native.join
