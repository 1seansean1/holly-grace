"""Deploy Workflow — Holly self-deploys via GitHub Actions + ECS.

4-node workflow:
  1. pre_check — verify no active runs, service stable, record current revision
  2. build_and_push — trigger GitHub Actions, poll for completion
  3. deploy — register task def, update ECS service, wait stable
  4. verify — health check, CloudWatch errors, record in tower_effects

Triggered by Holly's deploy_self() tool.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# ECS / ECR configuration
_CLUSTER = os.environ.get("ECS_CLUSTER", "holly-grace-cluster")
_SERVICE = os.environ.get("ECS_SERVICE", "holly-grace")
_TASK_FAMILY = os.environ.get("ECS_TASK_FAMILY", "holly-grace-holly-grace")
_ECR_REPO = os.environ.get("ECR_REPO", "327416545926.dkr.ecr.us-east-2.amazonaws.com/holly-grace/holly-grace")
_REGION = os.environ.get("AWS_REGION", "us-east-2")
_GH_OWNER = os.environ.get("GITHUB_OWNER", "1seansean1")
_GH_REPO = os.environ.get("GITHUB_REPO", "ecom-agents")

# Deploy state — prevents concurrent deploys
_deploy_in_progress = False


def pre_check() -> dict[str, Any]:
    """Node 1: Verify it's safe to deploy.

    Checks:
    - No other deploy in progress
    - No active Tower runs (optional: warn but don't block)
    - Record current task def revision for rollback
    """
    global _deploy_in_progress

    if _deploy_in_progress:
        return {"ok": False, "reason": "deploy_in_progress"}

    # Check for active Tower runs
    try:
        from src.tower.store import list_runs
        running = list_runs(status="running", limit=10)
        if running:
            logger.warning("Deploy pre-check: %d active runs, proceeding with caution", len(running))
    except Exception:
        pass

    # Get current task def revision
    current_revision = None
    try:
        import boto3
        ecs = boto3.client("ecs", region_name=_REGION)
        svc = ecs.describe_services(cluster=_CLUSTER, services=[_SERVICE])
        services = svc.get("services", [])
        if services:
            td_arn = services[0].get("taskDefinition", "")
            current_revision = td_arn.split(":")[-1] if ":" in td_arn else None
    except Exception as e:
        logger.warning("Failed to get current task def revision: %s", e)

    _deploy_in_progress = True

    return {
        "ok": True,
        "current_revision": current_revision,
    }


def build_and_push(image_tag: str) -> dict[str, Any]:
    """Node 2: Trigger GitHub Actions workflow and poll for completion.

    Dispatches the build-and-push workflow via GitHub API, then polls
    until the workflow run completes (or times out after 10 minutes).
    """
    from src.mcp.manager import get_mcp_manager

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"ok": False, "reason": "GITHUB_TOKEN not set"}

    # Trigger workflow_dispatch
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/repos/{_GH_OWNER}/{_GH_REPO}/actions/workflows/build-and-push.yml/dispatches"
    body = json.dumps({
        "ref": "master",
        "inputs": {"image_tag": image_tag},
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "holly-grace-deploy/1.0")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 204):
                return {"ok": False, "reason": f"Dispatch failed: HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"ok": False, "reason": f"Dispatch failed: HTTP {e.code} {detail[:200]}"}
    except Exception as e:
        return {"ok": False, "reason": f"Dispatch failed: {e}"}

    # Poll for workflow run completion (max 10 minutes)
    poll_url = f"https://api.github.com/repos/{_GH_OWNER}/{_GH_REPO}/actions/runs?per_page=1&branch=master"
    deadline = time.time() + 600  # 10 min timeout

    time.sleep(5)  # Give GH Actions time to register the run

    while time.time() < deadline:
        try:
            req = urllib.request.Request(poll_url)
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("Authorization", f"token {token}")
            req.add_header("User-Agent", "holly-grace-deploy/1.0")

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            runs = data.get("workflow_runs", [])
            if runs:
                latest = runs[0]
                status = latest.get("status", "")
                conclusion = latest.get("conclusion", "")

                if status == "completed":
                    if conclusion == "success":
                        return {"ok": True, "image_tag": image_tag}
                    else:
                        return {"ok": False, "reason": f"Build failed: {conclusion}"}
        except Exception:
            pass

        time.sleep(15)

    return {"ok": False, "reason": "build_timeout"}


def deploy_to_ecs(image_tag: str, current_revision: str | None) -> dict[str, Any]:
    """Node 3: Register new task def and update ECS service.

    If deployment fails, auto-rollback to current_revision.
    """
    global _deploy_in_progress

    try:
        import boto3
        ecs = boto3.client("ecs", region_name=_REGION)

        # Get current task definition to clone it
        current_td = ecs.describe_task_definition(taskDefinition=_TASK_FAMILY)
        td = current_td["taskDefinition"]

        # Update image tag in container definitions
        for container in td.get("containerDefinitions", []):
            if "holly-grace" in container.get("name", ""):
                container["image"] = f"{_ECR_REPO}:{image_tag}"

        # Register new task definition
        register_params = {
            "family": _TASK_FAMILY,
            "containerDefinitions": td["containerDefinitions"],
            "taskRoleArn": td.get("taskRoleArn", ""),
            "executionRoleArn": td.get("executionRoleArn", ""),
            "networkMode": td.get("networkMode", "awsvpc"),
            "requiresCompatibilities": td.get("requiresCompatibilities", ["FARGATE"]),
            "cpu": td.get("cpu", "512"),
            "memory": td.get("memory", "2048"),
        }
        # Only include volumes if present
        if td.get("volumes"):
            register_params["volumes"] = td["volumes"]

        new_td = ecs.register_task_definition(**register_params)
        new_revision = str(new_td["taskDefinition"]["revision"])
        new_td_arn = new_td["taskDefinition"]["taskDefinitionArn"]

        # Update service
        ecs.update_service(
            cluster=_CLUSTER,
            service=_SERVICE,
            taskDefinition=new_td_arn,
            forceNewDeployment=True,
            desiredCount=1,
        )

        # Wait for service stable (5 min timeout)
        waiter = ecs.get_waiter("services_stable")
        try:
            waiter.wait(
                cluster=_CLUSTER,
                services=[_SERVICE],
                WaiterConfig={"Delay": 15, "MaxAttempts": 20},
            )
        except Exception as e:
            # Auto-rollback
            logger.error("Deploy failed to stabilize, rolling back: %s", e)
            if current_revision:
                ecs.update_service(
                    cluster=_CLUSTER,
                    service=_SERVICE,
                    taskDefinition=f"{_TASK_FAMILY}:{current_revision}",
                    forceNewDeployment=True,
                    desiredCount=1,
                )
            _deploy_in_progress = False
            return {
                "ok": False,
                "reason": f"Service failed to stabilize: {e}",
                "rolled_back_to": current_revision,
            }

        return {
            "ok": True,
            "new_revision": new_revision,
            "image_tag": image_tag,
        }

    except Exception as e:
        _deploy_in_progress = False
        return {"ok": False, "reason": f"Deploy failed: {e}"}


def verify_deploy(image_tag: str, new_revision: str | None, run_id: str) -> dict[str, Any]:
    """Node 4: Health check and record deployment.

    Verifies /api/health returns 200, records in tower_effects and memory.
    """
    global _deploy_in_progress
    _deploy_in_progress = False

    # Health check
    health_ok = False
    try:
        import urllib.request
        # In production, check the ALB endpoint
        health_url = os.environ.get(
            "HEALTH_CHECK_URL",
            "http://holly-grace-alb-708960690.us-east-2.elb.amazonaws.com/api/health",
        )
        with urllib.request.urlopen(health_url, timeout=10) as resp:
            if resp.status == 200:
                health_ok = True
    except Exception as e:
        logger.warning("Health check failed: %s", e)

    # Record tower effect (two-phase)
    try:
        from src.tower.store import prepare_effect, commit_effect
        effect_id = prepare_effect(
            run_id=run_id,
            tool_name="deploy",
            params={
                "image_tag": image_tag,
                "task_def_revision": new_revision,
                "health_check": "passed" if health_ok else "failed",
            },
        )
        commit_effect(effect_id, result={
            "deployed": True,
            "image_tag": image_tag,
            "revision": new_revision,
            "health": "passed" if health_ok else "failed",
        })
    except Exception as e:
        logger.warning("Failed to record deploy effect: %s", e)

    # Store memory episode
    try:
        from src.holly.memory import store_episode
        outcome = "succeeded" if health_ok else "FAILED (health check)"
        store_episode(
            summary=f"Deployment {outcome}: image={image_tag}, "
                    f"revision={new_revision}, health={'OK' if health_ok else 'FAILED'}",
            outcome=outcome,
        )
    except Exception as e:
        logger.warning("Failed to store deploy episode: %s", e)

    return {
        "deployed": True,
        "image_tag": image_tag,
        "revision": new_revision,
        "health_check": "passed" if health_ok else "failed",
    }
