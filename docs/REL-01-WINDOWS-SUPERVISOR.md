# REL-01: Interactive Windows session supervisor

This milestone introduces agent/windows/Agent-Supervisor.ps1.
It is run manually by the owner in the **lunexrdp interactive desktop session**.
`-Mode Check` is read-only and verifies the installed agent, SSH device
identity and pinned known_hosts; `-Mode Run` starts only the vendor Windows
MCP server in strict mode and the existing outbound SSH tunnel.

The agent binds to 127.0.0.1:18789 with Screenshot and ControlStatus tools.
The reverse SSH tunnel may connect only to the fixed VPS using strict pinned
SSH host checking and exposes 127.0.0.1:23789 on VPS, never a public port.
The supervisor probes the local TCP port before opening the tunnel, caps
retry attempts, and stops only processes it launched. No scheduled task,
service, registry autorun, firewall or credential changes are made.

To check it in PowerShell in the right user session, run:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\agent\windows\Agent-Supervisor.ps1 -Mode Check

For an explicitly supervised interactive trial, substitute `-Mode Run`.
Do not run this from a Termalin SSH shell as `maill` Session 0: that is
not the user session with the Windows desktop. No separate Windows
or VPS autostart is enabled by this package.

**Status:** source/tests prepared. Needs on-machine PowerShell parser check,
interactive Windows dry-run and real live tunnel validation before marking
REL-01 done. The current public HTTPS MCP route remains closed.
