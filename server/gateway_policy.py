"""Fail-closed MCP tool policy, bounded rate limiting and redacted audit log.

No request contents, URLs, credentials, screenshots or client-originated strings
are sent to the audit log.
"""
from __future__ import annotations

import json
import os
import stat
import threading
import time
from collections import deque
from datetime import datetime, timezone

ALLOWED_TOOLS = frozenset({"Screenshot", "ControlStatus"})
# Never expose untrusted upstream descriptions or schemas to an MCP client.
PUBLIC_TOOL_SCHEMA = {"type": "object", "properties": {},
                      "additionalProperties": False}
PUBLIC_TOOL_DESCRIPTIONS = {
    "Screenshot": "Capture the interactive Windows desktop with user consent (read-only).",
    "ControlStatus": "Report whether Windows desktop control is currently permitted (read-only).",
}
SAFE_METHODS = frozenset({"initialize", "notifications/initialized", "ping",
                          "server/discover", "tools/list", "tools/call"})
EVENT_TYPES = frozenset({"allowed", "blocked", "invalid", "unauthorized",
                         "rate_limited", "upstream_error", "over_capacity"})
METHOD_TYPES = frozenset({"initialize", "discover", "notification", "ping", "list",
                          "call_screenshot", "call_status", "denied", "other"})


class PolicyError(Exception):
    def __init__(self, status, category="denied"):
        super().__init__(category)
        self.status = status
        self.category = category


def _unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate JSON member")
        result[k] = v
    return result


def inspect_request(body):
    """Validate a single JSON-RPC request. Reject all unknown methods/tools."""
    try:
        obj = json.loads(body, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError) as exc:
        raise PolicyError(400, "invalid") from exc
    if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0":
        raise PolicyError(400, "invalid")
    method = obj.get("method")
    if not isinstance(method, str) or method not in SAFE_METHODS:
        raise PolicyError(403)
    if method == "tools/call":
        params = obj.get("params")
        if not isinstance(params, dict):
            raise PolicyError(400, "invalid")
        name = params.get("name")
        if not isinstance(name, str) or name not in ALLOWED_TOOLS:
            raise PolicyError(403)
        arguments = params.get("arguments", {})
        if type(arguments) is not dict or arguments:
            # These two read-only tools need no arguments for this client.
            # Do not allow future argument-based controls without a review.
            raise PolicyError(403)
        return "call_screenshot" if name == "Screenshot" else "call_status"
    if method == "notifications/initialized":
        if "id" in obj:
            raise PolicyError(400, "invalid")
        return "notification"
    if "id" not in obj or type(obj["id"]) not in (int, str):
        raise PolicyError(400, "invalid")
    return {"initialize": "initialize", "server/discover": "discover",
            "ping": "ping", "tools/list": "list"}[method]


def filtered_response(body, method):
    """Show the client only the tools it is allowed to call."""
    if method not in ("list", "initialize", "discover"):
        return body
    try:
        doc = json.loads(body, object_pairs_hook=_unique_pairs)
        result = doc.get("result", {})
        if not isinstance(result, dict):
            raise ValueError("missing MCP result")
        if method == "discover":
            # Modern MCP discovery is upstream-defined. Verify its shape and
            # advertise only the negotiated 2026 version and read-only tools.
            versions = result.get("supportedVersions")
            capabilities = result.get("capabilities")
            if (result.get("resultType") != "complete"
                    or not isinstance(versions, list)
                    or "2026-07-28" not in versions
                    or not isinstance(capabilities, dict)
                    or not isinstance(capabilities.get("tools"), dict)):
                raise ValueError("invalid upstream MCP discovery")
            doc["result"] = {
                "resultType": "complete",
                "supportedVersions": ["2026-07-28"],
                "capabilities": {"tools": {}},
                "_meta": {"io.modelcontextprotocol/serverInfo": {
                    "name": "LunexPCControl", "version": "0.2"}},
                "ttlMs": 300000,
                "cacheScope": "private",
            }
        elif method == "initialize":
            # The gateway supports only tools; do not advertise prompts/resources,
            # unknown extensions or instructions supplied by the upstream.
            if not isinstance(result.get("protocolVersion"), str):
                raise ValueError("invalid negotiated protocol")
            doc["result"] = {
                "protocolVersion": result["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "LunexPCControl",
                    "version": "0.1"
                },
            }
        else:
            tools = result.get("tools")
            if not isinstance(tools, list):
                raise ValueError("missing MCP tool list")
            if any(not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                   for tool in tools):
                raise ValueError("invalid tool entry")
            filtered_tools = [
                {"name": name,
                 "description": PUBLIC_TOOL_DESCRIPTIONS[name],
                 "inputSchema": PUBLIC_TOOL_SCHEMA}
                for name in ("Screenshot", "ControlStatus")
                if any(tool["name"] == name for tool in tools)
            ]
            doc["result"] = {"tools": filtered_tools}
            if result.get("resultType") == "complete":
                doc["result"].update({
                    "resultType": "complete", "ttlMs": 300000,
                    "cacheScope": "private",
                })
        return json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as exc:
        raise PolicyError(502, "upstream_error") from exc


def filtered_sse_event(event, method):
    """Filter a complete SSE event; fail closed if a tools/list event is malformed."""
    if method not in ("list", "initialize", "discover"):
        return event
    # Preserve event metadata but replace JSON data; avoid writing any
    # unfiltered upstream tool descriptions to the downstream connection.
    normalized = event.replace(b"\r\n", b"\n")
    if not normalized.endswith(b"\n\n"):
        raise PolicyError(502, "upstream_error")
    lines = normalized[:-2].split(b"\n")
    data = b"\n".join(line[5:].lstrip(b" ") for line in lines
                      if line.startswith(b"data:"))
    if not data:
        # Empty event or comment heartbeat contains no tool metadata.
        return event
    filtered = filtered_response(data, method)
    metadata = [line for line in lines
                if line and not line.startswith(b"data:")]
    return b"\n".join(metadata + [b"data: " + filtered]) + b"\n\n"


class RateLimiter:
    """Shared in-memory sliding window, bounded number of identities."""
    def __init__(self, limit=120, window=60.0, max_identities=2048, clock=None):
        if limit < 1 or window <= 0 or max_identities < 1:
            raise ValueError("invalid rate limiter configuration")
        self.limit, self.window = limit, window
        self.max_identities = max_identities
        self.clock = clock or time.monotonic
        self._events = {}
        self._lock = threading.Lock()

    def allow(self, identity):
        now = self.clock()
        with self._lock:
            if identity not in self._events and len(self._events) >= self.max_identities:
                # Global fail closed under churn. Expire idle identities first.
                expired = [k for k, q in self._events.items()
                           if not q or now - q[-1] >= self.window]
                for k in expired:
                    del self._events[k]
                if len(self._events) >= self.max_identities:
                    return False
            queue = self._events.setdefault(identity, deque())
            while queue and now - queue[0] >= self.window:
                queue.popleft()
            if len(queue) >= self.limit:
                return False
            queue.append(now)
            return True


class AuditLog:
    """Append-only, private JSONL log with strict field allowlist."""
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                raise PermissionError("audit file must be a private regular file")
        finally:
            os.close(fd)

    def record(self, event, method="other", status=0):
        if event not in EVENT_TYPES or method not in METHOD_TYPES:
            raise ValueError("invalid fixed audit category")
        if type(status) is not int or not 0 <= status <= 599:
            raise ValueError("invalid audit status")
        entry = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event, "method": method, "status": status
        }, separators=(",", ":")).encode() + b"\n"
        with self.lock:
            flags = os.O_WRONLY | os.O_APPEND
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.path, flags)
            try:
                meta = os.fstat(fd)
                if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077:
                    raise PermissionError("audit log permissions changed")
                os.write(fd, entry)
            finally:
                os.close(fd)
