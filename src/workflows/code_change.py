"""Code Change Workflow — validates, commits, and audits Holly's code changes.

3-node autonomous workflow (no human gate):
  1. validate — governance rules + output validator + risk classification
  2. commit — GitHub Writer MCP: create_branch → commit → create_pr
  3. audit — tower_effects, tower_ticket, memory episode

All code writes funnel through propose_code_change() in Holly's tools, which
creates a Tower run with workflow_id="code_change".
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Governance rules (mirrors docs/CODE_GOVERNANCE.md)
# ---------------------------------------------------------------------------

FORBIDDEN_PATHS = [
    "src/security/",
    "src/tower/",
    "deploy/",
    ".env",
    "Dockerfile",
    ".github/workflows/",
]

PRINCIPAL_ONLY_PATHS = [
    "src/holly/tools.py",
    "src/holly/agent.py",
    "src/holly/prompts.py",
    "src/serve.py",
]

MAX_PROPOSALS_PER_HOUR = 5
MAX_FILES_PER_PROPOSAL = 20
MAX_CONTENT_BYTES = 50 * 1024  # 50 KB
FILE_COOLDOWN_SECONDS = 600  # 10 minutes

# In-memory rate limit tracking (reset on restart is acceptable)
_proposal_timestamps: list[float] = []
_file_last_proposed: dict[str, float] = {}


def _is_forbidden(path: str) -> str | None:
    """Return reason if path is forbidden, None if allowed."""
    for fp in FORBIDDEN_PATHS:
        if path.startswith(fp) or path == fp.rstrip("/"):
            return "forbidden_file"
    for pp in PRINCIPAL_ONLY_PATHS:
        if path == pp:
            return "principal_only"
    return None


def _classify_risk(files: list[dict]) -> str:
    """Classify risk level based on file paths."""
    risk = "low"
    for f in files:
        path = f.get("path", "")
        action = f.get("action", "create")
        # Test and doc files are low risk
        if path.startswith("tests/") or path.startswith("docs/"):
            continue
        # New files in known extension dirs are medium
        if action == "create" and (
            path.startswith("src/tools/")
            or path.startswith("src/workflows/")
            or path.startswith("src/mcp/")
        ):
            risk = max(risk, "medium", key=["low", "medium", "high"].index)
        # Modifications to existing src/ files are high
        elif action in ("update", "delete") and path.startswith("src/"):
            risk = "high"
        # Any src/ file creation not in the above categories is medium
        elif path.startswith("src/"):
            risk = max(risk, "medium", key=["low", "medium", "high"].index)
    return risk


def _check_rate_limits(files: list[dict]) -> str | None:
    """Return error reason if any rate limit exceeded, None if OK."""
    now = time.time()

    # Prune old timestamps
    cutoff = now - 3600
    _proposal_timestamps[:] = [t for t in _proposal_timestamps if t > cutoff]

    if len(_proposal_timestamps) >= MAX_PROPOSALS_PER_HOUR:
        return "rate_limit_exceeded"

    if len(files) > MAX_FILES_PER_PROPOSAL:
        return "too_many_files"

    total_bytes = sum(len(f.get("content", "").encode("utf-8")) for f in files)
    if total_bytes > MAX_CONTENT_BYTES:
        return "content_too_large"

    for f in files:
        path = f.get("path", "")
        last = _file_last_proposed.get(path, 0)
        if (now - last) < FILE_COOLDOWN_SECONDS and last > 0:
            return "cooldown_active"

    return None


def _record_proposal(files: list[dict]) -> None:
    """Record this proposal for rate limiting."""
    now = time.time()
    _proposal_timestamps.append(now)
    for f in files:
        _file_last_proposed[f.get("path", "")] = now


def _scan_content(files: list[dict]) -> str | None:
    """Run output validator patterns on file content. Return reason if unsafe."""
    secret_patterns = [
        (r"sk_live_[a-zA-Z0-9]{20,}", "stripe_secret_key"),
        (r"sk_test_[a-zA-Z0-9]{20,}", "stripe_test_key"),
        (r"shpat_[a-f0-9]{32,}", "shopify_token"),
        (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
        (r"sk-[a-zA-Z0-9]{20,}", "openai_api_key"),
        (r"sk-ant-[a-zA-Z0-9\-]{20,}", "anthropic_api_key"),
        (r"xoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{20,}", "slack_bot_token"),
        (r"npm_[a-zA-Z0-9]{36}", "npm_token"),
    ]
    for f in files:
        content = f.get("content", "")
        for pattern, name in secret_patterns:
            if re.search(pattern, content):
                return f"secret_detected:{name}"
    return None


# ---------------------------------------------------------------------------
# Workflow node functions
# ---------------------------------------------------------------------------

def validate_proposal(
    files: list[dict],
    branch_name: str,
    description: str,
) -> dict[str, Any]:
    """Node 1: Validate governance rules, rate limits, and content safety.

    Returns dict with 'valid' bool and details.
    """
    # Check forbidden/principal-only paths
    for f in files:
        reason = _is_forbidden(f.get("path", ""))
        if reason:
            return {
                "valid": False,
                "reason": reason,
                "path": f["path"],
            }

    # Check rate limits
    rate_reason = _check_rate_limits(files)
    if rate_reason:
        return {"valid": False, "reason": rate_reason}

    # Scan content for secrets
    scan_reason = _scan_content(files)
    if scan_reason:
        return {"valid": False, "reason": scan_reason}

    # Classify risk
    risk_level = _classify_risk(files)

    # Record this proposal
    _record_proposal(files)

    return {
        "valid": True,
        "risk_level": risk_level,
        "file_count": len(files),
        "branch_name": branch_name,
        "description": description,
    }


def execute_commit(
    files: list[dict],
    branch_name: str,
    message: str,
    risk_level: str,
    create_pr: bool = True,
) -> dict[str, Any]:
    """Node 2: Create branch, commit files, and create PR via GitHub Writer MCP.

    Returns commit SHA, PR number/URL, branch name.
    """
    from src.mcp.manager import get_mcp_manager

    mgr = get_mcp_manager()
    server_id = "github-writer"

    # 1. Create feature branch
    branch_result = mgr.call_tool(server_id, "create_branch", {
        "name": branch_name,
        "base": "master",
    })
    branch_data = json.loads(branch_result) if isinstance(branch_result, str) else branch_result
    if isinstance(branch_data, dict) and branch_data.get("error"):
        return {"error": f"Branch creation failed: {branch_data['error']}"}

    # 2. Commit files
    if len(files) == 1 and files[0].get("action") != "delete":
        # Single file — use create_or_update_file
        f = files[0]
        commit_result = mgr.call_tool(server_id, "create_or_update_file", {
            "path": f["path"],
            "content": f.get("content", ""),
            "message": message,
            "branch": branch_name,
        })
        commit_data = json.loads(commit_result) if isinstance(commit_result, str) else commit_result
        if isinstance(commit_data, dict) and commit_data.get("error"):
            return {"error": f"Commit failed: {commit_data['error']}"}
        commit_sha = commit_data.get("commit_sha", "")
    else:
        # Multiple files — use atomic commit
        commit_result = mgr.call_tool(server_id, "commit_multiple_files", {
            "branch": branch_name,
            "message": message,
            "files": [
                {"path": f["path"], "content": f.get("content", ""), "action": f.get("action", "create")}
                for f in files
            ],
        })
        commit_data = json.loads(commit_result) if isinstance(commit_result, str) else commit_result
        if isinstance(commit_data, dict) and commit_data.get("error"):
            return {"error": f"Commit failed: {commit_data['error']}"}
        commit_sha = commit_data.get("commit_sha", "")

    result = {
        "branch": branch_name,
        "commit_sha": commit_sha,
    }

    # 3. Create PR
    if create_pr:
        labels = []
        if risk_level in ("medium", "high"):
            labels.append("needs-review")
        if risk_level == "high":
            labels.append("high-risk")

        pr_result = mgr.call_tool(server_id, "create_pull_request", {
            "title": message[:70],
            "body": f"## Code Change\n\n{message}\n\n**Risk level**: {risk_level}\n**Files**: {len(files)}\n\n---\n*Proposed by Holly Grace via Tower run*",
            "head": branch_name,
            "base": "master",
            "labels": labels,
        })
        pr_data = json.loads(pr_result) if isinstance(pr_result, str) else pr_result
        if isinstance(pr_data, dict) and not pr_data.get("error"):
            result["pr_number"] = pr_data.get("pr_number", 0)
            result["pr_url"] = pr_data.get("pr_url", "")

    return result


def record_audit(
    run_id: str,
    commit_sha: str,
    pr_number: int | None,
    pr_url: str,
    branch_name: str,
    risk_level: str,
    description: str,
    files: list[dict],
) -> dict[str, Any]:
    """Node 3: Record audit trail — tower_effects, tower_ticket, memory episode."""
    # Record effect (two-phase: prepare → commit)
    try:
        from src.tower.store import prepare_effect, commit_effect
        effect_id = prepare_effect(
            run_id=run_id,
            tool_name="code_change",
            params={
                "commit_sha": commit_sha,
                "pr_number": pr_number,
                "pr_url": pr_url,
                "branch": branch_name,
                "risk_level": risk_level,
                "file_count": len(files),
            },
        )
        commit_effect(effect_id, result={
            "committed": True,
            "commit_sha": commit_sha,
            "pr_url": pr_url,
        })
    except Exception as e:
        logger.warning("Failed to record tower effect: %s", e)

    # Create audit ticket (post-hoc, auto-approved)
    try:
        from src.tower.store import create_ticket, decide_ticket
        file_paths = [f.get("path", "") for f in files]
        ticket_id = create_ticket(
            run_id=run_id,
            ticket_type="code_change",
            risk_level=risk_level,
            proposed_action={"description": description, "files": file_paths},
            context_pack={
                "tldr": description[:200],
                "commit_sha": commit_sha,
                "pr_url": pr_url,
                "branch": branch_name,
                "file_paths": file_paths,
            },
        )
        # Auto-approve
        decide_ticket(ticket_id, "approve", decided_by="holly_grace_auto")
    except Exception as e:
        logger.warning("Failed to create audit ticket: %s", e)

    # Store memory episode
    try:
        from src.holly.memory import store_episode
        store_episode(
            summary=f"Code change: {description[:200]}. "
                    f"Branch: {branch_name}, PR: {pr_url or 'none'}, "
                    f"Risk: {risk_level}, Files: {len(files)}",
            outcome="committed",
        )
    except Exception as e:
        logger.warning("Failed to store memory episode: %s", e)

    return {
        "audited": True,
        "commit_sha": commit_sha,
        "pr_url": pr_url,
        "branch": branch_name,
    }
