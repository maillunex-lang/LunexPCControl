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
