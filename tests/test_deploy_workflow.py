"""Tests for deploy workflow (src/workflows/deploy.py) and deploy_self tool (src/holly/tools.py).

20 tests across 5 categories:
  - Pre-check (4 tests)
  - Build and push (4 tests)
  - Deploy to ECS (5 tests)
  - Verify deploy (3 tests)
  - deploy_self integration (4 tests)

Key mocking strategy:
  boto3 is not installed in the local venv (it runs on AWS Fargate only).
  We inject a mock boto3 module into sys.modules so the lazy `import boto3`
  inside deploy functions picks up our mock.  urllib.request.urlopen is
  patched at the stdlib level since urllib IS available locally.  Tower store
  and Holly memory functions are patched at their own module paths.
"""

from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import MagicMock, patch


def _make_mock_boto3():
    """Create a mock boto3 module with a .client() that returns a MagicMock."""
    mock_mod = MagicMock()
    return mock_mod


class TestPreCheck(unittest.TestCase):
    """Category 1: pre_check() tests."""

    def setUp(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False
        # Inject mock boto3 into sys.modules
        self._mock_boto3 = _make_mock_boto3()
        self._orig_boto3 = sys.modules.get("boto3")
        sys.modules["boto3"] = self._mock_boto3

    def tearDown(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False
        # Restore original boto3 state
        if self._orig_boto3 is not None:
            sys.modules["boto3"] = self._orig_boto3
        else:
            sys.modules.pop("boto3", None)

    def test_clean_pre_check_passes(self):
        """Pre-check passes when no deploy in progress and ECS is reachable."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {
            "services": [
                {"taskDefinition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace-holly-grace:4"}
            ]
        }

        with patch("src.tower.store.list_runs", return_value=[]):
            from src.workflows.deploy import pre_check
            result = pre_check()

        self.assertTrue(result["ok"])
        self.assertEqual(result["current_revision"], "4")

    def test_concurrent_deploy_blocked(self):
        """Pre-check rejects when another deploy is already in progress."""
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = True

        from src.workflows.deploy import pre_check
        result = pre_check()

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "deploy_in_progress")

    def test_pre_check_with_active_tower_runs_warns_but_passes(self):
        """Pre-check warns about active Tower runs but still succeeds."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {
            "services": [
                {"taskDefinition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace-holly-grace:5"}
            ]
        }

        with patch("src.tower.store.list_runs") as mock_list_runs:
            mock_list_runs.return_value = [
                {"run_id": "run-1", "status": "running"},
                {"run_id": "run-2", "status": "running"},
            ]
            from src.workflows.deploy import pre_check
            result = pre_check()

            mock_list_runs.assert_called_once_with(status="running", limit=10)

        self.assertTrue(result["ok"])

    def test_pre_check_gets_current_revision_from_ecs(self):
        """Pre-check extracts the revision number from ECS task definition ARN."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs
        mock_ecs.describe_services.return_value = {
            "services": [
                {"taskDefinition": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace-holly-grace:16"}
            ]
        }

        with patch("src.tower.store.list_runs", return_value=[]):
            from src.workflows.deploy import pre_check
            result = pre_check()

        self.assertTrue(result["ok"])
        self.assertEqual(result["current_revision"], "16")
        self._mock_boto3.client.assert_called_with("ecs", region_name="us-east-2")


class TestBuildAndPush(unittest.TestCase):
    """Category 2: build_and_push() tests."""

    def setUp(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    @patch("time.time")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"})
    def test_successful_build(self, mock_time, mock_sleep, mock_urlopen):
        """Build succeeds when GitHub Actions run completes with success."""
        mock_time.side_effect = [
            1000.0,   # deadline = 1000 + 600 = 1600
            1001.0,   # while check: 1001 < 1600 -> enter loop
        ]

        # First urlopen call: dispatch (POST) -> returns 204
        dispatch_resp = MagicMock()
        dispatch_resp.status = 204
        dispatch_resp.__enter__ = MagicMock(return_value=dispatch_resp)
        dispatch_resp.__exit__ = MagicMock(return_value=False)

        # Second urlopen call: poll -> returns completed/success
        poll_data = json.dumps({
            "workflow_runs": [{
                "status": "completed",
                "conclusion": "success",
            }]
        }).encode("utf-8")
        poll_resp = MagicMock()
        poll_resp.status = 200
        poll_resp.read.return_value = poll_data
        poll_resp.__enter__ = MagicMock(return_value=poll_resp)
        poll_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [dispatch_resp, poll_resp]

        from src.workflows.deploy import build_and_push
        result = build_and_push("v12")

        self.assertTrue(result["ok"])
        self.assertEqual(result["image_tag"], "v12")

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    @patch("time.time")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"})
    def test_build_failure(self, mock_time, mock_sleep, mock_urlopen):
        """Build fails when GitHub Actions run concludes with failure."""
        mock_time.side_effect = [1000.0, 1001.0]

        dispatch_resp = MagicMock()
        dispatch_resp.status = 204
        dispatch_resp.__enter__ = MagicMock(return_value=dispatch_resp)
        dispatch_resp.__exit__ = MagicMock(return_value=False)

        poll_data = json.dumps({
            "workflow_runs": [{
                "status": "completed",
                "conclusion": "failure",
            }]
        }).encode("utf-8")
        poll_resp = MagicMock()
        poll_resp.status = 200
        poll_resp.read.return_value = poll_data
        poll_resp.__enter__ = MagicMock(return_value=poll_resp)
        poll_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [dispatch_resp, poll_resp]

        from src.workflows.deploy import build_and_push
        result = build_and_push("v12")

        self.assertFalse(result["ok"])
        self.assertIn("failure", result["reason"])

    @patch.dict("os.environ", {"GITHUB_TOKEN": ""}, clear=False)
    def test_no_github_token(self):
        """Build fails immediately when GITHUB_TOKEN is not set."""
        import os
        original = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = ""

        try:
            from src.workflows.deploy import build_and_push
            result = build_and_push("v12")

            self.assertFalse(result["ok"])
            self.assertIn("GITHUB_TOKEN", result["reason"])
        finally:
            if original:
                os.environ["GITHUB_TOKEN"] = original

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    @patch("time.time")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"})
    def test_build_timeout(self, mock_time, mock_sleep, mock_urlopen):
        """Build fails with timeout when poll exceeds deadline."""
        # First call: deadline = 1000 + 600 = 1600
        # Second call in while: 1700 > 1600 -> skip loop
        mock_time.side_effect = [1000.0, 1700.0]

        dispatch_resp = MagicMock()
        dispatch_resp.status = 204
        dispatch_resp.__enter__ = MagicMock(return_value=dispatch_resp)
        dispatch_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.return_value = dispatch_resp

        from src.workflows.deploy import build_and_push
        result = build_and_push("v12")

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "build_timeout")


class TestDeployToEcs(unittest.TestCase):
    """Category 3: deploy_to_ecs() tests."""

    def setUp(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False
        # Inject mock boto3 into sys.modules
        self._mock_boto3 = _make_mock_boto3()
        self._orig_boto3 = sys.modules.get("boto3")
        sys.modules["boto3"] = self._mock_boto3

    def tearDown(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False
        if self._orig_boto3 is not None:
            sys.modules["boto3"] = self._orig_boto3
        else:
            sys.modules.pop("boto3", None)

    def test_happy_path(self):
        """Full deploy: describe -> register -> update -> wait stable -> success."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs

        mock_ecs.describe_task_definition.return_value = {
            "taskDefinition": {
                "containerDefinitions": [
                    {
                        "name": "holly-grace",
                        "image": "327416545926.dkr.ecr.us-east-2.amazonaws.com/holly-grace/holly-grace:v11",
                    }
                ],
                "taskRoleArn": "arn:aws:iam::role/task",
                "executionRoleArn": "arn:aws:iam::role/exec",
                "networkMode": "awsvpc",
                "requiresCompatibilities": ["FARGATE"],
                "cpu": "512",
                "memory": "2048",
            }
        }

        mock_ecs.register_task_definition.return_value = {
            "taskDefinition": {
                "revision": 5,
                "taskDefinitionArn": "arn:aws:ecs:us-east-2:327416545926:task-definition/holly-grace-holly-grace:5",
            }
        }

        mock_ecs.update_service.return_value = {}

        mock_waiter = MagicMock()
        mock_ecs.get_waiter.return_value = mock_waiter

        from src.workflows.deploy import deploy_to_ecs
        result = deploy_to_ecs("v12", "4")

        self.assertTrue(result["ok"])
        self.assertEqual(result["new_revision"], "5")
        self.assertEqual(result["image_tag"], "v12")
        mock_waiter.wait.assert_called_once()

    def test_failed_stabilization_triggers_rollback(self):
        """When service fails to stabilize, auto-rollback to previous revision."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs

        mock_ecs.describe_task_definition.return_value = {
            "taskDefinition": {
                "containerDefinitions": [
                    {"name": "holly-grace", "image": "old:v11"}
                ],
                "taskRoleArn": "",
                "executionRoleArn": "",
                "networkMode": "awsvpc",
                "requiresCompatibilities": ["FARGATE"],
                "cpu": "512",
                "memory": "2048",
            }
        }

        mock_ecs.register_task_definition.return_value = {
            "taskDefinition": {
                "revision": 5,
                "taskDefinitionArn": "arn:aws:ecs:...:5",
            }
        }
        mock_ecs.update_service.return_value = {}

        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("Service did not stabilize")
        mock_ecs.get_waiter.return_value = mock_waiter

        from src.workflows.deploy import deploy_to_ecs
        result = deploy_to_ecs("v12", "4")

        self.assertFalse(result["ok"])
        self.assertIn("stabilize", result["reason"])
        self.assertEqual(result["rolled_back_to"], "4")

        # Verify rollback update_service was called with old revision
        calls = mock_ecs.update_service.call_args_list
        self.assertEqual(len(calls), 2)  # original + rollback
        rollback_call = calls[1]
        self.assertIn("holly-grace-holly-grace:4", rollback_call.kwargs.get("taskDefinition", ""))

    def test_boto3_error_deploy_fails(self):
        """Boto3 error during describe_task_definition causes deploy failure."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs
        mock_ecs.describe_task_definition.side_effect = Exception("AccessDeniedException")

        from src.workflows.deploy import deploy_to_ecs
        result = deploy_to_ecs("v12", "4")

        self.assertFalse(result["ok"])
        self.assertIn("Deploy failed", result["reason"])

    def test_image_tag_correctly_swapped(self):
        """Verifies the image tag in container definitions is correctly updated."""
        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs

        mock_ecs.describe_task_definition.return_value = {
            "taskDefinition": {
                "containerDefinitions": [
                    {
                        "name": "holly-grace-container",
                        "image": "327416545926.dkr.ecr.us-east-2.amazonaws.com/holly-grace/holly-grace:v11",
                    },
                    {
                        "name": "sidecar",
                        "image": "nginx:latest",
                    },
                ],
                "taskRoleArn": "",
                "executionRoleArn": "",
                "networkMode": "awsvpc",
                "requiresCompatibilities": ["FARGATE"],
                "cpu": "512",
                "memory": "2048",
            }
        }

        mock_ecs.register_task_definition.return_value = {
            "taskDefinition": {
                "revision": 6,
                "taskDefinitionArn": "arn:aws:ecs:...:6",
            }
        }
        mock_ecs.update_service.return_value = {}
        mock_waiter = MagicMock()
        mock_ecs.get_waiter.return_value = mock_waiter

        from src.workflows.deploy import deploy_to_ecs
        deploy_to_ecs("v13", "5")

        # Inspect what was passed to register_task_definition
        register_call = mock_ecs.register_task_definition.call_args
        containers = register_call.kwargs.get("containerDefinitions", [])

        # holly-grace container should have new image tag
        holly_container = [c for c in containers if "holly-grace" in c["name"]][0]
        self.assertIn("v13", holly_container["image"])
        self.assertIn("holly-grace/holly-grace:v13", holly_container["image"])

        # sidecar should NOT be changed
        sidecar = [c for c in containers if c["name"] == "sidecar"][0]
        self.assertEqual(sidecar["image"], "nginx:latest")

    def test_deploy_resets_flag_on_general_exception(self):
        """_deploy_in_progress is reset to False when a general exception occurs."""
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = True

        mock_ecs = MagicMock()
        self._mock_boto3.client.return_value = mock_ecs
        mock_ecs.describe_task_definition.side_effect = RuntimeError("boom")

        from src.workflows.deploy import deploy_to_ecs
        result = deploy_to_ecs("v12", "4")

        self.assertFalse(result["ok"])
        self.assertFalse(deploy_mod._deploy_in_progress)


class TestVerifyDeploy(unittest.TestCase):
    """Category 4: verify_deploy() tests."""

    def setUp(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = True  # Verify should reset this

    def tearDown(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False

    @patch("src.holly.memory.store_episode")
    @patch("src.tower.store.commit_effect")
    @patch("src.tower.store.prepare_effect", return_value="eff-001")
    @patch("urllib.request.urlopen")
    def test_health_check_passes(self, mock_urlopen, mock_prepare, mock_commit, mock_episode):
        """Health check passes, effect + episode recorded successfully."""
        health_resp = MagicMock()
        health_resp.status = 200
        health_resp.__enter__ = MagicMock(return_value=health_resp)
        health_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = health_resp

        from src.workflows.deploy import verify_deploy
        result = verify_deploy("v12", "5", "deploy_abc123")

        self.assertTrue(result["deployed"])
        self.assertEqual(result["health_check"], "passed")
        self.assertEqual(result["image_tag"], "v12")
        self.assertEqual(result["revision"], "5")

        # Verify tower effect was recorded
        mock_prepare.assert_called_once()
        prep_call = mock_prepare.call_args
        self.assertEqual(prep_call.kwargs["run_id"], "deploy_abc123")

        mock_commit.assert_called_once_with("eff-001", result={
            "deployed": True,
            "image_tag": "v12",
            "revision": "5",
            "health": "passed",
        })

        # Verify memory episode stored
        mock_episode.assert_called_once()
        ep_call = mock_episode.call_args
        self.assertIn("succeeded", ep_call.kwargs["summary"])

    @patch("src.holly.memory.store_episode")
    @patch("src.tower.store.commit_effect")
    @patch("src.tower.store.prepare_effect", return_value="eff-002")
    @patch("urllib.request.urlopen")
    def test_health_check_fails(self, mock_urlopen, mock_prepare, mock_commit, mock_episode):
        """Health check fails but deploy still records the result."""
        mock_urlopen.side_effect = Exception("Connection refused")

        from src.workflows.deploy import verify_deploy
        result = verify_deploy("v12", "5", "deploy_xyz789")

        self.assertTrue(result["deployed"])
        self.assertEqual(result["health_check"], "failed")

        # Effect still recorded with failed health
        mock_prepare.assert_called_once()
        mock_commit.assert_called_once()
        commit_call = mock_commit.call_args
        commit_result = commit_call.kwargs.get("result", commit_call[0][1] if len(commit_call[0]) > 1 else None)
        self.assertEqual(commit_result["health"], "failed")

        # Memory episode notes failure
        mock_episode.assert_called_once()
        ep_call = mock_episode.call_args
        self.assertIn("FAILED", ep_call.kwargs["summary"])

    @patch("src.holly.memory.store_episode")
    @patch("src.tower.store.commit_effect")
    @patch("src.tower.store.prepare_effect", return_value="eff-003")
    @patch("urllib.request.urlopen")
    def test_resets_deploy_in_progress_flag(self, mock_urlopen, mock_prepare, mock_commit, mock_episode):
        """verify_deploy always resets _deploy_in_progress to False."""
        import src.workflows.deploy as deploy_mod
        self.assertTrue(deploy_mod._deploy_in_progress)  # Confirm setUp set it

        mock_urlopen.side_effect = Exception("timeout")

        from src.workflows.deploy import verify_deploy
        verify_deploy("v12", "5", "deploy_reset")

        self.assertFalse(deploy_mod._deploy_in_progress)


class TestDeploySelfIntegration(unittest.TestCase):
    """Category 5: deploy_self() tool integration tests."""

    def setUp(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False
        # Inject mock boto3 for auto-increment test
        self._mock_boto3 = _make_mock_boto3()
        self._orig_boto3 = sys.modules.get("boto3")
        sys.modules["boto3"] = self._mock_boto3

    def tearDown(self):
        import src.workflows.deploy as deploy_mod
        deploy_mod._deploy_in_progress = False
        if self._orig_boto3 is not None:
            sys.modules["boto3"] = self._orig_boto3
        else:
            sys.modules.pop("boto3", None)

    @patch("src.workflows.deploy.verify_deploy")
    @patch("src.workflows.deploy.deploy_to_ecs")
    @patch("src.workflows.deploy.build_and_push")
    @patch("src.workflows.deploy.pre_check")
    def test_full_happy_path(self, mock_pre, mock_build, mock_deploy, mock_verify):
        """deploy_self succeeds end-to-end with all 4 workflow steps passing."""
        mock_pre.return_value = {"ok": True, "current_revision": "4"}
        mock_build.return_value = {"ok": True, "image_tag": "v12"}
        mock_deploy.return_value = {"ok": True, "new_revision": "5", "image_tag": "v12"}
        mock_verify.return_value = {
            "deployed": True,
            "image_tag": "v12",
            "revision": "5",
            "health_check": "passed",
        }

        from src.holly.tools import deploy_self
        result = deploy_self(image_tag="v12")

        self.assertEqual(result["status"], "deployed")
        self.assertEqual(result["image_tag"], "v12")
        self.assertEqual(result["revision"], "5")
        self.assertEqual(result["health_check"], "passed")

        # Verify the pipeline order
        mock_pre.assert_called_once()
        mock_build.assert_called_once_with("v12")
        mock_deploy.assert_called_once_with("v12", "4")
        mock_verify.assert_called_once()

    @patch("src.workflows.deploy.pre_check")
    def test_pre_check_failure_returns_blocked(self, mock_pre):
        """deploy_self returns blocked status when pre_check fails."""
        mock_pre.return_value = {"ok": False, "reason": "deploy_in_progress"}

        from src.holly.tools import deploy_self
        result = deploy_self(image_tag="v12")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "deploy_in_progress")

    @patch("src.workflows.deploy.build_and_push")
    @patch("src.workflows.deploy.pre_check")
    def test_build_failure_returns_build_failed(self, mock_pre, mock_build):
        """deploy_self returns build_failed when build_and_push fails."""
        mock_pre.return_value = {"ok": True, "current_revision": "4"}
        mock_build.return_value = {"ok": False, "reason": "Build failed: failure"}

        from src.holly.tools import deploy_self
        result = deploy_self(image_tag="v12")

        self.assertEqual(result["status"], "build_failed")
        self.assertIn("failure", result["reason"])

    @patch("src.workflows.deploy.verify_deploy")
    @patch("src.workflows.deploy.deploy_to_ecs")
    @patch("src.workflows.deploy.build_and_push")
    @patch("src.workflows.deploy.pre_check")
    def test_auto_increment_image_tag_from_ecr(self, mock_pre, mock_build, mock_deploy, mock_verify):
        """deploy_self auto-increments the image tag from ECR when none provided."""
        # Mock ECR describe_images to return existing tags v10, v11
        mock_ecr = MagicMock()
        self._mock_boto3.client.return_value = mock_ecr
        mock_ecr.describe_images.return_value = {
            "imageDetails": [
                {"imageTags": ["v10", "latest"]},
                {"imageTags": ["v11"]},
            ]
        }

        mock_pre.return_value = {"ok": True, "current_revision": "4"}
        mock_build.return_value = {"ok": True, "image_tag": "v12"}
        mock_deploy.return_value = {"ok": True, "new_revision": "5", "image_tag": "v12"}
        mock_verify.return_value = {
            "deployed": True,
            "image_tag": "v12",
            "revision": "5",
            "health_check": "passed",
        }

        from src.holly.tools import deploy_self
        result = deploy_self()  # No image_tag -- should auto-increment

        self.assertEqual(result["status"], "deployed")
        # Should have auto-incremented to v12 (max(10, 11) + 1)
        self.assertEqual(result["image_tag"], "v12")
        mock_build.assert_called_once_with("v12")


if __name__ == "__main__":
    unittest.main()
