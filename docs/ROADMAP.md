# Roadmap

- [ ] PC-01 Audit upstream Windows-MCP, license, transport and screenshot support.
- [ ] PC-02 Build authenticated gateway and device enrollment.
- [ ] PC-03 Integrate Windows desktop agent and test interactive session behavior (local interactive Windows MCP screenshot validated on 2026-11-26; gateway/tunnel end-to-end not yet tested).
- [ ] PC-04 Add optional protected RDP access.
- [ ] PC-05 Add PowerShell, WSL2 and development workflows.
- [ ] PC-06 Add durable jobs, cancellation and audit logging.
- [ ] PC-07 Add portable installer, configuration template and private ChatGPT plugin packaging.
- [ ] PC-08 Run integration and security tests on disposable environments before release.

## Security requirements
No embedded credentials; per-device authentication; least privilege; explicit approval for destructive operations; revocation and emergency stop; encrypted transport; no public raw desktop or shell endpoint.
