# LunexPCControl HTTPS gateway (deployment gate)

Target origin: https://rikagro.ru/lunexpc/; only the existing HTTPS vhost is
eligible. Nginx's existing certificate for rikagro.ru is reused. Never expose
TCP 18880 or the reverse SSH port 23789 on a public interface.

## Deny-by-default staging

The repo's server/nginx-lunexpc.conf is a **404-only** location snippet.
When included inside the existing HTTPS server block it prevents accidental
exposure. On VPS the snippet is installed at
/etc/nginx/snippets/lunexpc.conf; the reference in the active site config
is a single include after devcore.conf. On 2026-11-26 `nginx -t` passed.
A backup of the HTTPS site file was saved at
/etc/nginx/conf.d/game1.conf.lunexpc-backup-20261126.

No nginx reload occurred when the route was staged. Reload only after
review, and while the snippet remains deny-only. Verify prior game routes
still return their original statuses.

## Production activation gates

1. Dedicated unprivileged gateway service with a 0600 registry, approved
   device enrollment and auditable token rotation/revocation.
2. Gateway-side per-client tool policy: screenshot-only by default, deny any
   mouse, keyboard, PowerShell, filesystem, and unknown tool call. Upstream
   ControlStatus may be visible; actual desktop consent is still mandatory.
3. Request and connection rate limits, audit trail without token/body/PNG
   leakage, bounded requests and responses, safe streaming behavior.
4. Test an end-to-end remote screenshot, a bad token, revoked token, offline
   Windows agent and denial of prohibited tools through the actual HTTPS
   proxy. Confirm no external access to the raw TCP ports.
5. Confirm the ChatGPT plugin's HTTPS MCP authentication and advertised
   endpoint work. Merely adding an nginx route is not plugin registration.

Example *not enabled* configuration:
server/nginx-lunexpc-enabled.example.conf.

Important: that example expects the request path under `/lunexpc/` to be
mapped to `/devices/` upstream. Review URI normalization, allowed origins,
OAuth/client authentication needs and API shape before activation. Do not
replace the deny-by-default snippet with the example without passing all
readiness gates above.

## Rollback plan

Remove the single `include /etc/nginx/snippets/lunexpc.conf;` line from
/etc/nginx/conf.d/game1.conf after making a fresh backup, validate via
`nginx -t`, then reload nginx during a permitted maintenance operation.
Existing games and other snippets must remain unchanged.
