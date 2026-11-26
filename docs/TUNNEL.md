# Tunnel design

Use OpenSSH reverse forwarding instead of implementing a new transport. Windows initiates an outbound SSH connection to the VPS. Bind the reverse port to VPS loopback only. Use a dedicated non-root account and per-device SSH keys, restrict forwarding to the assigned port, disable shell access, agent forwarding and X11. Pin the VPS host key on Windows. The local Windows-MCP endpoint must require its own bearer credential. Never expose raw RDP or MCP directly to the Internet.

The public HTTPS MCP gateway must authenticate callers independently, enforce device authorization, preserve MCP image results and upstream consent controls. Do not forward arbitrary URLs. Deployment remains blocked until gateway authentication and end-to-end tests are implemented.

## LUNEX interactive Windows transport prototype

The independent Windows identity lives in the interactive account's local
LunexPCControl/ssh folder. The RSA SSH host key is delivered through the
existing trusted Termalin connector and checked against the exact VPS host
fingerprint SHA256:E4XxBUrI/KUjZLkJQA/zodQhr/20if9pZXpZd9ItM6k.
The private Ed25519 device identity never leaves Windows.

The VPS uses an isolated lunexpc-tunnel account with /usr/sbin/nologin,
no usable password, and a single authorized key restricted to
permitlisten="127.0.0.1:23789" plus deliberately unusable
permitopen="127.0.0.1:1". Existing global sshd config remains unchanged.

Run Start-ReverseTunnel.ps1 in the intended Windows desktop account. It
starts SSH in the foreground with password authentication prohibited, exact
host key pinning, one reverse forward, and liveness keepalives. Ctrl+C closes
the tunnel. It does not start Windows-MCP, install a service, expose an
external port or create autostart. If the Windows MCP process is not running
on local 127.0.0.1:18789, SSH can still establish a remote listener but
forwarded requests cannot complete.

After establishing a listener, verify on VPS with
ss -ltn '( sport = :23789 )' and confirm it only binds to 127.0.0.1.
