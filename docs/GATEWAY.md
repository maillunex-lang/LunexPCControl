# Gateway prototype and limitations

`python3 -m server.gateway --registry /private/path/registry.sqlite --port 18880`
binds to **127.0.0.1 only**. It must NOT be publicly exposed as HTTP.
An external TLS reverse proxy must authenticate requests too, disable buffering
for streaming, and restrict request size/timeouts. No reverse proxy is deployed yet.

GatewayRegistry.configure_route(device, port, upstream_key) creates an explicit
device-to-local-port mapping for ports 20000–29999. Windows connects over a
restricted reverse SSH tunnel (see TUNNEL.md); upstream credentials are
separate from public client credentials. GatewayRegistry.create_client(device)
issues an opaque secret shown once. Never log credentials. Protect the SQLite
database: it contains **plaintext upstream keys**, despite client token hashing.

Route: `/devices/<device>/mcp` -> `http://127.0.0.1:<assigned_port>/mcp`.
Only GET, POST and DELETE route to MCP. Non-stream responses are bounded to 16 MiB
and request bodies to 4 MiB. Authentication precedes proxying, redirect
responses are denied, and headers are allowlisted.

**Known blockers (not production ready):**
- SSE responses now flush each received upstream chunk immediately without
  buffering full events; the upstream socket currently has a 20-second inactivity
  timeout and sustained multi-minute SSE sessions have not been load-tested. The downstream
  TLS reverse proxy must disable response buffering and allow long-lived requests.
- HTTP request body framing has not been fuzzed against request smuggling.
- Device enrollment must bind a tunnel port and per-device server-side secrets
  with a protected provisioning path. The generic Registry in enrollment.py
  is a separate prototype and is not yet wired into this gateway.
- Missing gateway-side per-user tool policy/consent enforcement, rate limits,
  audit events, durable jobs, TLS proxy configuration and production lifecycle management.
- Upstream bearer authentication and the MCP endpoint were verified live.
  A production deployment still requires a dedicated security review.

## Verified local integration (2026-11-26)

The gateway test suite now covers a full MCP JSON-RPC sequence through the
authenticated loopback gateway: `initialize`, `tools/list`, and
`tools/call` carrying an image content block. It also verifies distinct
gateway client and upstream Windows credentials, revoked device access,
rejection of duplicate Authorization and Content-Length headers, restricted
SQLite registry permissions and symlink rejection.

These automated tests use an in-process MCP simulator. A separate real end-to-end
MCP screenshot test subsequently passed on 2026-11-26; see E2E-VALIDATION.md.
HTTPS and ChatGPT plugin connectivity remain pending.
Do not publish port 18880 as plain HTTP.
