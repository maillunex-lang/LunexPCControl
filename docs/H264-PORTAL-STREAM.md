# LunexPCControl H.264 live portal release

The Windows interactive-session video agent listens on
127.0.0.1:18790 and uses FFmpeg NVENC to encode the desktop into
fragmented MP4. It runs only when the authenticated owner watches.
The private outbound SSH reverse tunnel forwards Windows loopback 18790
to VPS loopback 23790, using a pinned SSH server host key and restricted
SSH authorized_keys permitlisten. No Windows inbound firewall port is opened.

On VPS, the protected panel at /portalmcp/live proxies the video only for
authenticated, same-origin requests bearing an explicit browser-generated
X-LunexPC-Video: active header. The panel derives an HMAC video credential
from its registered device secret and does not expose that secret or the
derived credential in browser HTML, JavaScript or logs. Concurrent streams
are capped, each stream expires and its payload is bounded.

Three target profiles (not independently measured browser FPS):
- data: 480p, 10fps, ~500kbit/s
- balanced: 720p, 20fps, ~1400kbit/s
- quality: 1080p, 30fps, ~3500kbit/s

The browser uses MediaSource to decode fragmented MP4 with H.264 baseline;
if unsupported or unavailable, it falls back to MJPEG, and JPEG snapshots
remain selectable. Streaming bytes are not persisted to disk. The existing
encrypted AI screenshot history stays in /var/lib/lunexpc-gateway/screens.

Operational caveats:
- When the RDP Windows session is disconnected, gdigrab may fail.
- A local Windows video service start and an independent video SSH tunnel
  must be made durable across restarts in a later packaging milestone.
- Pixel-perfect actual Android browser playback must still be verified
  by the owner on the phone. Automated transport tests are not equivalent
  to a device GPU/browser compatibility test.
- Do not expose /lunexpc/ or ports 23790, 18790 directly.
- H.264 codec is provided via separately installed FFmpeg, not vendored.
