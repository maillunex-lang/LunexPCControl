# Lunex PC Control

Self-hosted MCP bridge for authorized Windows desktop and development workflows.

Status: planning; no deployable release yet.

## Target architecture
ChatGPT private plugin -> authenticated HTTPS MCP gateway on a Linux VPS -> authenticated outbound tunnel -> Windows desktop agent.

Target: portable single-command VPS installation, separate Windows enrollment, no public RDP or unauthenticated MCP ports. Candidate upstream: CursorTouch/Windows-MCP; license and compatibility must be verified before integration.

See [roadmap](docs/ROADMAP.md).
