# ChatGPT LunexPCControl Plugin Alpha 0.1

This is the first private read-only plugin for an existing MCP server
hosted on the owner's VPS. The GitHub repository contains the complete
plugin package at chatgpt-plugin/, but the MCP server runs on Ubuntu and
is not hosted by GitHub.

## Tools actually implemented

- ControlStatus: current state of the Windows interactive control agent.
- Screenshot: current Windows desktop capture, returned as an MCP tool
  response if an interactive desktop session and permission are present.

Continuous video is separately available on the Basic-authenticated portal:
https://rikagro.ru/portalmcp/live. It is not streamed into ChatGPT.

No devices_list, shell, mouse, keyboard, files, telemetry or privileged
administrative tools are claimed as part of Alpha 0.1. The Go device
connector uses separate signed presence registration; a presence-only
device does not automatically gain MCP access.

## Deployment boundaries

The existing private lunexpc-gateway service remains on
127.0.0.1:18880; it checks a per-device bearer token using only its
SHA-256 digest in a private SQLite database and separately authenticates
the Windows MCP agent via the loopback reverse SSH tunnel.

The HTTPS server on rikagro.ru includes the reviewed
deploy/nginx-lunexpc-chatgpt-alpha.conf only inside the intended TLS
virtual host. The exact /lunexpc-mcp POST route is forwarded to
127.0.0.1:18880/devices/lunex/mcp. Other methods and nested routes
are rejected. The old /lunexpc and /lunexpc/ routes remain 404.
The gateway enforces the two read-only tools and rejects unknown tool
calls even from valid clients. Existing games remain independent.

To prepare a dedicated key as the owner on the VPS:

    cd /home/gamedev/LunexPCControl
    sudo /usr/bin/python3 -B -m installer.chatgpt_key provision
    sudo /usr/bin/python3 -B -m installer.chatgpt_key status

The credential is written only to this private file:

    /var/lib/lunexpc-gateway/chatgpt-alpha.key

with mode 0600. The provisioning tool does not print it. In your own
private terminal display the value and copy it directly into the
ChatGPT plugin connection dialog. Never paste it into a chat, upload
it to GitHub, send it to a bot or include it in screenshots. Protect
it like a password.

To rotate or revoke this plugin's credential without affecting
unrelated clients:

    sudo /usr/bin/python3 -B -m installer.chatgpt_key rotate
    sudo /usr/bin/python3 -B -m installer.chatgpt_key revoke

Revocation immediately disables that key. Rotation invalidates the
previous value and requires updating the plugin connection.

The public URL alone grants no access without the dedicated Bearer key.
The HTML portal uses a separate Basic credential and does not share
it with the ChatGPT plugin.

## Deployment verification (2026-11-26)

The alpha plugin package was saved to the owner's account privately and its
manifest and MCP URL were retrieved and verified. GitHub Actions passed all
Python and Go tests. The production Nginx route is live under HTTPS;
anonymous POST returns HTTP 401, invalid Bearer returns HTTP 403 and GET
returns HTTP 403. The private gateway passed a real MCP initialize handshake.
The owner-side plugin key entry and tool calls from ChatGPT remain
unverified until the owner explicitly authorizes the connection.

## Installation in ChatGPT

Install the private plugin through the Plugin Creator link or an
authorized plugin importer. When asked to connect, enter the private
Bearer key using the plugin connection interface. The first tool
call should be ControlStatus. If the Windows interactive desktop is
not active, Screenshot can fail even when the VPS is online.

## Release gate

Source: chatgpt-plugin/.
MCP endpoint: https://rikagro.ru/lunexpc-mcp (POST-only).
Auth: separate, revocable Bearer token.
Read-only scope: ControlStatus and Screenshot.
Remaining: user-side plugin connection/consent test; additional tools,
independent Windows capture service, full fresh-VPS restore.

This is not yet a full replacement for Termalin and does not offer
chat-controlled mouse or keyboard.
