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
- A private, responsive, **read-only HTML dashboard** on
  127.0.0.1:18881, with Basic authentication from a private local
  password file; it shows sanitized counts and audit events.
- Complete first-party source, Windows scripts, tests, installer,
  deployment templates and the unmodified MIT-licensed Windows-MCP
  upstream source are preserved in this repository.

**Current stage: prototype.** The public HTTPS MCP route is intentionally
closed. ChatGPT plugin login, unattended Windows lifecycle, production
backup/upgrade and external security review are not complete.

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

## Roadmap

See [roadmap](docs/ROADMAP.md), [end-to-end verification](docs/E2E-VALIDATION.md)
and [HTTPS security gates](docs/HTTPS.md).
