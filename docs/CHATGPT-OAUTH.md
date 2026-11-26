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
   then press the explicit "Разрешить просмотр" button.
6. ChatGPT receives a short-lived access token. It may request renewed
   authorization if the refresh token expires or the service is migrated.

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
Public clients: ChatGPT HTTPS callback paths only, exact redirect matching.
Tokens: 1-hour access, 30-day refresh; refresh is single-use and rotates.
Authorization codes: 2 minutes, single-use; owner approval valid 5 minutes.
Passwords: Existing portal's private credential file, not stored in OAuth DB.
The owner must enter the password explicitly on the server's own approval
page; it is checked locally with a bounded five-attempt authorization flow.

OAuth credentials, codes and tokens are held in a separate SQLite database
as SHA-256 digests. The dedicated bridge credential remains in a private
0600 file, accessible only to the lunexpc-gateway system user.
The legacy Alpha 0.1 API-key plugin remains compatible through the new bridge
for clients already configured using the original Bearer key.

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
