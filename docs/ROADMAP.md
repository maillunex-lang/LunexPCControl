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
