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
Only GET, POST and DELETE route to MCP. Responses are bounded to 16 MiB
and request bodies to 4 MiB. Authentication precedes proxying, redirect
responses are denied, and headers are allowlisted.

**Known blockers (not production ready):**
- Streamable MCP supports long-lived SSE and potentially unbounded streams.
  This stdlib prototype buffers responses, uses a 20-second upstream timeout,
  and cannot support long-lived streaming MCP sessions yet.
- HTTP request body framing has not been fuzzed against request smuggling.
- Device enrollment must bind a tunnel port and per-device server-side secrets
  with a protected provisioning path. The generic Registry in enrollment.py
  is a separate prototype and is not yet wired into this gateway.
- Missing per-user policy/consent enforcement, rate limits, audit events,
  durable jobs, TLS proxy configuration, lifecycle management and live Windows
  screenshot verification.
- Recheck upstream Windows-MCP's bearer format and actual MCP endpoint before
  attempting real end-to-end deployment.
