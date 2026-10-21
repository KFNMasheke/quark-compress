"""Loopback-only browser workspace. File contents live in memory for this session."""
import argparse
from dataclasses import asdict
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import lzma
from pathlib import Path
import secrets
import threading
import time
import urllib.parse
import webbrowser
import zlib

import zstandard as zstd
from . import core, qcore

WEB = Path(__file__).with_name("web")
UPLOAD_LIMIT = qcore.MAX_CONTAINER + 1024 * 1024


def restore(data):
    """Restore exactly one bounded stream; never use trusted-trial decoders here."""
    if data[:4] in (b"QKC1", b"QKC2"):
        return qcore.decompress(data, max_output=core.MAX_INPUT)
    if data.startswith(b"\x1f\x8b"):
        decoder = zlib.decompressobj(31)
        output = decoder.decompress(data, core.MAX_INPUT + 1)
        if len(output) > core.MAX_INPUT or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Gzip is incomplete, contains extra streams, or exceeds 32 MiB")
        return output
    if data.startswith(b"\xfd7zXZ\x00"):
        decoder = lzma.LZMADecompressor(memlimit=256 * 1024 * 1024)
        output = decoder.decompress(data, max_length=core.MAX_INPUT + 1)
        if len(output) > core.MAX_INPUT or not decoder.eof or decoder.unused_data:
            raise ValueError("XZ is incomplete, contains extra streams, or exceeds 32 MiB")
        return output
    if data.startswith(b"\x28\xb5\x2f\xfd"):
        frame = zstd.get_frame_parameters(data)
        if frame.window_size > 128 * 1024 * 1024 or frame.content_size not in (zstd.CONTENTSIZE_UNKNOWN, zstd.CONTENTSIZE_ERROR) and frame.content_size > core.MAX_INPUT:
            raise ValueError("Zstandard frame exceeds workspace limits")
        output = zstd.ZstdDecompressor(max_window_size=128 * 1024).decompress(
            data, max_output_size=core.MAX_INPUT, allow_extra_data=False)
        if len(output) > core.MAX_INPUT:
            raise ValueError("Restored file exceeds 32 MiB")
        return output
    raise ValueError("Choose a QCore, gzip, Zstandard, or XZ file. Raw files need no restoration.")


class Workspace:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.jobs = {}
        self.active = False

    def submit(self, data, name, mode, codec):
        if mode not in ("compress", "compare", "restore") or codec not in core.CODECS:
            raise ValueError("Unknown operation or engine")
        if len(data) > (UPLOAD_LIMIT if mode == "restore" else core.MAX_INPUT):
            raise ValueError("Workspace limit is 32 MiB per original file")
        with self.lock:
            if self.active:
                raise ValueError("An operation is already running. Wait for it to finish.")
            self.active = True
            # Keep at most two completed outputs in memory, never write uploaded paths.
            while len(self.jobs) >= 2:
                self.jobs.pop(next(iter(self.jobs)))
            job_id = secrets.token_hex(12)
            self.jobs[job_id] = dict(id=job_id, name=name, status="running", progress="Starting", trials=[])
        threading.Thread(target=self.run, args=(job_id, data, mode, codec), daemon=True).start()
        return job_id

    def run(self, job_id, data, mode, codec):
        try:
            started = time.perf_counter()
            if mode == "restore":
                output = restore(data)
                name = self.jobs[job_id]["name"]
                for suffix in (".qkc", ".gz", ".zst", ".xz"):
                    if name.lower().endswith(suffix):
                        name = name[:-len(suffix)]
                        break
                result = dict(filename=(name or "restored") + ".restored", trials=[],
                              input_bytes=len(data), output_bytes=len(output),
                              sha256=hashlib.sha256(output).hexdigest(), verified=False,
                              message="Decoded successfully. Compare this SHA-256 with your original to confirm identity.")
            else:
                engines = ("store", "zstd-3", "gzip-9", "qcore-2") if mode == "compare" else (codec,)
                best, output, trials = None, b"", []
                for engine in engines:
                    with self.lock:
                        self.jobs[job_id]["progress"] = "Testing " + engine
                    result, packed = core.trial(data, engine)
                    trials.append(asdict(result))
                    if best is None or result.output_bytes < best.output_bytes:
                        best, output = result, packed
                result = {**asdict(best), "trials": trials,
                          "filename": self.jobs[job_id]["name"] + core.SUFFIX[best.codec],
                          "message": "Restored bytes match the original. SHA-256 verified."}
            with self.lock:
                self.jobs[job_id].update(result, status="complete", progress="Complete",
                                         seconds=time.perf_counter() - started, output=output)
        except Exception as error:
            with self.lock:
                self.jobs[job_id].update(status="failed", error=str(error)[:300])
        finally:
            with self.lock:
                self.active = False


def create_server(port=3881):
    workspace = Workspace()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log names or uploaded contents.

        def send(self, status, data, mime="application/json", extra=None):
            if isinstance(data, (dict, list)):
                data = json.dumps(data).encode()
            self.send_response(status)
            for key, value in {"Content-Type": mime, "Content-Length": str(len(data)),
                               "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                               "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                               "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'", **(extra or {})}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, mutation=False):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host:
                self.send(403, {"error": "Use the local workspace address"})
                return False
            if mutation and (self.headers.get("Origin") != "http://" + host or not secrets.compare_digest(self.headers.get("X-Quark-Token", ""), workspace.token)):
                self.send(403, {"error": "Refresh the local workspace before continuing"})
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/api/session":
                return self.send(200, {"token": workspace.token, "limit": core.MAX_INPUT, "backend": qcore.BACKEND})
            if parsed.path.startswith("/api/jobs/"):
                parts = parsed.path.split("/")
                with workspace.lock:
                    job = workspace.jobs.get(parts[3])
                    if not job:
                        return self.send(404, {"error": "Result expired. Run the operation again."})
                    if len(parts) == 5 and parts[4] == "download":
                        if job["status"] != "complete":
                            return self.send(409, {"error": "Result is not ready"})
                        filename = urllib.parse.quote(job["filename"], safe="")
                        return self.send(200, job["output"], "application/octet-stream", {"Content-Disposition": "attachment; filename*=UTF-8''" + filename})
                    return self.send(200, {k: v for k, v in job.items() if k != "output"})
            asset = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}.get(parsed.path)
            if asset:
                return self.send(200, (WEB / asset).read_bytes(), {"html": "text/html; charset=utf-8", "js": "text/javascript", "css": "text/css"}[asset.split(".")[-1]])
            self.send(404, {"error": "Not found"})

        def do_POST(self):
            if not self.allowed(True):
                return
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/api/shutdown":
                self.send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if parsed.path != "/api/jobs":
                return self.send(404, {"error": "Not found"})
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if length < 0 or length > UPLOAD_LIMIT:
                    return self.send(413, {"error": "File exceeds workspace limit"})
                self.connection.settimeout(30)
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValueError("Upload interrupted")
                query = urllib.parse.parse_qs(parsed.query)
                name = query.get("name", ["file"])[0].replace("\\", "/").split("/")[-1][:160] or "file"
                job_id = workspace.submit(data, name, query.get("mode", ["compress"])[0], query.get("codec", ["zstd-3"])[0])
                self.send(202, {"id": job_id})
            except (ValueError, TimeoutError) as error:
                self.send(400, {"error": str(error)[:300]})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description="Quark local graphical workspace")
    parser.add_argument("--port", type=int, default=3881)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = create_server(args.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print("Quark workspace: " + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
