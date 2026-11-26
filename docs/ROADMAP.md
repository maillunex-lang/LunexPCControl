# Roadmap

- [ ] PC-01 Audit upstream Windows-MCP, license, transport and screenshot support.
- [ ] PC-02 Build authenticated gateway and device enrollment (prototypes implemented; restricted reverse SSH tunnel validated end-to-end for test HTTP, MCP gateway JSON-RPC sequence and credential separation tested locally; HTTPS gateway not deployed).
- [x] PC-03 Integrate Windows desktop agent and test interactive session behavior (2026-11-26: real screenshot through Windows MCP, SSH tunnel, authenticated VPS gateway and test client; only Screenshot and ControlStatus exposed).
- [ ] PC-04 Add optional protected RDP access.
- [ ] PC-05 Add PowerShell, WSL2 and development workflows.
- [ ] PC-06 Add durable jobs, cancellation and audit logging.
- [ ] PC-07 Add portable installer, configuration template and private ChatGPT plugin packaging.
- [ ] PC-08 Run integration and security tests on disposable environments before release.

## Security requirements
No embedded credentials; per-device authentication; least privilege; explicit approval for destructive operations; revocation and emergency stop; encrypted transport; no public raw desktop or shell endpoint.


## Screenshot Monitor milestone (2026-11-26)

- [x] AES-256-GCM screenshot archive with 64 MiB cap
- [x] Capture authenticated successful MCP Screenshot calls via JSON and SSE
- [x] Private responsive menu, gallery, fullscreen and PNG download
- [x] Configurable retention, clear, last-only or last-50 history
- [x] Auto-refresh every three seconds for new AI screenshots
- [x] Authenticated PNG routes and CSRF-protected settings
- [ ] Fresh real Windows agent + ChatGPT MCP end-to-end screenshot validation
- [ ] Independent continuous live video capture (future opt-in if desired)
- [ ] Durable off-VPS history-key backup and production restore


## Dynamic IP and private Live View portal (2026-11-26)

- [x] Outbound SSH tunnel independent of Windows public IP
- [x] Unlimited bounded-backoff reconnect supervisor in source
- [x] User-session login task setup in source (opt-in)
- [x] Authenticated devices page with online/offline tunnel status
- [x] Optimized on-demand 640/960/1280px JPEG preview, max 1fps
- [x] Capture-only-while-viewing, no idle screen recording
- [x] Browser route validation, strict source bounds and transport tests
- [ ] End-user browser-based secure device enrollment and key rotation
- [ ] Review smoother WebRTC video if needed after measuring bandwidth
- [ ] Standalone ChatGPT HTTPS MCP plugin and owner authorization

## Lunex Connector M01-M02 first delivery (2026-11-26)

- [x] Shared architectural GDD with per-device scope and release gates
- [x] Separate private SQLite registry and 256-bit one-time pairing codes
- [x] Server-verified Ed25519 device presence and replay protection
- [x] Authenticated portal invite, connector list and owner revocation
- [x] Go Windows/Linux presence connector using outbound HTTPS
- [ ] Test two downloaded release binaries on separate fresh client machines
- [ ] Durable, OS-native auto-start and safe signed updates
- [ ] Full per-device command/file/input grants, emergency stop and audit
- [ ] Deploy and verify ChatGPT MCP plugin independently


## Reproducible VPS milestone (2026-11-26)

- [x] Repair nested installer directory creation; include the current
  connector/HTTPS templates in the installed file inventory
- [x] Isolated fresh layout/import/HTTP authorization smoke test
- [x] Encrypted v2 allowlisted state backup, integrity check and offline staging
- [ ] Recover the archive key independently from secure off-VPS storage
- [ ] Transactional activation of staged credentials and databases with rollback
- [ ] Reconfigure Windows SSH host-key pins, TLS and DNS after moving VPS
- [ ] Install and validate on another clean supported Ubuntu VPS
- [ ] Verify full browser video and MCP functionality on that VPS


## Private ChatGPT plugin Alpha 0.1

- [x] Package source: plugin.json, mcp.json and scoped workflow skill
- [x] Dedicated read-only HTTPS gateway route and revocable Bearer-key script
- [x] Static fail-closed tests for endpoint, keys, and plugin metadata
- [x] Deploy exact POST-only Nginx route and verify unauthenticated requests
      are rejected; private MCP initialize returned HTTP 200
- [x] Create a private ChatGPT plugin package with the verified MCP URL
- [ ] Owner must connect the private plugin using its dedicated bearer key
- [ ] Verify screenshot and status from ChatGPT itself
- [ ] Expand to device listing, monitor metrics and explicit input control


## Private ChatGPT plugin Alpha 0.1.1 OAuth

- [x] Protected-resource and authorization-server metadata definitions
- [x] Dynamic client registration limited to known ChatGPT callbacks
- [x] Owner-confirmed authorization-code flow with PKCE S256
- [x] Short-lived resource-scoped bearer token and rotating refresh token
- [x] Revocation, one-time authorization codes and CSRF cookie binding
- [x] Separate read-only MCP bridge with legacy Alpha 0.1 compatibility
- [x] Login, token, callback and malicious-redirect unit tests
- [x] Production OAuth service and HTTPS route deployment verification
- [x] Update private ChatGPT plugin to version 0.1.1
- [ ] Owner sign-in and genuine tool-call verification from ChatGPT
