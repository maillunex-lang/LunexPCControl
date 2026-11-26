# Windows agent bootstrap (PC-03, preparation)

The bootstrap never changes system Python, PATH, SSH configuration or the
Windows firewall. It checks for Python 3.14+, Git and OpenSSH.

On a trusted interactive desktop, execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\agent\windows\Bootstrap.ps1
```

The default mode **only checks prerequisites**. The optional `-Install` switch
clones the MIT-licensed upstream at its audited pinned commit and installs it
into a per-user virtual environment under LocalAppData. Verify upstream
repository and code before running it; no automatic updates are enabled.

Starting the agent also requires an explicit `-Start` and a separately
provisioned `WINDOWS_MCP_AUTH_KEY`. The agent binds to 127.0.0.1 only.
Run only in an interactive desktop session after confirming the upstream
desktop-control consent model. Never run with elevated privileges.

There is deliberately **no reverse tunnel, remote HTTPS endpoint or scheduled
task** in this stage. Do not publish the loopback MCP port. Real screenshot,
mouse/keyboard and ChatGPT MCP tests remain pending.
