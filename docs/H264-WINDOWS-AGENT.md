# H.264 NVENC desktop streaming agent (experimental)

A separate Windows interactive-session video agent lives in
agent/windows/h264_agent.py. It listens only on 127.0.0.1:18790,
does not initiate desktop capture until a valid authorized GET arrives,
and streams fragmented MP4 with H.264 NVENC from FFmpeg. Video bytes are
served in memory over HTTP and are not written to a file.

The local H.264 authorization key is HMAC-SHA-256 of the existing private
Windows MCP upstream credential and a fixed purpose label. It is different
from the original MCP credential. The command line contains only a private
credential *file path*, never the secret value.

Supported profiles:
- data: 854x480 at 10fps, 500kbit/s target
- balanced: 1280x720 at 20fps, 1400kbit/s target
- quality: 1920x1080 at 30fps, 3500kbit/s target

These are encoding **targets**, not measured end-to-end performance.
NVENC on the user's RTX 4060 passed both synthetic and active RDP desktop
transcoding tests. The module still requires a separate authenticated
HTTPS relay and browser MSE client, and must not be marked released
until those have passed real interactive integration checks.

The end-user must install a trusted compatible FFmpeg build separately.
FFmpeg builds can be licensed under GPL-3.0 and are not bundled or copied
into this project's Source Available repository. Document FFmpeg's
individual license obligations if distributing a Windows installer.

No new external port, Windows Firewall rule or VPS SSH authorized-key
restriction has yet been changed by this module. Existing private
Screenshot/ControlStatus MCP tools remain separate.
