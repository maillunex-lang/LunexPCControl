"""Private Windows H.264 streaming adapter for an interactive desktop.

No capture until an authenticated GET; binds loopback only; the browser
never sees the internal bearer key. Requires an owner-installed FFmpeg
with h264_nvenc and an active Windows desktop session. No video saved.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import subprocess
import threading
import time

PORT = 18790
MAX_SECONDS = 180
MAX_BYTES = 100 * 1024 * 1024
AUTH_CONTEXT = b"lunexpc-video-h264-v1"
PROFILES = {
    "data": (854, 480, 10, "500k"),
    "balanced": (1280, 720, 20, "1400k"),
    "quality": (1920, 1080, 30, "3500k"),
}


def derived_video_key(upstream_secret: str) -> str:
    if not isinstance(upstream_secret, str) or len(upstream_secret) < 32:
        raise ValueError("invalid upstream secret")
    return hmac.new(upstream_secret.encode("ascii"), AUTH_CONTEXT, hashlib.sha256).hexdigest()


def ffmpeg_command(path: str, profile: str) -> list[str]:
    if profile not in PROFILES:
        raise ValueError("unsupported stream profile")
    width, height, fps, bitrate = PROFILES[profile]
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )
    return [
        path, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1",
        "-i", "desktop", "-an", "-vf", video_filter,
        "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "ll",
        "-rc", "vbr", "-b:v", bitrate, "-maxrate", bitrate,
        "-bufsize", bitrate, "-g", str(fps), "-bf", "0",
        "-profile:v", "baseline", "-level:v", "4.2",
        "-pix_fmt", "yuv420p", "-t", str(MAX_SECONDS),
        "-f", "mp4", "-movflags",
        "+empty_moov+default_base_moof+frag_keyframe",
        "-frag_duration", "400000", "-flush_packets", "1",
        "pipe:1",
    ]


class VideoHandler(BaseHTTPRequestHandler):
    server_version = "LunexPC-Video"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def _reply(self, code, body=b"Unavailable"):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        if code == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="LunexPC Video"')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}",
                                           f"localhost:{self.server.server_port}"}:
            self._reply(403)
            return
        auths = self.headers.get_all("Authorization", [])
        expected = "Bearer " + self.server.video_key
        if len(auths) != 1 or not hmac.compare_digest(auths[0], expected):
            self._reply(401, b"Not authorized")
            return
        match = re.fullmatch(r"/video/h264/(data|balanced|quality)\.mp4", self.path)
        if match is None:
            self._reply(404)
            return
        if not self.server.stream_lock.acquire(blocking=False):
            self._reply(503, b"Screen stream busy")
            return
        process = None
        try:
            try:
                process = subprocess.Popen(
                    ffmpeg_command(self.server.ffmpeg, match.group(1)),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, bufsize=0,
                    creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
                )
                # Read an MP4 initialization segment before sending HTTP 200.
                first = process.stdout.read(8192)
                if not first or b"ftyp" not in first:
                    self._reply(503, b"Screen encoder unavailable")
                    return
            except (OSError, ValueError):
                self._reply(503, b"Screen encoder unavailable")
                return

            self.send_response(200)
            self.send_header("Content-Type", 'video/mp4; codecs="avc1.42E02A"')
            self.send_header("Cache-Control", "private, no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            transmitted = len(first)
            self.wfile.write(first)
            self.wfile.flush()
            started = time.monotonic()
            while time.monotonic() - started < MAX_SECONDS and transmitted < MAX_BYTES:
                chunk = process.stdout.read(32768)
                if not chunk:
                    break
                transmitted += len(chunk)
                if transmitted > MAX_BYTES:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=4)
                if process.stdout:
                    process.stdout.close()
            self.server.stream_lock.release()

    def do_POST(self):
        self._reply(405, b"Read-only")

    def log_message(self, format, *args):
        # Never print secrets, URLs or desktop content.
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--credential-file", required=True)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    if args.port != PORT:
        raise ValueError("Only the fixed local video port is permitted")
    ffmpeg = Path(args.ffmpeg)
    credential = Path(args.credential_file)
    if not ffmpeg.is_file() or ffmpeg.is_symlink():
        raise ValueError("FFmpeg binary unavailable or redirected")
    if not credential.is_file() or credential.is_symlink():
        raise ValueError("Private MCP credential unavailable or redirected")
    secret = credential.read_text(encoding="ascii").strip()
    key = derived_video_key(secret)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), VideoHandler)
    server.video_key = key
    server.ffmpeg = str(ffmpeg)
    server.stream_lock = threading.Lock()
    server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
