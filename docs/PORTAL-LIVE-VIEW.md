# LunexPCControl: dynamic Windows IP and private Live View

## Dynamic IP and reconnection

Windows creates an outbound SSH tunnel to the trusted VPS. Its local MCP agent listens only on 127.0.0.1:18789, and the VPS tunnel listener remains on 127.0.0.1:23789. The PC needs no publicly routable or static IP, so ordinary Wi-Fi, router, or ISP address changes do not require changing its registered connection route.

Agent-Supervisor.ps1 now supports MaxRetries=0 for unlimited reconnect attempts, with capped exponential backoff and cleanup of its own child processes. This covers lost connections while the Windows desktop user is signed in. Changing the VPS address or host key still requires a separately approved migration.

AutoStart-Interactive.ps1 provides an opt-in current-user Scheduled Task, created only when invoked in an interactive Windows session. The task runs as that ordinary user at sign-in, not as SYSTEM, and never stores the Windows sign-in password. Default mode Check is read-only. Install and Disable are explicit operations.

## Device portal

Private authenticated pages: /devices for registered computer and reverse-tunnel status, /live for live screen viewing, /monitor for encrypted AI screenshot history, and / for overview. Device online status means the outbound reverse SSH tunnel is reachable, not that desktop consent is currently granted.

The browser never receives the private MCP upstream key or Windows SSH identity. The existing Termalin internal site and panel password remain the private entry point. New browser-based device enrollment, credential rotation and revoke are separate pending release gates.

## Optimized Live View

The owner starts capture explicitly from the Live View page. The panel sends a permitted Screenshot MCP call through the authenticated local reverse tunnel, converts the PNG to JPEG in memory and returns it only through a protected same-origin HTTP route.

Three quality profiles: data (640px, JPEG quality 45), balanced (960px, quality 55) and quality (1280px, quality 65). At most one new frame per second per device and one concurrent frame capture, with short-lived in-memory caching. JPEG previews are capped at 650 KiB; source PNGs are bounded and validated. This does not save continuous screen video on disk.

The browser stops requesting frames when the owner presses Stop, leaves the page, or hides the tab. If the agent is disconnected, returns a consent refusal or responds slowly, the panel shows an unavailable state rather than forcing remote control.

This is an economical near-live screenshot viewer, not an H.264/WebRTC video stream. Full-motion streaming would need a separately reviewed Windows-side encoder and explicit capture permission.

## Security and rollout

- No inbound port is opened on the Windows PC and no new public VPS route is enabled.
- Basic authentication, restricted Host and a custom same-origin request header protect live frames.
- Desktop input, shell and file-control tools remain disabled at the MCP gateway.
- The panel now needs Python Pillow in addition to cryptography. Portable installation must verify both are present.
- Source, tests and UI can be updated separately from the live Windows agent. Existing services should only be restarted after unit checks and a rollback copy.
- ChatGPT's own MCP plugin HTTPS/OAuth compatibility still needs final integration testing.
