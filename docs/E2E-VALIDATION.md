# Real end-to-end MCP validation, 2026-11-26

Result: PASS for the read-only screenshot path.

- Windows host LUNEX, user lunexrdp, interactive RDP session 3. Windows-MCP
  0.9.0 ran on localhost:18789, restricted to Screenshot and the upstream
  mandatory ControlStatus with strict user-consent controls.
- Windows initiated a restricted outbound SSH reverse tunnel to VPS, binding
  its remote port ONLY to 127.0.0.1:23789. Host key was pinned; independent
  device Ed25519 key and dedicated non-shell tunnel account were used.
- VPS gateway listened ONLY on 127.0.0.1:18880 and routed MCP requests to the
  SSH tunnel. The client bearer token differed from the Windows-MCP token.
- A separate device X25519 key decrypted an ephemeral token in the user's
  Windows profile. Neither token was typed into RDP, logged, or committed.
  VPS gateway database and test tokens were stored in a 0700 directory with
  0600 files.
- VPS tests/live_gateway_probe.py verified rejection of an invalid token,
  MCP initialize with assigned session, list of exactly Screenshot and
  ControlStatus, and a real tools/call Screenshot invocation.
- The screenshot returned exactly 1 valid PNG of 582,226 bytes. Image bytes
  were validated in memory but were not saved to disk or printed.
- On cleanup, stopping the foreground PowerShell script and the Termalin
  gateway job left orphaned child processes. These were identified by exact
  command line, session and port and explicitly stopped. The Windows test
  runner was subsequently modified to stop process trees and matching
  children. The improved cleanup code passed all automated tests and the
  real PowerShell 5.1 parser; it has not yet been retested live.
- Final verification showed no listeners on Windows port 18789 or VPS ports
  23789 and 18880. Temporary credentials, SQLite registry and ciphertext
  were removed. Permanent per-user SSH/X25519 keys were retained.

Not yet delivered: public HTTPS endpoint, ChatGPT plugin connection,
unattended agent lifecycle, production audit/rate-limit/tool policy,
mouse or keyboard controls, and sustained SSE load testing. No changes
were made to global SSH configuration, nginx, firewall or live games.

To repeat this test, generate a fresh upstream token sealed to the Windows
device encryption key, install it with Prepare-RemoteMcpSmoke.ps1, launch
Run-RemoteMcpSmoke.ps1 in the desired interactive Windows session, start
a loopback-only gateway with a private registry on VPS, and run
tests/live_gateway_probe.py against it. Afterward always check and stop
all test processes and remove disposable credentials.
