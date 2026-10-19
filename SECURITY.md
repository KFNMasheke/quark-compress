# Security policy

Quark Compress 0.1 is an experimental local compression lab, not a reviewed
archive extractor, backup product, or encryption tool.

The CLI reads local files and produces standard compressed streams. Its 32 MiB
input limit is not a process-memory limit. Do not expose the internal decoder
to untrusted compressed data or run the lab as a service. Keep originals and
independent backups until restoration has been verified.

Use this repository's private vulnerability reporting option if enabled. If
unavailable, open an issue requesting a private contact method without exploit
details or sensitive data. Include version, platform and a minimal synthetic
reproducer privately. There is no response-time guarantee or bug bounty.
Security fixes target the current development branch.
