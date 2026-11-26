"""Bounded, on-demand, private multipart MJPEG over a single HTTP response.

This is not H.264 or WebRTC. It supports existing upstream Windows MCP,
never starts capturing before an authenticated viewer explicitly opens
the stream, and does not persist JPEG frames on the VPS.
"""
from __future__ import annotations

import re
import threading
import time

from panel.live_view import LiveError, PROFILE

MAX_STREAM_SECONDS = 180
MIN_FRAME_SECONDS = 1.1
MAX_STREAM_CLIENTS = 2
MAX_STREAM_BYTES = 50 * 1024 * 1024
BOUNDARY = "lunexpcscreenframe"

class StreamBusy(LiveError):
    pass

class StreamGate:
    """Global, non-blocking client slots; one viewer is already sufficient."""
    def __init__(self, max_clients=MAX_STREAM_CLIENTS):
        self.capacity = threading.BoundedSemaphore(max_clients)

    def acquire(self):
        if not self.capacity.acquire(blocking=False):
            raise StreamBusy("maximum concurrent viewers reached")

    def release(self):
        self.capacity.release()


def stream_frames(viewer, device, profile, *, clock=time.monotonic,
                  sleep=time.sleep, max_seconds=MAX_STREAM_SECONDS,
                  stop=None):
    """Yield individual validated wire parts; never hold a global lock idle."""
    if not isinstance(device, str) or not re.fullmatch("[A-Za-z0-9_-]{1,64}",device):
        raise LiveError("unknown device")
    if profile not in PROFILE:
        raise LiveError("unknown quality")
    if max_seconds <= 0 or max_seconds > MAX_STREAM_SECONDS:
        raise LiveError("invalid stream lifetime")
    start=clock()
    emitted=0
    delivered=0
    consecutive_failures=0
    while clock()-start<max_seconds and delivered<MAX_STREAM_BYTES:
        if stop is not None and stop():
            return
        before=clock()
        try:
            image,etag,new=viewer.frame(device,profile)
            if not image.startswith(bytes.fromhex("ffd8")) or not image.endswith(bytes.fromhex("ffd9")):
                raise LiveError("invalid JPEG preview")
            if len(image)>650*1024:
                raise LiveError("oversize JPEG preview")
            part=(b"--"+BOUNDARY.encode()+b"\r\n"
                  +b"Content-Type: image/jpeg\r\n"
                  +b"Content-Length: "+str(len(image)).encode()+b"\r\n"
                  +b"Cache-Control: no-store\r\n\r\n"
                  +image+b"\r\n")
            delivered+=len(part)
            if delivered>MAX_STREAM_BYTES:
                return
            emitted+=1
            consecutive_failures=0
            yield part
        except LiveError:
            consecutive_failures+=1
            if consecutive_failures>=4:
                return
        remaining=MIN_FRAME_SECONDS-(clock()-before)
        if remaining>0:
            sleep(remaining)


def content_type():
    return "multipart/x-mixed-replace; boundary="+BOUNDARY
