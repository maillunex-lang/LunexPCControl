---
name: remote-monitor
description: Use when the user requests a screenshot or current desktop-control status from their own Windows PC through LunexPCControl, or wants to open the owner's browser live-view portal.
---

# LunexPCControl Alpha 0.1

The remote MCP endpoint is hosted by the owner on their VPS and must be
connected using the owner's private bearer key. Never ask the user to paste
the key into a chat message or store it in plugin files. The plugin's
connection screen is the appropriate place to enter the key.

## Available tools (confirmed by the gateway policy)

- ControlStatus: read-only status of whether Windows desktop control is
  permitted by the interactive Windows agent.
- Screenshot: one current screenshot of the interactive Windows desktop.
  The result is a single captured frame, not continuous video.

When the user asks to check the computer, prefer ControlStatus. When
asked to see the screen, call Screenshot and describe only what was
returned. Do not infer that a failed screenshot means the computer is
offline; RDP session state or capture permissions may be the cause.

When asked to view live video, link to the owner's separate authenticated
browser page at https://rikagro.ru/portalmcp/live. Opening the page does
not give the model the continuous video frames.

## Boundaries

This alpha is scoped to the existing authorized Windows device lunex.
The optional Go connector's presence registration is separate; it does
not grant MCP access, and is not equivalent to an interactive desktop.

Mouse clicks, mouse movement, keyboard typing, shell commands, file
access, app launching, device management, and unattended automation are
NOT supported through this plugin version. Do not claim otherwise or
guess hidden tool names. Do not try to bypass the read-only tool policy
or ask for gateway/Windows upstream credentials.

On authentication failures, guide the owner to the account connection
flow and the documentation at
https://github.com/maillunex-lang/LunexPCControl/blob/main/docs/CHATGPT-ALPHA-01.md.
Never provide or reveal credentials in a chat message.
