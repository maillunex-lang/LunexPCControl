# REL-02: restricted input argument validation

The upstream Windows-MCP names and parameters were verified in the
vendored source at vendor/windows-mcp/src/windows_mcp/tools/input.py.
This phase adds a strict argument validation module for the future
interactive control profile. It is **not** activated in the running
gateway. Read-only Screenshot and ControlStatus remain the only exposed
tools until consent, authorization, session lease, emergency-stop,
audit and end-to-end tests are complete.

The candidate input tools are Click, Type, Scroll and Move. Click permits
hover, single/double click; Move permits hover without drag; Scroll is
bounded to ten wheel notches; Type accepts 1-500 characters and does not
press Enter automatically. Coordinates must be integer pairs in a
bounded range. Shell, filesystem, clipboard, registry, shortcut and drag
tools remain prohibited by default.

REL-02 enabling gate:
- Authenticate a registered device and client independently.
- Require an explicit, expiring user consent lease bound to the
  interactive Windows session before forwarding any input.
- Preserve emergency-stop and fail closed when the user disconnects,
  session changes or a permission check fails.
- Present the audited allowlisted schemas to ChatGPT instead of accepting
  arbitrary upstream tool descriptions.
- Validate through live interactive screenshots, actions and audit logs.

The existing live gateway and private HTML panel remain unchanged in
this commit; no OS control is authorized by these pure validators.
