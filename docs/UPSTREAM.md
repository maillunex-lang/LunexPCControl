# Upstream audit

CursorTouch/Windows-MCP, inspected commit 3333dbdac75ea3cae2a1eea00dccb207db9c5e4d, MIT, version 0.9.0, Python >=3.14, FastMCP >=3.0.
Source inspection confirms streamable HTTP, bearer authentication, OAuth options, PNG MCP image results and interactive scheduled-task installation. Set ANONYMIZED_TELEMETRY=false. A real interactive Windows-MCP screenshot and a screenshot through the authenticated VPS gateway were validated on 2026-11-26. Direct ChatGPT app connectivity remains unverified. Preserve upstream consent controls and license notices.


## Bundled Windows-MCP source

The exact MIT-licensed upstream commit is preserved in the tracked
vendor/windows-mcp folder, including its LICENSE.md, pyproject.toml, Python
sources, tests, media assets and documentation. Marker file:
vendor/WINDOWS-MCP-COMMIT.txt. The upstream source is not silently modified.
The existing Windows Bootstrap.ps1 uses the bundled package when run from
a complete LunexPCControl repository checkout and falls back to the pinned
remote Git checkout only when run separately without the vendor directory.

Other Python dependencies are still fetched through normal pip package
resolution. This delivers source availability, not a fully offline Windows
binary bundle. Offline package wheel caching and platform-specific lockfiles
remain release tasks. Preserve original MIT attribution in derivative builds.
