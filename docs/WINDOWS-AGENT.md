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

## Session identity check (PC-03)

Before attempting live screenshots, run
`agent/windows/SessionPreflight.ps1` under the **same Windows account and
session** that owns the visible desktop. It is read-only and reports the account,
Windows session ID, whether Explorer exists in that session, whether the
agent is installed under that user's `LocalAppData`, and whether the local
port is already in use. Do not copy an agent installation between Windows
profiles or assume an SSH/Termalin shell can capture the RDP user's screen.

The default `Bootstrap.ps1 -Start` now exposes only the `Screenshot` MCP tool,
with strict desktop control policy. Additional input, PowerShell and filesystem
tools will require a separate policy and explicit consent. No autostart.

## Screenshot integration smoke test

Run these commands only in the interactive Windows account whose screen you
intend to inspect, **after** provisioning a strong Windows-MCP bearer secret
securely in that process's environment:

```powershell
# First start the agent in a separate interactive terminal:
.\Bootstrap.ps1 -Start
# Then from the same desktop account, in another terminal:
.\.venv\Scripts\python.exe .\smoke_screenshot.py --check
.\.venv\Scripts\python.exe .\smoke_screenshot.py
```

The script enforces loopback-only transport, verifies the server exports
exactly `Screenshot`, calls that tool, validates PNG image data and reports
only image count and byte size. It does not write the screenshot or reveal the
token. It is not a substitute for user consent and cannot validate a different
Windows session.

**Paths in the example are illustrative:** use the current user's
`LocalAppData\LunexPCControl\.venv` interpreter and the repository's
`agent/windows` scripts.

## Second user on the same Windows machine

The Termalin SSH shell on LUNEX runs as `maill` in Session 0, but the saved
RDP desktop was observed as `lunexrdp` in Session 3. They are distinct
Windows user profiles; the agent installed under `maill` does not capture
`lunexrdp`'s desktop. Do not copy the former user's virtualenv into the
latter profile or try to invoke an interactive screenshot from Session 0.

Run `Prepare-Interactive.ps1` in the RDP user's actual desktop first. It
only inspects account, session, and tool availability. Install Python 3.14
for that user and run the existing audited bootstrap in that account only
after checking the output and deciding to provision it. Starting an agent
requires the interactive user's explicit choice and per-session credentials.

## Interactive user one-command setup (not run automatically)

For a fresh Windows profile, from an interactive PowerShell window in the
verified repository checkout, execute:
```powershell
.\agent\windows\Install-CurrentUser.ps1
```
This is a **read-only** check by default. After reviewing the output, explicitly
run with `-Install` in that same user account to install Python 3.14
using winget (user scope) if missing, then an isolated Windows-MCP environment
in that user's LocalAppData. No service, firewall rule, scheduled task or
remote connection is created. Starting the agent requires separate consent,
a securely provided bearer token and an interactive desktop.

During Termalin RDP validation, the initial Windows Run dialog mangled Latin
input because the RDP keyboard layout was Russian. Changing the layout to ENG
and running the prepared read-only preflight from Explorer resolved it.

## Verified live interactive screenshot (2026-11-26)

The user profile `lunexrdp` and session 3 were confirmed through the
interactive read-only preflight, and Python 3.14.10 plus Windows-MCP 0.9.0
were successfully installed **for that account**, separately from `maill`.
The locally bound agent at 127.0.0.1:18789 used an ephemeral bearer key and
exposed only the upstream tools `Screenshot` and mandatory `ControlStatus`.
The original upstream control-consent interface appeared during the test.

After the control-consent flow, the real FastMCP client completed an MCP
handshake, enumerated precisely those two tools and called Screenshot:
`LOCAL-MCP-SCREENSHOT-CHECK=PASS`, one valid PNG of **559,295 bytes**. Neither
the image nor the token was persisted or printed by the test. The test runner
stopped the temporary agent and restored environment variables.

An independent Termalin check after the run confirmed no listener on port
18789 and no lingering `windows-mcp` process. This is a **local test only**:
no reverse SSH tunnel, production HTTPS gateway, public URL, unattended
startup, or mobile ChatGPT-to-Windows screenshot path was tested.
