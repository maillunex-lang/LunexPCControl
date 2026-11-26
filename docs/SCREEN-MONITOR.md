# LunexPCControl: AI screenshot monitoring

## Implemented capabilities

The authenticated private dashboard has a separate Screen Monitor menu
at /monitor with the latest Screenshot, gallery/history, fullscreen view,
PNG downloads, a sanitized MCP action log, and recording controls.
The latest view refreshes every 3 seconds when the AI takes a new Screenshot.
It is not a continuous video feed and never initiates extra screenshot
requests to the Windows agent.

The gateway captures only successful authenticated MCP Screenshot tool calls,
including JSON and complete SSE data responses. Other tools and errors
are excluded. History recording is disabled by default and eligibility is
fixed when each MCP request arrives to prevent retroactive capture.

## Encryption and retention

History lives under /var/lib/lunexpc-gateway/screens, a private 0700 folder.
PNG images are individually encrypted with AES-256-GCM and a random nonce.
A mode-0600 key and private SQLite metadata file are used. No unencrypted
PNG is stored on the server filesystem.

Per-image maximum: 5 MiB. Maximum total plaintext payload: 64 MiB.
Maximum number of screenshots: 50. Allowed retention: disabled, one hour,
24 hours or 7 days. The UI can keep only the latest snapshot or up to 50.
Disabling recording removes the history; an authenticated separate Clear
action removes the history without changing the recording setting.

## Security

All screens and PNG downloads require panel authentication. Saving settings
and clearing images also require matching Origin and a custom action header
to resist cross-origin requests. The panel does not enable any new MCP
commands. Mouse/keyboard/shell calls remain denied by gateway policy.
The audit timeline displays only allowed Screenshot and ControlStatus
events and their non-sensitive HTTP status codes.

All responses use no-store and the monitor remains behind the existing
private Termalin site or an SSH tunnel. Raw screenshots and encryption
keys must never enter a public GitHub repository.

## Limitations

The current production gateway has no enrolled Windows device, and its
reverse SSH tunnel and interactive Windows agent may be offline. Actual
screenshots will appear only after a properly authenticated Windows agent
connects and an authorized AI invokes Screenshot through the gateway.
Automated JSON and SSE integration tests exercise capture and retrieval.
They do not replace a new real Windows end-to-end check.

Live View means near-live refresh of AI-requested screenshots, not an
independent video stream. Continuous capture would need explicit separate
Windows-side opt-in and additional security review.

The current encrypted VPS registry backup does not include screenshot
history or its encryption key. History is intentionally ephemeral, and
the 64 MiB limit protects the VPS from disk exhaustion.
