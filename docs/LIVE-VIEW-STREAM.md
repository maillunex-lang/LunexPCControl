# Live View 2.0: continuous HTTP MJPEG

This milestone introduces continuous multipart MJPEG streaming using the
existing authenticated Windows Screenshot MCP command and the established
loopback reverse SSH tunnel. One stream uses one HTTPS HTTP response, with
individual JPEG images separated by multipart boundaries. MJPEG is a real
HTTP media stream but it is **not** H.264/WebRTC and currently sends at most
one new frame per second. Do not describe it as 20-30 fps full-motion video.

## UI

Open /portalmcp/live and select "Потоковое видео" for an ongoing stream.
Alternatively choose "Резервный JPEG" for the previous one-request-per-frame
mode. In both cases capture starts only after pressing the Start button,
stops when viewing is stopped or the tab is hidden, and requires an
authenticated private panel session. The MJPEG stream ends automatically
after at most 180 seconds; the viewer reconnects while still active.
No video recording is stored on VPS.

## Security and limits

The remote agent continues to allow only Screenshot and ControlStatus.
No desktop control permission, shell or file access is added. HTTP Basic
credentials are required for the streaming route; a forged or unregistered
device name is rejected. At most two simultaneous streaming viewers share
one limited MCP capture service. Each MJPEG response has a lifetime bound
and a 50 MiB response cap. Frame size is capped at 650 KiB, and only
validated JPEG bytes are transmitted.

Nginx preserves the portal's HTTPS and authentication forwarding. For
multipart streaming the panel sends "X-Accel-Buffering: no"; other portal
routes retain normal buffering. Existing screenshot history remains in
encrypted mode-0600 files under /var/lib/lunexpc-gateway/screens. Streaming
previews are not written to disk or added to that history.

## Full-motion H.264 planned separately

The Windows test machine has an NVIDIA RTX 4060 Laptop GPU but has not yet
been verified to encode H.264 from the actual interactive RDP session.
The current Windows and VPS environments have no preconfigured ffmpeg /
aiortc streaming components. A high-FPS low-latency H.264 WebRTC transport
requires a Windows-side capture/encode agent, authenticated signaling,
congestion/backpressure limits, mobile browser testing, and network routing
through VPS. Until all of those are installed and checked, the stream is
MJPEG and the quality options affect JPEG resolution and compression only.
