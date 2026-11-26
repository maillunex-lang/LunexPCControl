"""Owner-initiated, bounded, in-memory JPEG previews of an enrolled Windows agent.

No background capture: only authorized /api/live/frame GET requests trigger
screenshots. No raw PNG or JPEG is written to disk. Device credentials never
reach the browser or appear in the HTTP query string.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import re
import socket
import sqlite3
import threading
import time

from PIL import Image, ImageOps, UnidentifiedImageError
from server.screen_history import extract_pngs

MAX_SSE = 8 * 1024 * 1024
MAX_JPEG = 650 * 1024
FRAME_INTERVAL = 1.0
MAX_DEVICES = 25
PROFILE = {
    "data": (640, 45),
    "balanced": (960, 55),
    "quality": (1280, 65),
}


class LiveError(Exception):
    """Expected transient offline, authorization, or response problem."""


def device_routes(path):
    connection = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=3)
    try:
        rows = connection.execute(
            "SELECT device,port FROM routes ORDER BY device LIMIT ?", (MAX_DEVICES,)
        ).fetchall()
    finally:
        connection.close()
    return [(device, int(port)) for device, port in rows
            if isinstance(device, str) and re.fullmatch("[A-Za-z0-9_-]{1,64}", device)
            and type(port) is int and 20000 <= port <= 29999]


def probe_devices(path, connector=None):
    """TCP presence says the reverse tunnel is reachable, not that UI consent holds."""
    result = []
    for name, port in device_routes(path):
        live = False
        try:
            if connector:
                live = bool(connector(port))
            else:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    live = True
        except OSError:
            pass
        result.append({
            "id": name, "tunnel_online": live, "status": "connected" if live else "offline",
            "connection": "outbound-ssh", "ip_required": False,
        })
    return result


def _parse_sse(body):
    """Return the first complete JSON-RPC response event; reject huge streams."""
    if len(body) > MAX_SSE:
        raise LiveError("oversized upstream response")
    for event in body.replace(b"\r\n", b"\n").split(b"\n\n"):
        lines = [line[5:].lstrip() for line in event.split(b"\n")
                 if line.startswith(b"data:")]
        if not lines:
            continue
        try:
            data = json.loads(b"\n".join(lines))
        except (ValueError, UnicodeError):
            continue
        if isinstance(data, dict) and "result" in data:
            return data
    raise LiveError("missing complete JSON-RPC response")


def _post_mcp(port, secret, method, params, ident, session=None, timeout=10):
    request = {"jsonrpc": "2.0", "method": method, "params": params}
    if ident is not None:
        request["id"] = ident
    body = json.dumps(request, separators=(",", ":")).encode()
    headers = {
        "Authorization": "Bearer " + secret,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("POST", "/mcp", body=body, headers=headers)
        response = connection.getresponse()
        sid = response.getheader("Mcp-Session-Id")
        if response.status not in (200, 202, 204):
            response.read(min(1024, MAX_SSE))
            raise LiveError("upstream refused the request")
        if ident is None:
            response.read(1024)
            return None, sid
        data = bytearray()
        if "text/event-stream" in response.getheader("Content-Type", ""):
            while len(data) < MAX_SSE:
                chunk = response.read1(min(65536, MAX_SSE - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                normalized = bytes(data).replace(b"\r\n", b"\n")
                if b"\n\n" in normalized:
                    try:
                        _parse_sse(normalized)
                    except LiveError:
                        continue
                    break
            return _parse_sse(bytes(data)), sid
        data.extend(response.read(MAX_SSE + 1))
        if len(data) > MAX_SSE:
            raise LiveError("upstream response too large")
        try:
            return json.loads(data), sid
        except (ValueError, UnicodeError):
            raise LiveError("invalid upstream JSON") from None
    except (TimeoutError, OSError, http.client.HTTPException) as exc:
        raise LiveError("Windows agent connection unavailable") from exc
    finally:
        connection.close()


def take_screenshot(port, secret):
    """One MCP screenshot in one authenticated session (best effort)."""
    hello = {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "LunexPCControl-LiveView", "version": "1.0"},
    }
    _, session = _post_mcp(port, secret, "initialize", hello, 1)
    if not session:
        raise LiveError("MCP session not established")
    _post_mcp(port, secret, "notifications/initialized", {}, None, session)
    doc, _ = _post_mcp(port, secret, "tools/call",
                       {"name": "Screenshot", "arguments": {}}, 2, session, timeout=18)
    if not isinstance(doc, dict):
        raise LiveError("invalid MCP response")
    png = extract_pngs(json.dumps(doc, separators=(",", ":")).encode())
    if not png:
        raise LiveError("no permitted screenshot returned")
    return png[0]


def encode_preview(png, profile="balanced"):
    if profile not in PROFILE:
        raise ValueError("invalid quality profile")
    width, quality = PROFILE[profile]
    try:
        with Image.open(io.BytesIO(png)) as image:
            if image.format != "PNG":
                raise LiveError("not a PNG frame")
            if image.width < 1 or image.height < 1 or image.width * image.height > 18_000_000:
                raise LiveError("invalid frame dimensions")
            output = ImageOps.exif_transpose(image).convert("RGB")
            output.thumbnail((width, 1280), Image.Resampling.BILINEAR)
            stream = io.BytesIO()
            output.save(stream, format="JPEG", quality=quality, optimize=True)
            data = stream.getvalue()
            if len(data) > MAX_JPEG:
                raise LiveError("preview exceeds size limit")
            return data
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise LiveError("image conversion failed") from exc


class LiveFrameService:
    """At most one active capture at a time, cached briefly across viewers."""
    def __init__(self, registry, capture=take_screenshot, clock=time.monotonic):
        self.registry = registry
        self.capture = capture
        self.clock = clock
        self.lock = threading.Lock()
        self.last = {}
        self.last_capture = {}

    def frame(self, device, profile="balanced"):
        if not re.fullmatch("[A-Za-z0-9_-]{1,64}", device):
            raise LiveError("invalid device")
        if profile not in PROFILE:
            raise LiveError("invalid profile")
        if not self.lock.acquire(blocking=False):
            raise LiveError("capture busy")
        try:
            now = self.clock()
            key = (device, profile)
            item = self.last.get(key)
            if item is not None and now - item[0] < FRAME_INTERVAL:
                return item[1], item[2], False
            if now - self.last_capture.get(device, -1e10) < FRAME_INTERVAL:
                raise LiveError("capture rate limited")
            conn = sqlite3.connect("file:" + str(self.registry) + "?mode=ro", uri=True, timeout=3)
            try:
                route = conn.execute("SELECT port,upstream_key FROM routes WHERE device=?",
                                     (device,)).fetchone()
            finally:
                conn.close()
            if not route:
                raise LiveError("device not registered")
            port, secret = route
            if not (type(port) is int and 20000 <= port <= 29999
                    and isinstance(secret, str) and len(secret) >= 24):
                raise LiveError("invalid device route")
            self.last_capture[device] = self.clock()
            png = self.capture(port, secret)
            jpeg = encode_preview(png, profile)
            etag = hashlib.sha256(jpeg).hexdigest()[:32]
            self.last[key] = (self.clock(), jpeg, etag)
            # Keep only bounded cached data. Purge other profiles/devices.
            if len(self.last) > MAX_DEVICES:
                self.last = {key: self.last[key]}
            return jpeg, etag, True
        finally:
            self.lock.release()
