# QCore v1 / QKC1 experimental format

QCore is an independent implementation of established compression techniques,
written for this project. It does not call Zstandard, XZ, gzip or Deflate for
compression. Python's `zlib.crc32` is used only for checksums. This is original
implementation work, not a claim of a novel information-theoretic algorithm.

## Pipeline

Split input into 65,536-byte blocks. For each block, compare raw storage,
LZ77, byte-delta then LZ77, canonical Huffman alone, and Huffman after either
LZ77 variant. Choose the smallest payload, including transform metadata.
Exact previously seen blocks can instead use a 4-byte backward reference.
Ties keep the first candidate. Decisions are deterministic; file extensions
are not used. This first encoder tries candidates exhaustively.

The input and decoded output are limited to 32 MiB. This is a whole-file
research implementation, not a streaming or memory-budgeted engine. Pure
Python matching/bit operations are expected to be substantially slower than
native codecs. Fixed block boundaries miss shifted duplicates; all blocks
use their own dictionary, so cross-block redundancy can be missed.

## Frame header (52 bytes, big endian)

| Field | Width | Meaning |
|---|---:|---|
| Magic/version | 4 bytes | ASCII `QKC1` |
| Original size | uint64 | 0 through 33,554,432 bytes |
| Block size | uint32 | Must equal 65,536 |
| Block count | uint32 | Exactly ceil(original size / block size) |
| SHA-256 | 32 bytes | Digest of original complete content |

Empty content has zero blocks and SHA-256 of empty content. Frames cannot be
concatenated and trailing bytes are rejected. Maximum frame size is 33,561,140
bytes: original maximum plus 52 bytes and 512 block headers of 13 bytes.

## Block header (13 bytes) and payload

`method:uint8, raw_size:uint32, payload_size:uint32, crc32:uint32`, then payload.
Every block except the final one decodes to 65,536 bytes; the final size follows
from the frame's original size. Payload size must be between 1 and raw_size.
Raw fallback guarantees this bound for emitted nonempty blocks. Frame and block
headers still cause small expansion on incompressible inputs.

| Method | ID | Payload |
|---|---:|---|
| raw | 0 | Original block bytes; payload_size must equal raw_size |
| lz77 | 1 | LZ token stream |
| delta-lz77 | 2 | LZ tokens for byte-delta-transformed block |
| reference | 3 | uint32 zero-based earlier block index; exactly 4 bytes |
| huffman | 4 | Huffman-encoded original block |
| lz77-huffman | 5 | Huffman-encoded LZ tokens |
| delta-lz77-huffman | 6 | Huffman-encoded LZ tokens for byte deltas |

References must point backward; recover bytes from already decoded output.
They never recurse or read the filesystem. CRC32 validates the decoded block.
CRC32 and SHA-256 detect accidental corruption; neither authenticates the sender.

## LZ77 tokens

The encoder uses three-byte hash keys, up to 16 recent positions per key,
greedy longest matching, a 65,535-byte distance window and 65,535-byte maximum
match. It emits matches of at least 4 bytes; the format permits 3-byte matches.

- Token below 128: literal length = token + 1, followed by those 1–128 bytes.
- Token 128 through 254: match length = (token & 127) + 3, followed by a
  big-endian uint16 distance.
- Token 255: big-endian uint16 distance, then uint16 match length (130–65,535).
  All distances must be positive and at most current output length.
- Overlapping copy is permitted. Every token is checked against expected block
  output length before expansion. Final output length must match exactly.

## Byte delta

For each block, previous starts at 0. Encode `(current - previous) mod 256`,
then update previous to current. Decode cumulatively modulo 256. This is
reversible for arbitrary bytes; benefits depend on the data's byte ordering.

## Canonical Huffman payload

First a uint32 decoded token/byte count, then 256 uint8 code lengths in symbol
order, then MSB-first encoded bits. Unused symbols have zero lengths. Active
lengths range from 1 to 24. Canonical codes are assigned by increasing length,
then increasing byte value. Ties during tree construction use stable heap IDs.

Oversubscribed or incomplete trees are rejected, except a one-symbol tree
with length 1 and code 0. The encoder skips candidates requiring lengths above
24 rather than truncating them. The decoder caps intermediate token output
at raw_size + ceil(raw_size / 128). Encoded bytes must be consumed exactly,
except final zero padding of fewer than 8 bits. Extra bytes and nonzero
padding are rejected. The final decoded block still passes length and CRC checks.

## Compatibility and safety

Treat QKC1 as experimental; freeze it only after independent review and broader
tests. A future incompatible format must use a different magic/version.
Existing originals remain essential. The decoder validates size budgets before
expansion and never interprets filenames, paths or executable instructions.
The CLI verifies the entire frame before opening the output path exclusively.
Crash-safe output publication and a streaming API remain future work.
