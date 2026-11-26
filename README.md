# Lunex PC Control

Self-hosted MCP bridge for authorized Windows desktop and development workflows.

Status: prototype. Live Windows-MCP screenshot test passed locally in an interactive Windows session; **no deployable remote service or complete HTTPS/tunnel integration yet**.

## Target architecture
ChatGPT private plugin -> authenticated HTTPS MCP gateway on a Linux VPS -> authenticated outbound tunnel -> Windows desktop agent.

Target: portable single-command VPS installation, separate Windows enrollment, no public RDP or unauthenticated MCP ports. Upstream: CursorTouch/Windows-MCP at audited pinned commit. A local screenshot test was performed with the screenshot-only tool and upstream control-consent mechanism. The public gateway, tunnels and end-to-end authorization are not deployed.

See [roadmap](docs/ROADMAP.md).
