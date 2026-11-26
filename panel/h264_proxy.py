"""Authenticated loopback relay for the separate interactive Windows H.264 agent.

The upstream device token is read only from the owner-private registry.
A purpose-bound HMAC key grants video-only access, not MCP commands.
The viewer receives raw fragmented MP4 over an authenticated HTTPS route.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import re
import sqlite3

from panel.live_view import LiveError

H264_PROFILE_NAMES = frozenset({"data", "balanced", "quality"})
MAX_H264_BYTES = 100 * 1024 * 1024
MAX_H264_SECONDS = 180
DERIVATION_LABEL = b"lunexpc-video-h264-v1"


def purpose_bound_key(mcp_secret: str) -> str:
    if not isinstance(mcp_secret, str) or len(mcp_secret) < 32:
        raise LiveError("invalid upstream credential")
    try:
        key=mcp_secret.encode("ascii")
    except UnicodeEncodeError:
        raise LiveError("invalid upstream credential") from None
    return hmac.new(key, DERIVATION_LABEL, hashlib.sha256).hexdigest()


def video_route(registry, device, profile):
    if not isinstance(device,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",device):
        raise LiveError("invalid device")
    if profile not in H264_PROFILE_NAMES:
        raise LiveError("invalid H264 quality")
    try:
        db=sqlite3.connect("file:"+str(registry)+"?mode=ro",uri=True,timeout=3)
        try:
            row=db.execute("SELECT port,upstream_key FROM routes WHERE device=?",(device,)).fetchone()
        finally:
            db.close()
    except sqlite3.Error as e:
        raise LiveError("device registry unavailable") from e
    if not row:
        raise LiveError("device not registered")
    port,secret=row
    if type(port) is not int or not 20000<=port<=29998:
        raise LiveError("invalid tunnel port")
    return port+1,purpose_bound_key(secret)


def open_h264_stream(registry, device, profile, connection_factory=None):
    video_port,video_key=video_route(registry,device,profile)
    if connection_factory is None:
        connection_factory=http.client.HTTPConnection
    conn=connection_factory("127.0.0.1",video_port,timeout=18)
    try:
        conn.request("GET",f"/video/h264/{profile}.mp4",headers={
            "Authorization":"Bearer "+video_key,
            "Accept":"video/mp4",
            "Host":"127.0.0.1:18790",
        })
        response=conn.getresponse()
        if response.status!=200:
            response.read(min(128,MAX_H264_BYTES))
            raise LiveError("Windows video agent unavailable")
        media=response.getheader("Content-Type","")
        if not media.startswith("video/mp4"):
            raise LiveError("unsupported H264 response")
        return conn,response
    except (OSError,TimeoutError,http.client.HTTPException) as exc:
        conn.close()
        raise LiveError("video tunnel unavailable") from exc
    except Exception:
        conn.close()
        raise
