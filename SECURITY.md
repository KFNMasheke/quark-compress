# Security policy

Quark Compress 0.2 is an experimental local compression project, not a reviewed
archive extractor, backup product, or encryption tool.

The CLI produces standard compressed streams or QCore `.qkc` frames. Its 32 MiB
input/output limit is not a process-memory limit. QCore checks frame dimensions,
payload lengths, backward references, Huffman/LZ validity, checksums and trailing
data. It does not extract paths or execute archive content. These controls and
malformed-input tests are not a substitute for independent parser review or
coverage-guided fuzzing. Do not expose the decoder as a public service.

QCore CRC32/SHA-256 checks detect corruption but do not authenticate a sender.
The project provides no encryption. Keep originals and independent backups
until restoration has been verified. Interrupted writes may leave partial files.

Use this repository's private vulnerability reporting option if enabled. If
unavailable, open an issue requesting a private contact method without exploit
details or sensitive data. Include version, platform and a minimal synthetic
reproducer privately. There is no response-time guarantee or bug bounty.
Security fixes target the current development branch.
