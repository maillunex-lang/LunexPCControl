# LunexPCControl Alpha 0.1.1: OAuth login for ChatGPT

The read-only ChatGPT plugin uses the self-hosted OAuth 2 authorization-code
flow with PKCE S256, Dynamic Client Registration and protected-resource
metadata. No third-party paid API or identity provider is required.

## Connecting from an Android phone

1. Open ChatGPT Plugins, add a custom MCP server by URL.
2. Enter https://rikagro.ru/lunexpc-mcp.
3. Select OAuth, leaving advanced endpoint discovery automatic.
4. ChatGPT discovers the public protected-resource and authorization-server
   metadata, registers its client and opens the approval page on
   https://rikagro.ru/oauth/authorize.
5. Check that the browser address begins with https://rikagro.ru/oauth/.
   Enter your existing LunexPCControl portal password only on this page,
   then press "Разрешить просмотр" once.
6. The server displays "Доступ подтверждён" on a no-store page. Press
   "Перейти в ChatGPT" on that page to activate the exact, single-use
   ChatGPT callback. Do not repeat the password form submission.
   The callback link expires after about two minutes; if it expires,
   start a fresh connection in ChatGPT.
7. ChatGPT exchanges the authorization code for an access token. It may
   request renewed authorization if the refresh token expires or the
   service is migrated.

The OAuth page displays the actual ChatGPT callback URI and read-only
scope before approval. Do not enter your password in any ChatGPT message.
Do not disable authentication or publicly share access tokens.

## Published endpoints

- MCP resource: https://rikagro.ru/lunexpc-mcp (POST)
- Protected resource metadata:
  https://rikagro.ru/.well-known/oauth-protected-resource/lunexpc-mcp
- OAuth authorization server metadata:
  https://rikagro.ru/.well-known/oauth-authorization-server
- Dynamic registration: https://rikagro.ru/oauth/register
- Authorization: https://rikagro.ru/oauth/authorize
- Exchange and refresh: https://rikagro.ru/oauth/token
- Revocation: https://rikagro.ru/oauth/revoke

Issuer: https://rikagro.ru
Resource: https://rikagro.ru/lunexpc-mcp
Scope: desktop:read (Screenshot, ControlStatus only)
Code challenge method: S256
RFC 9207: OAuth discovery advertises `authorization_response_iss_parameter_supported: true`;
issued authorization responses include an exact `iss=https://rikagro.ru`.
When issuer identification is advertised, ChatGPT can select its stable
`https://chatgpt.com/connector_platform_oauth_redirect` callback. Previously
registered per-connection callback URLs remain allowlisted and require an exact
match. A reconnect may be needed for ChatGPT to re-read discovery and choose
its preferred callback for a new link.
Public clients: ChatGPT HTTPS callback paths only, exact redirect matching.
Tokens: 1-hour access, 30-day refresh; refresh is single-use and rotates.
Authorization codes: 2 minutes, single-use; owner approval valid 5 minutes.
Passwords: Existing portal's private credential file, not stored in OAuth DB.
The owner must enter the password explicitly on the server's own approval
page; it is checked locally with a bounded five-attempt authorization flow.

OAuth credentials, codes and tokens are held in a separate SQLite database
as SHA-256 digests. The authorization handoff page contains the short-lived
callback URL only after a successful owner-password check; it is not
cached and is not logged. The initial POST returns HTML rather than an
empty cross-site HTTP 303, so embedded browsers expose a visible link.
The original Secure/HttpOnly/SameSite cookie stays in the browser until
its normal expiry to recognize a repeated POST without issuing another
authorization code. A nonce-protected script disables the submit button
after the first click. The dedicated bridge credential remains in a private
0600 file, accessible only to the lunexpc-gateway system user.
The legacy Alpha 0.1 API-key plugin remains compatible through the new bridge
for clients already configured using the original Bearer key.

### Modern MCP interoperability (2026-07-28)

ChatGPT's current MCP client may initiate the connection using
server/discover instead of a legacy initialize handshake. The
read-only bridge passes Mcp-Protocol-Version, Mcp-Method, and
Mcp-Name to the private gateway and validates modern header values
against the JSON-RPC request. The gateway permits server/discover as a
metadata-only request, validates the upstream discovery response, and
publishes only its supported 2026 protocol version plus the tools
capability. It strips prompts, resources, untrusted instructions and
unapproved Windows capabilities. tools/list still exposes exactly
Screenshot and ControlStatus; tools/call remains fail-closed for
all other methods and for nonempty arguments. The private gateway's
audit log uses fixed categories and does not record credentials or
client-supplied payloads. Legacy initialize and token handling remain
available for backwards compatibility.

A real ChatGPT refresh and tool invocation is required to verify the
production OpenAI client after deployment. Synthetic protocol and
OAuth tests do not prove the hosted application has refreshed yet.

### Important security boundaries

- No OAuth token grants mouse, keyboard, shell, file management or privilege.
- Even a successfully authenticated request passes through the existing
  fail-closed Windows MCP gateway and its two-tool allowlist.
- The Windows interactive session must be active and accessible for screenshots.
- HTTPS terminates at existing Nginx; the OAuth service is loopback-only.
- Registration is restricted to known ChatGPT callback URI shapes, not
  arbitrary client-provided hosts. The owner sees the callback before approval.
- Authorization-code requests require an exact resource and S256 challenge.
- Access tokens are checked for the intended resource and expiry.
- Nginx and application rate limits protect the public entry points.
- The old /lunexpc and /lunexpc/ endpoints remain closed.

### Data preservation and portability

Tracked source files:
server/oauth_store.py, server/oauth_http.py,
deploy/lunexpc-oauth.service, deploy/nginx-lunexpc-oauth.conf,
deploy/nginx-lunexpc-chatgpt-alpha.conf, chatgpt-plugin/.

Private state directory: /var/lib/lunexpc-gateway/oauth/.
The encrypted v2 state migration includes the OAuth database and bridge key
when present. Private files must never be committed to GitHub.

On a fresh VPS, prepare a private OAuth directory and provision the
dedicated gateway client identity as the unprivileged service user.
Provisioning never prints the token and refuses to overwrite existing
identities:

    sudo install -d -o lunexpc-gateway -g lunexpc-gateway -m 0700 /var/lib/lunexpc-gateway/oauth
    sudo runuser -u lunexpc-gateway -- /usr/bin/python3 -B -m installer.oauth_setup provision
    sudo runuser -u lunexpc-gateway -- /usr/bin/python3 -B -m installer.oauth_setup status

The separate oauth/issuer.sqlite database will be created as mode 0600
when the OAuth service first starts. Install its reviewed systemd unit
and add the OAuth Nginx snippet only to the intended HTTPS host.
Never edit the Windows SSH tunnel credentials as part of OAuth setup.

Revoking access in the OAuth issuer /oauth/revoke invalidates the affected
token. Removing the lunexpc-oauth.service or blocking the new Nginx routes
disables future OAuth logins without disabling the old private gateway.
Full owner-driven "disconnect all clients" UI is a later milestone.

## Operational verification

The expected automated tests cover metadata, DCR, redirection restrictions,
owner consent, CSRF, wrong-password lockout, PKCE S256, code replay,
access and refresh expiry, token rotation and revocation, and MCP bridging.
The final release still requires the owner to complete an actual browser
login and verify a Windows ControlStatus tool call from inside ChatGPT.


## Production verification (2026-11-26)

- OAuth bridge runs under the existing unprivileged lunexpc-gateway user.
- The service listens only on 127.0.0.1:18882 and keeps its OAuth
  issuer DB and internal gateway credential in 0600 files.
- Public HTTPS discovery returned valid issuer, resource and S256 metadata.
- Public DCR registration returned 201 and the owner login page returned 200.
- Malicious redirect URI registration and bogus token exchanges returned 400.
- Unauthenticated MCP requests returned 401 with a resource-metadata challenge.
- The legacy /lunexpc route remains 404; portal access still requires Basic.
- The neighboring DevCore protected-resource OAuth metadata is unchanged.
- The real owner login and a tool call from ChatGPT still require the owner
  to complete the connection UI; no owner password was read for public tests.


## Deployment source and restart

The checked-in main HTTPS include dispatcher is deploy/nginx-lunexpc.conf;
its public subroutes are defined by deploy/nginx-lunexpc-chatgpt-alpha.conf
and deploy/nginx-lunexpc-oauth.conf. The raw /lunexpc gateway remains closed.
Install only in the correct HTTPS virtual host, then run nginx -t before
reloading Nginx. The optional lunexpc-oauth.service is enabled for reboot
persistence only after successful local and public checks.

The existing private plugin was updated in-place to version 0.1.1,
preserving its URL, account scope and read-only tools. Manual custom MCP
connections can use the same resource URL and OAuth discovery without
installing an additional plugin.

## Mobile Chrome consent fix (Alpha 0.1.2)

An investigation of two real rejected approvals showed both were refused
before checking the owner's password (zero recorded password-validation
attempts). The earlier build used one transient cookie for all OAuth tabs and
returned raw JSON for authorization failures.

The mobile-compatible revision uses a distinct Secure, HttpOnly, SameSite=Lax
cookie per authorization request, so parallel tabs and repeated ChatGPT
connection attempts cannot overwrite each other's browser state. If a mobile
browser drops a cookie during the app-to-browser transition, the owner may
still approve using the server-side request ID and high-entropy CSRF token,
but only with a verified exact same-origin Origin header and a compatible
Sec-Fetch-Site browser header. A present but wrong cookie is never accepted.
Cross-site origins and invalid CSRF tokens are rejected.

Denied approvals now return a Russian HTML explanation and a link to start a
new connection in ChatGPT. Server logs record only fixed failure categories
such as cookie_mismatch, origin_rejected or password_mismatch. They never
include secrets, user input, IP addresses, OAuth codes or redirects.

As before, a real owner login in Chrome must be tested after deployment.
