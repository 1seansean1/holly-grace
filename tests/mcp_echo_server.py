"""A tiny MCP stdio server used for integration tests.

Implements:
- initialize + notifications/initialized
- tools/list (one tool: echo)
- tools/call (echoes back args)
- ping
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _write(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()


def _result(req_id: Any, result: dict[str, Any]) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        if not isinstance(msg, dict):
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications have no id
        if req_id is None:
            continue

        if method == "initialize":
            requested = (params or {}).get("protocolVersion") or "2025-11-25"
            _result(
                req_id,
                {
                    "protocolVersion": requested,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "pytest-mcp-echo", "version": "0.0.0"},
                },
            )
            continue

        if method == "ping":
            _result(req_id, {})
            continue

        if method == "tools/list":
            _result(
                req_id,
                {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo back the provided text payload.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string", "description": "Text to echo"},
                                },
                                "required": ["text"],
                            },
                        }
                    ]
                },
            )
            continue

        if method == "tools/call":
            name = (params or {}).get("name")
            arguments = (params or {}).get("arguments") or {}
            if name != "echo":
                _error(req_id, -32601, f"Unknown tool: {name}")
                continue
            text = ""
            if isinstance(arguments, dict):
                text = str(arguments.get("text", ""))
            _result(
                req_id,
                {"content": [{"type": "text", "text": f"echo:{text}"}]},
            )
            continue

        _error(req_id, -32601, f"Unknown method: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

