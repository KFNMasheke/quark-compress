# QCore v2 (QKC2)

QKC2 retains the [v1 frame and token layout](QCORE_FORMAT.md) and checksum
rules, with the following explicit changes. QKC1 decoding remains supported.
Old QKC1 decoders must reject QKC2; the format is still experimental.

## Frame and block choice

Magic is ASCII `QKC2`. The frame header's block-size field accepts exactly
65,536 or 262,144. Block count is ceil(original size / chosen block size).
Raw sizes and reference indices use that chosen size consistently throughout
the frame. Maximum input/output remains 32 MiB. The encoder tries both sizes
for inputs larger than 64 KiB and keeps the smaller complete frame, with 64 KiB
winning a tie. Whole-file hashes, headers and all fields count in this choice.
Trying both costs extra CPU; it is not a predictive planner.

LZ distances remain limited to 65,535, and long matches to 65,535. Larger
blocks preserve the match table between former 64 KiB boundaries and amortize
model/header overhead. The 64 KiB candidate preserves fine-grained duplicate
references when those produce a smaller result.

## Additional methods

IDs 0–6 retain v1 meaning. QKC2 additionally permits:

| ID | Method | Decoding |
|---:|---|---|
| 7 | split-lz77 | Unpack factored token fields, reconstruct LZ tokens, decode |
| 8 | delta-split-lz77 | As above, then reverse the byte-delta transform |

These candidates are attempted only when the LZ token stream is at least
1,024 bytes and smaller than the original block. All original candidates and
raw storage remain available. This heuristic limits setup costs; it does not
claim an optimal parse or globally optimal compression.

## Factored payload

Exactly six fields appear, in order: control tokens, literal bytes, distance
high bytes, distance low bytes, extended-length high bytes, extended-length
low bytes. Each field starts with `method:uint8, decoded_size:uint32,
payload_size:uint32` (9 bytes, big endian), immediately followed by payload.

Method 0 stores raw field bytes and requires equal sizes. Method 1 uses the v1
canonical Huffman payload, including its own decoded count and 256 code-length
bytes. Method 2 stores the same Huffman model and bits with a compact table:
after the uint32 decoded count, `(run_length_minus_one:uint8, code_length:uint8)`
pairs reconstruct exactly 256 code lengths, followed by the unchanged bits.
Runs cannot exceed the table boundary, lengths cannot exceed 24, and at least
one encoded-bit byte must remain. The reconstructed payload then passes the
normal bounded Huffman decoder, including tree and padding validation.
The field's declared decoded size must match the Huffman count. Empty fields
must use method 0 and both sizes zero. Payload size cannot exceed decoded size.
The encoder chooses the smallest complete raw, dense-Huffman or compact-Huffman
payload, with raw winning a tie.

The sum of decoded field sizes is bounded by raw block size + ceil(raw block
size / 128), before any field is expanded. During reconstruction:

- Each control byte below 128 consumes token + 1 literal bytes.
- Each control byte at least 128 consumes one byte from each distance field.
- Control 255 also consumes one byte from each extended-length field.

All fields must be consumed exactly, corresponding high/low fields must have
equal lengths, and trailing bytes are rejected. Reconstructed tokens pass the
normal bounded LZ decoder and original-content checksums.

## Native implementation

The optional CPython C extension accelerates matching, LZ decoding, deltas,
frequency counting, Huffman packing/decoding, and token factoring/reassembly.
It implements the same format, not a different proprietary backend. Python
reference decoders and cross-implementation tests remain available.

The native encoder uses four-byte hash keys and searches up to 64 hash-chain entries per position; the
Python reference tracks 16 positions per exact three-byte key. Therefore
compressed bytes can differ across backends even though decoding is compatible.
Encoding is deterministic within a fixed backend and source revision.
The C extension currently holds the GIL; applications should use worker
processes for CPU isolation and responsive UI work.
