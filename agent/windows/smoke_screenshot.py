"""Validate the local read-only Windows-MCP screenshot tool.

No screenshot bytes or authentication tokens are persisted or printed.
Must execute inside the intended interactive Windows user's session.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import os
import sys
from urllib.parse import urlsplit

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.path != "/mcp" or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port is None):
        raise ValueError("only http://127.0.0.1:<port>/mcp is permitted")
    if parsed.port < 1024 or parsed.port > 65535:
        raise ValueError("invalid local port")
    return endpoint


def summarize_screenshot(result) -> dict[str, int]:
    if bool(getattr(result, "isError", False)):
        raise ValueError("Screenshot tool returned an MCP error")
    images = [part for part in getattr(result, "content", [])
              if getattr(part, "type", None) == "image"]
    if not images:
        raise ValueError("MCP Screenshot returned no image blocks")
    total = 0
    for image in images:
        try:
            raw = base64.b64decode(image.data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Screenshot image is not valid base64") from exc
        if not raw.startswith(PNG_SIGNATURE):
            raise ValueError("Expected PNG screenshot content")
        total += len(raw)
    return {"images": len(images), "bytes": total}


async def smoke(endpoint: str) -> None:
    # Import only during live execution; pure validators work without dependencies.
    from fastmcp import Client

    token = os.getenv("LUNEXPC_CLIENT_TOKEN") or os.getenv("WINDOWS_MCP_AUTH_KEY", "")
    if len(token) < 24:
        raise RuntimeError("MCP client authentication token is missing or too short")
    print("MCP stage: connect", flush=True)
    async with Client(endpoint, auth=token, timeout=30) as client:
        print("MCP stage: list_tools", flush=True)
        tools = await client.list_tools()
        names = {item.name for item in tools}
        print(f"MCP tool count={len(names)}; screenshot_present={'Screenshot' in names}", flush=True)
        if names != {"Screenshot", "ControlStatus"}:
            raise RuntimeError("Unsafe MCP tool set enabled; expected Screenshot and ControlStatus only")
        print("MCP stage: call_screenshot", flush=True)
        result = await client.call_tool("Screenshot", {})
        print(f"MCP result block types={','.join(sorted({str(getattr(x, 'type', 'unknown')) for x in getattr(result, 'content', [])}))}", flush=True)
        summary = summarize_screenshot(result)
        # Only a numeric summary. Do not print or save base64/PNG data.
        print(f"MCP screenshot OK; images={summary['images']}; bytes={summary['bytes']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18789/mcp")
    parser.add_argument("--check", action="store_true",
                        help="validate dependencies and endpoint without connecting")
    args = parser.parse_args()
    endpoint = validate_endpoint(args.endpoint)
    if args.check:
        from importlib.metadata import version
        print(f"Local MCP smoke ready; fastmcp={version('fastmcp')}; endpoint={endpoint}")
        return 0
    try:
        asyncio.run(smoke(endpoint))
    except (Exception, KeyboardInterrupt) as exc:
        print(f"MCP screenshot check failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
