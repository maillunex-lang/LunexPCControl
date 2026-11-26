# Lunex PC Control

**Self-hosted Windows control bridge for ChatGPT, with a private Linux VPS
gateway and an outbound SSH tunnel.** The default policy exposes only
read-only desktop Screenshot and ControlStatus.

## What works

- Windows-MCP 0.9.0 under an interactive Windows session with native
  user consent, pinned SSH host key and isolated Python environment.
- A real PNG screenshot was successfully returned through the full path:
  Windows-MCP -> outbound SSH reverse tunnel -> authenticated VPS
  gateway -> MCP client.
- Gateway runs under a dedicated unprivileged systemd account,
  with a private SQLite registry, token validation, tool allowlisting,
  rate limiting, audit logging and log rotation.
- An owner-authenticated HTML portal on 127.0.0.1:18881, with
  read-only status views plus limited pairing and retention controls,
  protected by a private local password file.
- Separate Screen Monitor at /monitor with encrypted history, fullscreen
  preview, live 3-second polling of AI screenshots, controls for retention
  and clearing, and an action timeline. Capture is disabled by default.
- Authenticated device portal at /devices with outbound-tunnel online status,
  and optimized owner-initiated JPEG Live View at /live (640/960/1280 px,
  1 fps maximum). Capture stops when the owner closes the viewer.
- Interactive Windows supervisor supports unlimited reconnection after a
  change of Wi-Fi, router or ISP address, and an opt-in current-user login
  task without privileged Windows services or inbound firewall ports.
- Complete first-party source, Windows scripts, tests, installer,
  deployment templates and the unmodified MIT-licensed Windows-MCP
  upstream source are preserved in this repository.

**Current stage: prototype.** The public HTTPS MCP route is intentionally
closed. ChatGPT plugin login, unattended Windows lifecycle, production
backup/upgrade and external security review are not complete.

## Lunex Connector alpha

The new self-hosted device enrollment design includes a Go connector
for Windows and Linux, one-time 10-minute pairing in the portal,
Ed25519-signed presence heartbeats and owner revocation. Enrollment
provides **online presence only** and does not grant desktop, files,
shell or ChatGPT MCP tool permissions. See [GDD](docs/GDD-LUNEX-CONNECTOR-v0.1.md)
and [quickstart](docs/CONNECTOR-QUICKSTART.md).

## Portable VPS install

A single bootstrap command can install a NEW Ubuntu 24.04/26.04 VPS from
a full immutable Git commit. Substitute a reviewed full commit SHA:

    curl -fsSL https://raw.githubusercontent.com/maillunex-lang/LunexPCControl/main/installer/bootstrap.sh | sudo bash -s -- --ref FULL_COMMIT_SHA --apply

For an initial inspection, leave off the --apply flag. No existing
deployment is overwritten. The installer does not touch nginx,
firewall, sshd or other applications and does not automatically start,
enable or publicly expose either service.

A new installation generates the panel password into a private file
without printing it to logs or committing it to GitHub. Read it only in
your own private VPS shell. Use the browser login username admin through
an authenticated SSH or private Termalin tunnel, never an unencrypted
public connection.

After review, you may start the gateway and optional dashboard manually:

    sudo systemctl start lunexpc-gateway.service
    sudo systemctl start lunexpc-panel.service

See [portable installation guide](docs/PORTABLE-INSTALL.md) and
[gateway operations](docs/GATEWAY-OPS.md) for limits, audit and rollback.
The installer has NOT yet been exercised on a second clean VPS.

## Source and third-party software

The complete MIT-licensed CursorTouch/Windows-MCP source snapshot is
preserved under vendor/windows-mcp at commit
3333dbdac75ea3cae2a1eea00dccb207db9c5e4d,
along with its original LICENSE.md and a SHA-256 file manifest.
The Windows bootstrap uses the bundled copy when run from a full checkout.
Package dependencies still require pip downloads; offline wheel caching
is a planned release feature.

The project also includes a bounded AES-256-GCM backup tool and immutable
checksum-verified update staging. Automated restore, deployment activation
with rollback, and a full one-click upgrade remain under development.

## Private device portal and optimized Live View

The device portal monitors reverse SSH connection status without requiring
a static Windows IP. The Live View page captures compressed frames only while
the owner explicitly watches, without recording continuous screen video.
See docs/PORTAL-LIVE-VIEW.md for settings, security and limitations.

## Screenshot monitoring

Open the private dashboard, choose Screen Monitor, and enable retention.
Images appear when an authenticated AI calls the approved Screenshot
tool through the gateway. There is no independent continuous video capture.
See the screen monitoring documentation in docs/SCREEN-MONITOR.md.

## Roadmap

See [roadmap](docs/ROADMAP.md), [end-to-end verification](docs/E2E-VALIDATION.md)
and [HTTPS security gates](docs/HTTPS.md).
