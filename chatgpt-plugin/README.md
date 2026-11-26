# LunexPCControl ChatGPT plugin Alpha 0.1

Source for the private read-only ChatGPT plugin. This package points to
the real, HTTPS, streamable HTTP MCP endpoint on the owner's VPS.

- The MCP service is not hosted on GitHub.
- The package contains no keys, tokens, screenshots or user data.
- Only ControlStatus and Screenshot are available in Alpha 0.1.
- The connection requires the owner to enter their dedicated private
  bearer key through the ChatGPT plugin connection interface.
- Live video is separately available on the authenticated web portal.
- Read the deployment and enrollment instructions in
  docs/CHATGPT-ALPHA-01.md in the repository.

The plugin package is intentionally small and follows the Agent Plugins
1.0.0 manifest format. Do not substitute the HTML portal URL for the
Streamable HTTP MCP endpoint.
