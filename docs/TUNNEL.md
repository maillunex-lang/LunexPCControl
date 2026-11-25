# Tunnel design

Use OpenSSH reverse forwarding instead of implementing a new transport. Windows initiates an outbound SSH connection to the VPS. Bind the reverse port to VPS loopback only. Use a dedicated non-root account and per-device SSH keys, restrict forwarding to the assigned port, disable shell access, agent forwarding and X11. Pin the VPS host key on Windows. The local Windows-MCP endpoint must require its own bearer credential. Never expose raw RDP or MCP directly to the Internet.

The public HTTPS MCP gateway must authenticate callers independently, enforce device authorization, preserve MCP image results and upstream consent controls. Do not forward arbitrary URLs. Deployment remains blocked until gateway authentication and end-to-end tests are implemented.
