# LunexPCControl ChatGPT plugin Alpha 0.1.1

Source for the owner's private read-only ChatGPT plugin. The MCP
endpoint runs on the owner's HTTPS VPS, not on GitHub.

- Only ControlStatus and Screenshot are available in Alpha 0.1.1.
- OAuth 2 authorization code + PKCE S256 with dynamic client registration
  lets the owner sign in through the LunexPCControl portal password.
- The plugin package contains no secrets or credentials.
- OAuth login is performed through https://rikagro.ru/oauth/authorize
  after the owner explicitly chooses to connect.
- Earlier Alpha 0.1 API-key clients remain supported by the gateway.
- Live video is separately available at https://rikagro.ru/portalmcp/live.

Read the owner setup and security information in
docs/CHATGPT-OAUTH.md in the repository. Do not substitute the HTML
portal URL for the MCP endpoint, which remains
https://rikagro.ru/lunexpc-mcp.
