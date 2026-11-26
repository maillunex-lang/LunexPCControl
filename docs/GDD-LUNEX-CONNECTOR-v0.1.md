# Lunex Control: Connector and ChatGPT MCP architecture (GDD v0.1)

Date: 2026-11-26. Project: LunexPCControl, public source on GitHub.
Target: Android-friendly portal at https://rikagro.ru/portalmcp/
with independently paired Windows PCs and Ubuntu/Linux servers.

## Product goal

The owner can enroll multiple computers and VPS instances without
static client IPs or inbound firewall ports. Each computer initiates
TLS connections to the VPS. The portal lists identities and actual
recent connectivity, offers a one-time pairing flow, controls permitted
actions, and eventually lets ChatGPT operate selected desktops while
the owner watches the live video and can interrupt it.

The existing Windows-MCP screenshot gateway, reverse SSH/H.264 tunnel,
Nginx, encrypted screenshot gallery and running game services are
preserved, not replaced.

## MVP connector enrollment, release v0.3.0-connector-alpha

The owner signs in to the portal using the existing protected account,
selects Windows or Linux and enters a device label. The owner receives
a random 256-bit pairing code, valid for 600 seconds. No raw code is
stored in SQLite, only its SHA-256 digest. The portal displays the
code one time and never inserts it into a URL.

A user downloads the standalone Go connector from the project release
and enters the code locally. The connector generates a fresh Ed25519
keypair. Only the public key and pairing code cross the HTTPS channel.
The server atomically consumes the invitation, allocates a random
device ID, and records the public key, device label and operating
system in a private SQLite database. Client private keys remain in
the user's protected configuration directory.

The agent sends heartbeat messages every 25 seconds through HTTPS;
the request contains the device ID, Unix timestamp, random nonce and
Ed25519 signature. The server rejects reused nonces, malformed keys,
invalid or expired invitations, revoked device identities and timestamps
outside a 90-second window. The UI displays a connector as online only
with a valid recent heartbeat. Errors trigger bounded exponential
retries up to two minutes. No IP address is part of device identity.

The owner can revoke a device in the authenticated portal. Revocation
invalidates future heartbeat signatures and removes the device from
the active list. This does not automatically terminate any previously
established legacy SSH or Windows-MCP tunnel, which has its own
separate credentials. A combined emergency stop for all channels is
a later milestone.

### Security boundaries

- A newly paired connector has permission ONLY for presence heartbeats.
- It cannot execute terminal commands, access files, control the mouse,
  see screenshots or obtain the private MCP upstream token.
- Owner portal invitation/revocation uses existing authentication,
  exact HTTPS Origin and a dedicated action header.
- Public pairing/heartbeat endpoints require a versioned custom header,
  strict JSON size limits, high-entropy enrollment and rate limits.
- SQLite identities, secrets and image history stay outside /var/www
  under private service ownership.
- Only TLS with system-trusted certificates is supported, and connector
  pairing redirects are forbidden.
- Windows signed-in user identity is distinct from system privileges.
  On Linux no root access is required for this phase.
- No paid API, Termalin dependency, public SSH port or 0.0.0.0 listener
  is introduced by the connector.
- GitHub release executables are published separately with SHA-256
  hashes and can be replaced by locally compiled source.

## Roadmap (approved direction, not claims of implementation)

M01: Self-hosted device registry, one-time pairing, signed online status,
safe owner revocation, Windows and Linux Go command-line agents.

M02: Owner-visible connection wizard, download links, signed release
manifest, installer services for Windows and Linux, automatic recovery
after reboot and upgrade/rollback.

M03: Per-device routing, control scopes, permissions and short-lived
leases. All endpoint commands audited. Owner can immediately stop a
control session. No shell/input without a distinct permission grant.

M04: Read-only metrics for CPU, RAM, storage, GPU where supported,
and health alerts, with bounded sampling and no sensitive process logs.

M05: Explicit opt-in command and file access for Windows PowerShell,
WSL2, Linux. Restricted working directories, confirmation for sensitive
operations, durable progress and cancellation. No arbitrary remote
command execution from a mere device enrollment token.

M06: Stable unattended desktop capture subject to active Windows session,
or an explicitly approved Windows service/interactive helper architecture.
RDP session 0 desktop isolation must be respected.

M07: Low-latency WebRTC live video (H.264 hardware acceleration),
authenticated signaling and fallback. Current fragmented MP4/MJPEG
viewer remains until measured Android/browser stability improves.

M08: Browser mouse, keyboard, touchpad and emergency stop through a
separately authorized desktop lease and OS input API, not by granting
unrestricted GUI control to new agents by default.

M09: Public HTTPS MCP Streamable HTTP endpoint + independent auth and
per-user device grant, tool discovery and policy-aware requests.
ChatGPT integration must be tested for actual compatibility before
claiming release.

M10: Shared AI/human desktop view; actions serialized and tagged by
actor, owner can see what AI did, interrupt or take control. Audit and
session recording enabled only with informed owner choice.

M11-M13: Signed autoupdate, cross-VPS restore, external security
assessment, rollback-tested release and optional commercial licensing.

## Success and release gates

New Linux/Windows connector can pair, survive client public IP change,
show online status and revoke. The portal remains password-protected;
no secrets leak into HTML, URLs, stdout, GitHub or logs. Screenshots
stay encrypted on the VPS. Existing Windows-MCP and game services
remain unchanged. Production shell/mouse access and the ChatGPT
plugin remain explicitly pending until separately deployed and tested.
