# Windows agent bootstrap (PC-03, preparation)

The bootstrap never changes system Python, PATH, SSH configuration or the
Windows firewall. It checks for Python 3.14+, Git and OpenSSH.

On Windows, execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent\windows\Bootstrap.ps1
```

The default mode **only checks prerequisites**. The optional `-Install` switch
clones the MIT-licensed upstream at its audited pinned commit and installs it
into a per-user virtual environment under LocalAppData. Verify upstream
repository and code before running it; no automatic updates are enabled.

Installation may run in a noninteractive session, but starting the desktop agent requires an interactive user session. Starting the agent also requires an explicit `-Start` and a separately
provisioned `WINDOWS_MCP_AUTH_KEY`. The agent binds to 127.0.0.1 only.
Run only in an interactive desktop session after confirming the upstream
desktop-control consent model. Never run with elevated privileges.

There is deliberately **no reverse tunnel, remote HTTPS endpoint or scheduled
task** in this stage. Do not publish the loopback MCP port. Real screenshot,
mouse/keyboard and ChatGPT MCP tests remain pending.

## Windows LUNEX validation, 2026-11-26

The following checks were completed via Termalin on the user's Windows PC:
- Python 3.14.10 installed in user scope without removing Python 3.12.
- Original upstream pinned commit checked out at
  `3333dbdac75ea3cae2a1eea00dccb207db9c5e4d`.
- `Bootstrap.ps1 -Install` finished with exit code 0.
- `windows-mcp --help` and `windows-mcp serve --help` returned successfully.
- Upstream supports streamable HTTP, loopback binding, a bearer key, tool filtering,
  control consent flags and explicit CORS restrictions.
- There is no agent service, scheduled startup or reverse tunnel yet.
- Live desktop tools and screenshot return path are not verified yet.

A local user session is necessary for desktop capture and interaction. The
noninteractive Termalin shell is appropriate for installing dependencies only.
