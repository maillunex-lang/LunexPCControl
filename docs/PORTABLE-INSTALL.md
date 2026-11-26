# LunexPCControl: portable self-hosted deployment

## Architecture recommendation

Use a two-stage solution:

1. Immutable one-command VPS bootstrap. It fetches the complete first-party
   source tree from GitHub at a specific full commit SHA, verifies the revision
   and installs the local gateway and dashboard. It works without the panel
   and has a safe read-only plan mode.
2. Optional responsive HTML dashboard. The initial version shows system
   status, device/client counts and sanitized audit events. It runs on
   loopback and contains no actions that could control Windows.

A web-only installer would depend on a running site for disaster recovery.
The terminal bootstrap avoids that dependency. After installation, future
approved UI controls can manage device enrollment and upgrades separately.

## Source completeness

GitHub contains all first-party source code: the gateway, security policy,
Windows-side integration scripts, nginx templates, systemd units, installer,
dashboard, tests and documentation. No passwords, private keys, device tokens,
local SQLite database or customer operating data are checked into source.

The third-party Windows-MCP dependency is pinned to an audited commit
and its complete MIT-licensed source is included in vendor/windows-mcp,
along with the original LICENSE.md and upstream commit marker. The
Windows bootstrap prefers this local source when the complete repo is
present. Python package dependencies still require PyPI or a separately
prepared wheel cache, so this is not yet an offline installer.

## Supported VPS

Ubuntu 24.04 or 26.04, systemd, Python >= 3.11, Git and sudo/root. No paid
API is required. No Docker or special orchestration layer is required.
Non-Ubuntu Linux distributions and Windows Server VPS installations have
not been validated.

## One-command installation

For a reviewed full 40-character Git commit SHA, execute on a CLEAN VPS:

    curl -fsSL https://raw.githubusercontent.com/maillunex-lang/LunexPCControl/main/installer/bootstrap.sh | sudo bash -s -- --ref FULL_COMMIT_SHA --apply

Without --apply the bootstrap only prints the plan. The pinned source SHA
is mandatory, and the script verifies that the checked-out commit matches
the requested full revision.

For security, it is better to download and review the bootstrap script
before running it as root. This command fetches the entrypoint from mutable
main; for production prefer a release-signed immutable bootstrap artifact
in addition to a pinned source revision. No such production release has
yet been published.

The installer refuses existing deployments or conflicting paths. It creates
a non-login service user, private SQLite state and audit log directories,
installs the gateway and read-only panel plus their systemd units and
logrotate, then performs systemd validation. It does NOT automatically
start or enable the services. It does NOT modify nginx, firewall, sshd,
other game units or existing site configuration.

After inspecting the installation, the owner can run:

    sudo systemctl start lunexpc-gateway.service
    sudo systemctl start lunexpc-panel.service
    sudo bash /opt/lunexpc-gateway/deploy/verify-gateway.sh

Autostart, public HTTPS routing, client login and Windows enrollment remain
separate, reviewed operations.

## HTML panel

The prototype dashboard listens only on 127.0.0.1:18881. It allows GET
requests for the page and a sanitized JSON status. POST/PUT/DELETE are
rejected. Device IDs, upstream credentials and client token digests
never appear in its output.

Access with a local SSH forward or a private authenticated Termalin
Internal Site. Never publish it through nginx unauthenticated.
The application validates Host and Origin headers. If a trusted
private reverse proxy preserves its own Host, the one specific hostname
can be configured through the LUNEXPC_PANEL_ALLOWED_HOST environment variable.
Do not use wildcard hosts.

## Backup, upgrade, portability limitations

The fresh installer deliberately refuses existing deployments. A separate
transactional upgrade/rollback command is planned. For migration, backup
the SQLite database and approved device credentials encrypted, separately
from GitHub. No automatically migrating secret-containing state is built yet.
An offline restore and first installation on a second clean VPS still
require end-to-end validation. Do not treat the current prototype as a
finished one-click production appliance.

The CI workflow checks Python tests, shell syntax and accidental tracking
of secret file types on each push to main.
