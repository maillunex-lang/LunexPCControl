# LunexPCControl: isolated VPS gateway operations

## Staging deployment, 2026-11-26

The MCP gateway is now staged as the separate systemd service
lunexpc-gateway.service on Lunex VPS. It runs as the dedicated
unprivileged, non-login user lunexpc-gateway. Installed code lives
under /opt/lunexpc-gateway, owned by root, and runs with systemd
sandbox restrictions. Other project directories and services are not
part of this unit.

SQLite registry: /var/lib/lunexpc-gateway/registry.sqlite (0600)
under a private 0700 folder. There are zero device routes and zero
enrolled clients. Log: /var/log/lunexpc-gateway/audit.jsonl (0600)
with a 0700 parent folder. The audit contains only fixed categories,
UTC timestamps and numeric status codes.

The logrotate rule /etc/logrotate.d/lunexpc-gateway rotates the
audit daily, retaining 14 archives, compressing previous logs and
rotating early at 10 MiB. A real forced rotation was tested: the two
previous events were preserved and a new 0600 audit file accepted a
fresh event without restarting the application.

Unit file: /etc/systemd/system/lunexpc-gateway.service. It includes
NoNewPrivileges, ProtectSystem=strict, PrivateTmp, capability
restrictions, 256 MiB memory limit and a process count limit.
Systemd security analyzer rated it 3.8 (OK).

The listener is restricted to 127.0.0.1:18880. Local unauthenticated
requests returned 401, and invalid client credentials returned 403.
The active game path /game1-rtb/ returned 200; the public LunexPC
path /lunexpc/ remains denied with 404.

The unit has been started manually but is NOT enabled for boot.
No Windows device, client token, SSH tunnel or public HTTPS endpoint
has been enabled by this stage.

## Routine read-only verification

- systemctl status lunexpc-gateway.service --no-pager
- systemctl is-enabled lunexpc-gateway.service
- ss -ltn '( sport = :18880 )'
- bash /opt/lunexpc-gateway/deploy/verify-gateway.sh
- journalctl -u lunexpc-gateway.service -p warning --since '-15 min' --no-pager
- logrotate -d /etc/logrotate.d/lunexpc-gateway

The verification script can also be run from the repository checkout.
To stop this isolated gateway, use systemctl stop
lunexpc-gateway.service. Do not change nginx, sshd, firewall
or other application units.

## Production gates still open

Before activating public HTTPS, verify a full TLS MCP session, tool
denials, client OAuth or other ChatGPT-supported authentication,
Windows consent, audit retention, revocation, safe lifecycle and
offline handling. PowerShell, mouse, keyboard and filesystem control
remain outside the current read-only tool policy.
