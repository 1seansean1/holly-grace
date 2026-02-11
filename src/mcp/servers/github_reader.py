"""GitHub Reader MCP server — read-only access to a GitHub repo via REST API.

Stdio MCP server that exposes 5 tools:
- read_file: Read file contents by path
- list_directory: List files in a directory
- search_code: Search code in the repo
- list_branches: List branches
- get_file_tree: Get the full repo tree (names only)

Uses urllib.request (stdlib) — no external dependencies.
Runs as: python -m src.mcp.servers.github_reader
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

# Defaults — configurable via env vars
_OWNER = os.environ.get("GITHUB_OWNER", "1seansean1")
_REPO = os.environ.get("GITHUB_REPO", "ecom-agents")
_BRANCH = os.environ.get("GITHUB_BRANCH", "master")
_TOKEN = os.environ.get("GITHUB_TOKEN", "")

_API_BASE = "https://api.github.com"


def _github_get(path: str, accept: str = "application/vnd.github.v3+json") -> Any:
    """Make a GET request to GitHub REST API."""
    url = f"{_API_BASE}{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "holly-grace-mcp/1.0")
    if _TOKEN:
        req.add_header("Authorization", f"token {_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": body[:500]}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _read_file(args: dict) -> str:
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    path = args.get("path", "")
    branch = args.get("branch", _BRANCH)

    if not path:
        return json.dumps({"error": "path is required"})

    data = _github_get(f"/repos/{owner}/{repo}/contents/{path}?ref={branch}")
    if isinstance(data, dict) and data.get("error"):
        return json.dumps(data)

    if isinstance(data, dict) and data.get("encoding") == "base64":
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        return json.dumps({
            "path": path,
            "size": data.get("size", 0),
            "content": content,
        })

    if isinstance(data, list):
        return json.dumps({"error": f"'{path}' is a directory, not a file. Use list_directory instead."})

    return json.dumps(data, default=str)


def _list_directory(args: dict) -> str:
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    path = args.get("path", "")
    branch = args.get("branch", _BRANCH)

    ref_param = f"?ref={branch}" if branch else ""
    endpoint = f"/repos/{owner}/{repo}/contents/{path}{ref_param}"
    data = _github_get(endpoint)

    if isinstance(data, dict) and data.get("error"):
        return json.dumps(data)

    if isinstance(data, list):
        entries = [{"name": e.get("name", ""), "type": e.get("type", ""), "size": e.get("size", 0)} for e in data]
        return json.dumps({"path": path or "/", "entries": entries, "count": len(entries)})

    return json.dumps({"error": "Unexpected response — path may be a file, not a directory."})


def _search_code(args: dict) -> str:
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    query = args.get("query", "")

    if not query:
        return json.dumps({"error": "query is required"})

    q = urllib.request.quote(f"{query} repo:{owner}/{repo}")
    data = _github_get(f"/search/code?q={q}&per_page=20")

    if isinstance(data, dict) and data.get("error"):
        return json.dumps(data)

    items = data.get("items", []) if isinstance(data, dict) else []
    results = [{"path": i.get("path", ""), "name": i.get("name", "")} for i in items[:20]]
    return json.dumps({"query": query, "total_count": data.get("total_count", 0), "results": results})


def _list_branches(args: dict) -> str:
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)

    data = _github_get(f"/repos/{owner}/{repo}/branches?per_page=30")

    if isinstance(data, dict) and data.get("error"):
        return json.dumps(data)

    if isinstance(data, list):
        branches = [b.get("name", "") for b in data]
        return json.dumps({"branches": branches, "count": len(branches)})

    return json.dumps({"error": "Unexpected response"})


def _get_file_tree(args: dict) -> str:
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    branch = args.get("branch", _BRANCH)

    data = _github_get(f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1")

    if isinstance(data, dict) and data.get("error"):
        return json.dumps(data)

    tree = data.get("tree", []) if isinstance(data, dict) else []
    paths = [{"path": e.get("path", ""), "type": e.get("type", "")} for e in tree if e.get("type") in ("blob", "tree")]
    return json.dumps({"branch": branch, "file_count": len(paths), "tree": paths})


# ---------------------------------------------------------------------------
# MCP stdio protocol
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file from the GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root (e.g. 'src/serve.py')"},
                "owner": {"type": "string", "description": "GitHub owner (default: 1seansean1)"},
                "repo": {"type": "string", "description": "GitHub repo name (default: ecom-agents)"},
                "branch": {"type": "string", "description": "Branch name (default: master)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories in a directory of the GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path relative to repo root (empty string for root)"},
                "owner": {"type": "string", "description": "GitHub owner (default: 1seansean1)"},
                "repo": {"type": "string", "description": "GitHub repo name (default: ecom-agents)"},
                "branch": {"type": "string", "description": "Branch name (default: master)"},
            },
        },
    },
    {
        "name": "search_code",
        "description": "Search for code in the GitHub repository by keyword or pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'def build_graph', 'class TowerWorker')"},
                "owner": {"type": "string", "description": "GitHub owner (default: 1seansean1)"},
                "repo": {"type": "string", "description": "GitHub repo name (default: ecom-agents)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_branches",
        "description": "List all branches in the GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "GitHub owner (default: 1seansean1)"},
                "repo": {"type": "string", "description": "GitHub repo name (default: ecom-agents)"},
            },
        },
    },
    {
        "name": "get_file_tree",
        "description": "Get the full file tree of the GitHub repository (file names and types only).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "GitHub owner (default: 1seansean1)"},
                "repo": {"type": "string", "description": "GitHub repo name (default: ecom-agents)"},
                "branch": {"type": "string", "description": "Branch name (default: master)"},
            },
        },
    },
]

_TOOL_DISPATCH = {
    "read_file": _read_file,
    "list_directory": _list_directory,
    "search_code": _search_code,
    "list_branches": _list_branches,
    "get_file_tree": _get_file_tree,
}


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

        # Notifications (no id) — ignore
        if req_id is None:
            continue

        if method == "initialize":
            requested = (params or {}).get("protocolVersion") or "2025-11-25"
            _result(req_id, {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "github-reader", "version": "1.0.0"},
            })
            continue

        if method == "ping":
            _result(req_id, {})
            continue

        if method == "tools/list":
            _result(req_id, {"tools": _TOOLS})
            continue

        if method == "tools/call":
            name = (params or {}).get("name")
            arguments = (params or {}).get("arguments") or {}
            handler = _TOOL_DISPATCH.get(name)
            if not handler:
                _error(req_id, -32601, f"Unknown tool: {name}")
                continue
            try:
                text = handler(arguments if isinstance(arguments, dict) else {})
            except Exception as e:
                text = json.dumps({"error": str(e)})
            _result(req_id, {"content": [{"type": "text", "text": text}]})
            continue

        _error(req_id, -32601, f"Unknown method: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
