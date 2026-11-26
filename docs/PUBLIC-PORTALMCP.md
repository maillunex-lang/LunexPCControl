# Public HTTPS admin portal on the owner's VPS

LunexPCControl is served at https://rikagro.ru/portalmcp/ . This is
a password-protected administrative interface, not a public desktop stream.
The MCP gateway path /lunexpc/ must continue to return HTTP 404.

## Nginx setup

For the existing HTTPS virtual host server_name rikagro.ru, install
deploy/nginx-portalmcp.conf in the included snippets directory. Define
the shared rate limit zone from deploy/nginx-portalmcp-rate-limit.conf
inside Nginx's outer http context. On this VPS game1.conf already
includes /etc/nginx/snippets/lunexpc.conf; that snippet may include a
separate /etc/nginx/snippets/lunexpc-portal.conf. Preserve unrelated
website and game routes. Run nginx -t before reloading.

Public paths are /portalmcp/, /portalmcp/devices, /portalmcp/live,
 /portalmcp/monitor, and /portalmcp/api/*. Nginx removes the
/portalmcp prefix before forwarding to 127.0.0.1:18881, a private,
unprivileged panel. The panel verifies Host, HTTP Basic credentials,
and exact HTTPS Origin for settings/clear changes. No direct Windows
agent port or MCP gateway port is publicly exposed.

The username is admin. The private existing panel password remains
in /var/lib/lunexpc-gateway/panel-auth.key with file mode 0600.
Never paste this credential into chat or publish it in GitHub.
HTTPS is mandatory; use rate limiting and do not cache private data.
The private Termalin entry remains supported through root paths.

## VPS screenshot retention

Authenticated AI Screenshot calls that traverse the MCP gateway are
saved as AES-256-GCM-encrypted individual image files in
/var/lib/lunexpc-gateway/screens (0700). Key and SQLite metadata remain
private (0600). The encrypted folder is intentionally outside /var/www
and cannot be accessed through Nginx except by authenticated, validated
panel image endpoints.

Initial retention is 7 days, up to 50 images, total decoded image cap
64 MiB. The gallery includes viewer, download, retention settings and
history clear. The gallery is pruned on access or screenshot insertion.
Live View generates optimized JPEG previews only while viewing and
does not automatically write continuous recordings to storage.

Offsite disaster recovery of the independent screenshot encryption key
and images is a future separate workstream. The current registry backup
does not include image history.

## Verification

Check unauthenticated HTTP 401 for all portal routes; authenticated
200 for HTML, devices, gallery and JPG/PNG previews; invalid Host 403;
missing or mismatched Origin 403 for mutations. Confirm old private
Termalin paths still work, /lunexpc/ still returns 404, certificate
valid, other websites unchanged and Nginx config check successful.
