"""GitHub Writer MCP server — write access to a GitHub repo via REST API.

Stdio MCP server that exposes 7 tools:
- create_branch: Create a new branch from a base ref
- create_or_update_file: Write a single file to a branch
- delete_file: Remove a file from a branch
- commit_multiple_files: Atomic multi-file commit via Git Data API
- create_pull_request: Open a PR
- merge_pull_request: Merge a PR (squash default)
- get_pull_request: Check PR status

Uses urllib.request (stdlib) — no external dependencies.
Runs as: python -m src.mcp.servers.github_writer
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
_TOKEN = os.environ.get("GITHUB_TOKEN", "")

_API_BASE = "https://api.github.com"


def _github_request(
    method: str,
    path: str,
    body: dict | None = None,
    accept: str = "application/vnd.github.v3+json",
) -> Any:
    """Make a request to GitHub REST API."""
    url = f"{_API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "holly-grace-mcp/1.0")
    if body:
        req.add_header("Content-Type", "application/json")
    if _TOKEN:
        req.add_header("Authorization", f"token {_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": detail[:500]}
    except Exception as e:
        return {"error": str(e)}


def _github_get(path: str) -> Any:
    return _github_request("GET", path)


def _github_post(path: str, body: dict) -> Any:
    return _github_request("POST", path, body)


def _github_put(path: str, body: dict) -> Any:
    return _github_request("PUT", path, body)


def _github_delete(path: str, body: dict) -> Any:
    return _github_request("DELETE", path, body)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _create_branch(args: dict) -> str:
    """Create a new branch from a base ref."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    name = args.get("name", "")
    base = args.get("base", "master")

    if not name:
        return json.dumps({"error": "name is required"})

    # Get SHA of base branch
    base_data = _github_get(f"/repos/{owner}/{repo}/git/ref/heads/{base}")
    if isinstance(base_data, dict) and base_data.get("error"):
        return json.dumps({"error": f"Cannot find base branch '{base}': {base_data['error']}"})

    base_sha = base_data.get("object", {}).get("sha", "")
    if not base_sha:
        return json.dumps({"error": f"Cannot find SHA for base branch '{base}'"})

    # Create the new ref
    result = _github_post(f"/repos/{owner}/{repo}/git/refs", {
        "ref": f"refs/heads/{name}",
        "sha": base_sha,
    })

    if isinstance(result, dict) and result.get("error"):
        return json.dumps(result)

    return json.dumps({
        "created": True,
        "branch": name,
        "base": base,
        "sha": base_sha,
    })


def _create_or_update_file(args: dict) -> str:
    """Create or update a single file on a branch."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    path = args.get("path", "")
    content = args.get("content", "")
    message = args.get("message", f"Update {path}")
    branch = args.get("branch", "")
    sha = args.get("sha")  # Required for updates, not for creates

    if not path:
        return json.dumps({"error": "path is required"})
    if not branch:
        return json.dumps({"error": "branch is required"})

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    body: dict[str, Any] = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    result = _github_put(f"/repos/{owner}/{repo}/contents/{path}", body)

    if isinstance(result, dict) and result.get("error"):
        return json.dumps(result)

    commit_sha = result.get("commit", {}).get("sha", "")
    return json.dumps({
        "path": path,
        "branch": branch,
        "commit_sha": commit_sha,
        "action": "updated" if sha else "created",
    })


def _delete_file(args: dict) -> str:
    """Delete a file from a branch."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    path = args.get("path", "")
    message = args.get("message", f"Delete {path}")
    branch = args.get("branch", "")
    sha = args.get("sha", "")

    if not path:
        return json.dumps({"error": "path is required"})
    if not branch:
        return json.dumps({"error": "branch is required"})
    if not sha:
        return json.dumps({"error": "sha is required (current file SHA)"})

    result = _github_delete(f"/repos/{owner}/{repo}/contents/{path}", {
        "message": message,
        "sha": sha,
        "branch": branch,
    })

    if isinstance(result, dict) and result.get("error"):
        return json.dumps(result)

    commit_sha = result.get("commit", {}).get("sha", "")
    return json.dumps({
        "deleted": True,
        "path": path,
        "branch": branch,
        "commit_sha": commit_sha,
    })


def _commit_multiple_files(args: dict) -> str:
    """Atomic multi-file commit via Git Data API (blobs → tree → commit → ref update)."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    branch = args.get("branch", "")
    message = args.get("message", "Multi-file commit")
    files = args.get("files", [])

    if not branch:
        return json.dumps({"error": "branch is required"})
    if not files:
        return json.dumps({"error": "files list is required"})

    # 1. Get current commit SHA for the branch
    ref_data = _github_get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    if isinstance(ref_data, dict) and ref_data.get("error"):
        return json.dumps({"error": f"Cannot find branch '{branch}': {ref_data['error']}"})

    current_sha = ref_data.get("object", {}).get("sha", "")
    if not current_sha:
        return json.dumps({"error": f"Cannot find SHA for branch '{branch}'"})

    # Get the tree SHA from the current commit
    commit_data = _github_get(f"/repos/{owner}/{repo}/git/commits/{current_sha}")
    if isinstance(commit_data, dict) and commit_data.get("error"):
        return json.dumps(commit_data)
    base_tree_sha = commit_data.get("tree", {}).get("sha", "")

    # 2. Create blobs for each file
    tree_items = []
    for f in files:
        action = f.get("action", "create")
        fpath = f.get("path", "")
        if not fpath:
            continue

        if action == "delete":
            # To delete, we omit the file from the new tree by not including it
            # But the Git Data API tree creation with base_tree merges, so we use
            # sha=None to delete
            tree_items.append({
                "path": fpath,
                "mode": "100644",
                "type": "blob",
                "sha": None,
            })
        else:
            content = f.get("content", "")
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            blob_result = _github_post(f"/repos/{owner}/{repo}/git/blobs", {
                "content": encoded,
                "encoding": "base64",
            })
            if isinstance(blob_result, dict) and blob_result.get("error"):
                return json.dumps({"error": f"Failed to create blob for {fpath}: {blob_result['error']}"})
            blob_sha = blob_result.get("sha", "")
            tree_items.append({
                "path": fpath,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

    # 3. Create tree
    tree_result = _github_post(f"/repos/{owner}/{repo}/git/trees", {
        "base_tree": base_tree_sha,
        "tree": tree_items,
    })
    if isinstance(tree_result, dict) and tree_result.get("error"):
        return json.dumps({"error": f"Failed to create tree: {tree_result['error']}"})
    new_tree_sha = tree_result.get("sha", "")

    # 4. Create commit
    commit_result = _github_post(f"/repos/{owner}/{repo}/git/commits", {
        "message": message,
        "tree": new_tree_sha,
        "parents": [current_sha],
    })
    if isinstance(commit_result, dict) and commit_result.get("error"):
        return json.dumps({"error": f"Failed to create commit: {commit_result['error']}"})
    new_commit_sha = commit_result.get("sha", "")

    # 5. Update branch ref to point to new commit
    ref_result = _github_request("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", {
        "sha": new_commit_sha,
        "force": False,
    })
    if isinstance(ref_result, dict) and ref_result.get("error"):
        return json.dumps({"error": f"Failed to update ref: {ref_result['error']}"})

    return json.dumps({
        "committed": True,
        "branch": branch,
        "commit_sha": new_commit_sha,
        "files_count": len(files),
        "message": message,
    })


def _create_pull_request(args: dict) -> str:
    """Create a pull request."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    title = args.get("title", "")
    body = args.get("body", "")
    head = args.get("head", "")
    base = args.get("base", "master")

    if not title:
        return json.dumps({"error": "title is required"})
    if not head:
        return json.dumps({"error": "head branch is required"})

    result = _github_post(f"/repos/{owner}/{repo}/pulls", {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    })

    if isinstance(result, dict) and result.get("error"):
        return json.dumps(result)

    pr_number = result.get("number", 0)
    pr_url = result.get("html_url", "")

    # Add labels if specified
    labels = args.get("labels", [])
    if labels and pr_number:
        _github_post(f"/repos/{owner}/{repo}/issues/{pr_number}/labels", {
            "labels": labels,
        })

    return json.dumps({
        "created": True,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "head": head,
        "base": base,
    })


def _merge_pull_request(args: dict) -> str:
    """Merge a pull request."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    pr_number = args.get("pr_number", 0)
    merge_method = args.get("merge_method", "squash")

    if not pr_number:
        return json.dumps({"error": "pr_number is required"})

    result = _github_put(f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", {
        "merge_method": merge_method,
    })

    if isinstance(result, dict) and result.get("error"):
        return json.dumps(result)

    return json.dumps({
        "merged": result.get("merged", False),
        "pr_number": pr_number,
        "merge_sha": result.get("sha", ""),
        "message": result.get("message", ""),
    })


def _get_pull_request(args: dict) -> str:
    """Get pull request status and details."""
    owner = args.get("owner", _OWNER)
    repo = args.get("repo", _REPO)
    pr_number = args.get("pr_number", 0)

    if not pr_number:
        return json.dumps({"error": "pr_number is required"})

    result = _github_get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    if isinstance(result, dict) and result.get("error"):
        return json.dumps(result)

    return json.dumps({
        "pr_number": result.get("number", 0),
        "state": result.get("state", ""),
        "title": result.get("title", ""),
        "mergeable": result.get("mergeable"),
        "merged": result.get("merged", False),
        "head_sha": result.get("head", {}).get("sha", ""),
        "html_url": result.get("html_url", ""),
        "labels": [l.get("name", "") for l in result.get("labels", [])],
    })


# ---------------------------------------------------------------------------
# MCP stdio protocol
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "create_branch",
        "description": "Create a new git branch from a base branch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "New branch name (e.g. 'holly/add-tool-xyz')"},
                "base": {"type": "string", "description": "Base branch (default: master)"},
                "owner": {"type": "string", "description": "GitHub owner (default: 1seansean1)"},
                "repo": {"type": "string", "description": "GitHub repo (default: ecom-agents)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_or_update_file",
        "description": "Create or update a single file on a branch. For updates, provide the current file SHA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"},
                "content": {"type": "string", "description": "File content (UTF-8 text)"},
                "message": {"type": "string", "description": "Commit message"},
                "branch": {"type": "string", "description": "Target branch"},
                "sha": {"type": "string", "description": "Current file SHA (required for updates, omit for creates)"},
                "owner": {"type": "string", "description": "GitHub owner"},
                "repo": {"type": "string", "description": "GitHub repo"},
            },
            "required": ["path", "content", "branch"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from a branch. Requires the current file SHA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to delete"},
                "message": {"type": "string", "description": "Commit message"},
                "branch": {"type": "string", "description": "Target branch"},
                "sha": {"type": "string", "description": "Current file SHA"},
                "owner": {"type": "string", "description": "GitHub owner"},
                "repo": {"type": "string", "description": "GitHub repo"},
            },
            "required": ["path", "branch", "sha"],
        },
    },
    {
        "name": "commit_multiple_files",
        "description": "Atomically commit multiple file changes (create, update, delete) in a single commit via the Git Data API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Target branch"},
                "message": {"type": "string", "description": "Commit message"},
                "files": {
                    "type": "array",
                    "description": "List of file operations",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "File content (for create/update)"},
                            "action": {"type": "string", "enum": ["create", "update", "delete"], "description": "Operation type"},
                        },
                        "required": ["path", "action"],
                    },
                },
                "owner": {"type": "string", "description": "GitHub owner"},
                "repo": {"type": "string", "description": "GitHub repo"},
            },
            "required": ["branch", "message", "files"],
        },
    },
    {
        "name": "create_pull_request",
        "description": "Create a pull request from a head branch to a base branch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR description (markdown)"},
                "head": {"type": "string", "description": "Source branch"},
                "base": {"type": "string", "description": "Target branch (default: master)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to add"},
                "owner": {"type": "string", "description": "GitHub owner"},
                "repo": {"type": "string", "description": "GitHub repo"},
            },
            "required": ["title", "head"],
        },
    },
    {
        "name": "merge_pull_request",
        "description": "Merge a pull request. Default merge method is squash.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pr_number": {"type": "integer", "description": "PR number to merge"},
                "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"], "description": "Merge method (default: squash)"},
                "owner": {"type": "string", "description": "GitHub owner"},
                "repo": {"type": "string", "description": "GitHub repo"},
            },
            "required": ["pr_number"],
        },
    },
    {
        "name": "get_pull_request",
        "description": "Get the status and details of a pull request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pr_number": {"type": "integer", "description": "PR number"},
                "owner": {"type": "string", "description": "GitHub owner"},
                "repo": {"type": "string", "description": "GitHub repo"},
            },
            "required": ["pr_number"],
        },
    },
]

_TOOL_DISPATCH = {
    "create_branch": _create_branch,
    "create_or_update_file": _create_or_update_file,
    "delete_file": _delete_file,
    "commit_multiple_files": _commit_multiple_files,
    "create_pull_request": _create_pull_request,
    "merge_pull_request": _merge_pull_request,
    "get_pull_request": _get_pull_request,
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
                "serverInfo": {"name": "github-writer", "version": "1.0.0"},
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
