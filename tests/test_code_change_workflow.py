"""Tests for the code change workflow (src/workflows/code_change.py)
and the Holly tool propose_code_change (src/holly/tools.py).

35 tests across 6 categories:
  1. Governance Rules (~10)
  2. Rate Limits (~6)
  3. Content Scanning (~5)
  4. Risk Classification (~5)
  5. Workflow Integration (~5)
  6. Adversarial (~4)
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch


class TestGovernanceRules(unittest.TestCase):
    """Category 1: Forbidden-path and principal-only-path enforcement."""

    def setUp(self):
        from src.workflows import code_change

        code_change._proposal_timestamps.clear()
        code_change._file_last_proposed.clear()

    # --- Forbidden paths ---

    def test_forbidden_security_auth(self):
        """src/security/auth.py is blocked as forbidden_file."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("src/security/auth.py")
        self.assertEqual(result, "forbidden_file")

    def test_forbidden_security_middleware(self):
        """Any file under src/security/ is forbidden."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("src/security/middleware.py")
        self.assertEqual(result, "forbidden_file")

    def test_forbidden_deploy_directory(self):
        """deploy/ directory is forbidden."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("deploy/docker-compose.yml")
        self.assertEqual(result, "forbidden_file")

    def test_forbidden_env_file(self):
        """.env file is forbidden."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden(".env")
        self.assertEqual(result, "forbidden_file")

    def test_forbidden_dockerfile(self):
        """Dockerfile is forbidden."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("Dockerfile")
        self.assertEqual(result, "forbidden_file")

    def test_forbidden_github_workflows(self):
        """.github/workflows/ is forbidden."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden(".github/workflows/deploy.yml")
        self.assertEqual(result, "forbidden_file")

    def test_forbidden_tower_directory(self):
        """src/tower/ is forbidden."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("src/tower/store.py")
        self.assertEqual(result, "forbidden_file")

    # --- Principal-only paths ---

    def test_principal_only_holly_tools(self):
        """src/holly/tools.py is principal_only."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("src/holly/tools.py")
        self.assertEqual(result, "principal_only")

    def test_principal_only_serve(self):
        """src/serve.py is principal_only."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("src/serve.py")
        self.assertEqual(result, "principal_only")

    # --- Allowed paths ---

    def test_allowed_tests_directory(self):
        """tests/ is allowed."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("tests/test_new_feature.py")
        self.assertIsNone(result)

    def test_allowed_docs_directory(self):
        """docs/ is allowed."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("docs/README.md")
        self.assertIsNone(result)

    def test_allowed_src_tools(self):
        """src/tools/new_tool.py is allowed."""
        from src.workflows.code_change import _is_forbidden

        result = _is_forbidden("src/tools/new_tool.py")
        self.assertIsNone(result)


class TestRateLimits(unittest.TestCase):
    """Category 2: Rate limit enforcement."""

    def setUp(self):
        from src.workflows import code_change

        code_change._proposal_timestamps.clear()
        code_change._file_last_proposed.clear()

    def _make_file(self, path="tests/test_foo.py", content="# test"):
        return {"path": path, "content": content, "action": "create"}

    def test_sixth_proposal_rejected(self):
        """6th proposal within 1 hour is rejected (MAX_PROPOSALS_PER_HOUR=5)."""
        from src.workflows import code_change

        now = time.time()
        # Simulate 5 proposals already recorded
        code_change._proposal_timestamps.extend([now - 60 * i for i in range(5)])

        result = code_change._check_rate_limits([self._make_file()])
        self.assertEqual(result, "rate_limit_exceeded")

    def test_five_proposals_allowed(self):
        """5th proposal (exactly at limit) is still blocked because >= check."""
        from src.workflows import code_change

        now = time.time()
        # 4 proposals already recorded
        code_change._proposal_timestamps.extend([now - 60 * i for i in range(4)])

        result = code_change._check_rate_limits([self._make_file()])
        self.assertIsNone(result)

    def test_too_many_files_rejected(self):
        """21 files in one proposal exceeds MAX_FILES_PER_PROPOSAL=20."""
        from src.workflows.code_change import _check_rate_limits

        files = [self._make_file(f"tests/test_{i}.py") for i in range(21)]
        result = _check_rate_limits(files)
        self.assertEqual(result, "too_many_files")

    def test_content_too_large_rejected(self):
        """60KB total content exceeds MAX_CONTENT_BYTES=50KB."""
        from src.workflows.code_change import _check_rate_limits

        big_content = "x" * (60 * 1024)
        files = [{"path": "tests/big.py", "content": big_content, "action": "create"}]
        result = _check_rate_limits(files)
        self.assertEqual(result, "content_too_large")

    def test_cooldown_active_rejected(self):
        """Same file proposed within 10 minutes is rejected."""
        from src.workflows import code_change

        now = time.time()
        # File was proposed 5 minutes ago (within 600s cooldown)
        code_change._file_last_proposed["tests/test_foo.py"] = now - 300

        result = code_change._check_rate_limits([self._make_file()])
        self.assertEqual(result, "cooldown_active")

    def test_normal_proposal_passes(self):
        """A normal proposal within all limits passes."""
        from src.workflows.code_change import _check_rate_limits

        files = [self._make_file()]
        result = _check_rate_limits(files)
        self.assertIsNone(result)


class TestContentScanning(unittest.TestCase):
    """Category 3: Secret pattern detection in file content."""

    def setUp(self):
        from src.workflows import code_change

        code_change._proposal_timestamps.clear()
        code_change._file_last_proposed.clear()

    def _make_file(self, content):
        return [{"path": "src/tools/example.py", "content": content, "action": "create"}]

    def test_stripe_secret_key_detected(self):
        """Stripe live secret key is detected and blocked."""
        from src.workflows.code_change import _scan_content

        files = self._make_file('API_KEY = "sk_live_' + 'x' * 24 + '"')
        result = _scan_content(files)
        self.assertEqual(result, "secret_detected:stripe_secret_key")

    def test_aws_access_key_detected(self):
        """AWS access key (AKIA prefix + 16 chars) is detected."""
        from src.workflows.code_change import _scan_content

        files = self._make_file('aws_key = "AKIAIOSFODNN7EXAMPLE"')
        result = _scan_content(files)
        self.assertEqual(result, "secret_detected:aws_access_key")

    def test_anthropic_api_key_detected(self):
        """Anthropic API key (sk-ant-...) is detected."""
        from src.workflows.code_change import _scan_content

        files = self._make_file('key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"')
        result = _scan_content(files)
        self.assertEqual(result, "secret_detected:anthropic_api_key")

    def test_slack_bot_token_detected(self):
        """Slack bot token (xoxb-...) is detected."""
        from src.workflows.code_change import _scan_content

        files = self._make_file('SLACK_TOKEN = "xoxb-' + '0' * 10 + '-' + '0' * 10 + '-' + 'a' * 22 + '"')
        result = _scan_content(files)
        self.assertEqual(result, "secret_detected:slack_bot_token")

    def test_clean_content_passes(self):
        """Normal Python code with no secrets passes scanning."""
        from src.workflows.code_change import _scan_content

        files = self._make_file('def hello():\n    return "Hello, world!"')
        result = _scan_content(files)
        self.assertIsNone(result)


class TestRiskClassification(unittest.TestCase):
    """Category 4: Risk level classification based on file paths and actions."""

    def setUp(self):
        from src.workflows import code_change

        code_change._proposal_timestamps.clear()
        code_change._file_last_proposed.clear()

    def test_test_files_low_risk(self):
        """Files in tests/ are classified as low risk."""
        from src.workflows.code_change import _classify_risk

        files = [{"path": "tests/test_new.py", "action": "create"}]
        self.assertEqual(_classify_risk(files), "low")

    def test_doc_files_low_risk(self):
        """Files in docs/ are classified as low risk."""
        from src.workflows.code_change import _classify_risk

        files = [{"path": "docs/new_doc.md", "action": "create"}]
        self.assertEqual(_classify_risk(files), "low")

    def test_new_tool_file_medium_risk(self):
        """New file in src/tools/ is classified as medium risk."""
        from src.workflows.code_change import _classify_risk

        files = [{"path": "src/tools/new_tool.py", "action": "create"}]
        self.assertEqual(_classify_risk(files), "medium")

    def test_update_existing_src_high_risk(self):
        """Updating an existing src/ file is classified as high risk."""
        from src.workflows.code_change import _classify_risk

        files = [{"path": "src/agent_registry.py", "action": "update"}]
        self.assertEqual(_classify_risk(files), "high")

    def test_mixed_files_highest_risk_wins(self):
        """When mixing low, medium, and high risk files, highest wins."""
        from src.workflows.code_change import _classify_risk

        files = [
            {"path": "tests/test_x.py", "action": "create"},          # low
            {"path": "src/tools/new.py", "action": "create"},          # medium
            {"path": "src/agent_registry.py", "action": "update"},     # high
        ]
        self.assertEqual(_classify_risk(files), "high")


class TestWorkflowIntegration(unittest.TestCase):
    """Category 5: Full propose_code_change workflow (Holly tool)."""

    def setUp(self):
        from src.workflows import code_change

        code_change._proposal_timestamps.clear()
        code_change._file_last_proposed.clear()

    def _make_files(self):
        return [
            {"path": "tests/test_example.py", "content": "# test file", "action": "create"},
        ]

    @patch("src.workflows.code_change.record_audit")
    @patch("src.workflows.code_change.execute_commit")
    def test_happy_path(self, mock_commit, mock_audit):
        """Full happy path: validate -> commit -> audit -> committed status."""
        from src.holly.tools import propose_code_change

        mock_commit.return_value = {
            "branch": "holly/test-change",
            "commit_sha": "abc123def456",
            "pr_number": 42,
            "pr_url": "https://github.com/1seansean1/ecom-agents/pull/42",
        }
        mock_audit.return_value = {"audited": True}

        result = propose_code_change(
            branch_name="holly/test-change",
            description="Add test example",
            files=self._make_files(),
            create_pr=True,
        )

        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["commit_sha"], "abc123def456")
        self.assertEqual(result["pr_number"], 42)
        self.assertIn("run_id", result)
        mock_commit.assert_called_once()
        mock_audit.assert_called_once()

    def test_validation_failure_returns_rejected(self):
        """When validation fails (forbidden file), status is 'rejected'."""
        from src.holly.tools import propose_code_change

        files = [{"path": "src/security/auth.py", "content": "# hack", "action": "update"}]
        result = propose_code_change(
            branch_name="holly/bad-change",
            description="Modify security",
            files=files,
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "forbidden_file")

    @patch("src.workflows.code_change.record_audit")
    @patch("src.workflows.code_change.execute_commit")
    def test_commit_error_returns_failed(self, mock_commit, mock_audit):
        """When execute_commit returns an error, status is 'failed'."""
        from src.holly.tools import propose_code_change

        mock_commit.return_value = {"error": "Branch creation failed: 409 Conflict"}

        result = propose_code_change(
            branch_name="holly/fail-change",
            description="Add something",
            files=self._make_files(),
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("Branch creation failed", result["error"])
        mock_audit.assert_not_called()

    @patch("src.mcp.manager.get_mcp_manager")
    def test_pr_labels_medium_risk(self, mock_get_mgr):
        """Medium risk proposals get 'needs-review' label on the PR."""
        from src.workflows.code_change import execute_commit

        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        # Branch creation succeeds
        mock_mgr.call_tool.side_effect = [
            '{"branch": "holly/new-tool"}',                                         # create_branch
            '{"commit_sha": "aaa111"}',                                             # create_or_update_file
            '{"pr_number": 99, "pr_url": "https://github.com/example/pull/99"}',    # create_pull_request
        ]

        files = [{"path": "src/tools/new_tool.py", "content": "# new", "action": "create"}]
        result = execute_commit(
            files=files,
            branch_name="holly/new-tool",
            message="Add new tool",
            risk_level="medium",
            create_pr=True,
        )

        # Verify PR creation call includes 'needs-review' label
        pr_call = mock_mgr.call_tool.call_args_list[2]
        pr_args = pr_call[0][2]  # 3rd positional arg is the dict
        self.assertIn("needs-review", pr_args["labels"])
        self.assertNotIn("high-risk", pr_args["labels"])

    @patch("src.mcp.manager.get_mcp_manager")
    def test_pr_labels_high_risk(self, mock_get_mgr):
        """High risk proposals get both 'needs-review' and 'high-risk' labels."""
        from src.workflows.code_change import execute_commit

        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        mock_mgr.call_tool.side_effect = [
            '{"branch": "holly/risky"}',
            '{"commit_sha": "bbb222"}',
            '{"pr_number": 100, "pr_url": "https://github.com/example/pull/100"}',
        ]

        files = [{"path": "src/agent_registry.py", "content": "# modified", "action": "update"}]
        result = execute_commit(
            files=files,
            branch_name="holly/risky",
            message="Risky change",
            risk_level="high",
            create_pr=True,
        )

        pr_call = mock_mgr.call_tool.call_args_list[2]
        pr_args = pr_call[0][2]
        self.assertIn("needs-review", pr_args["labels"])
        self.assertIn("high-risk", pr_args["labels"])


class TestAdversarial(unittest.TestCase):
    """Category 6: Adversarial inputs trying to bypass governance."""

    def setUp(self):
        from src.workflows import code_change

        code_change._proposal_timestamps.clear()
        code_change._file_last_proposed.clear()

    def test_akia_pattern_in_content_blocked(self):
        """Content containing an AKIA pattern (AWS access key) is blocked."""
        from src.workflows.code_change import validate_proposal

        files = [
            {
                "path": "src/tools/helper.py",
                "content": 'config = {"aws_key": "AKIAIOSFODNN7EXAMPLE"}',
                "action": "create",
            }
        ]
        result = validate_proposal(files, "holly/sneaky", "Add helper")
        self.assertFalse(result["valid"])
        self.assertIn("aws_access_key", result["reason"])

    def test_script_tag_containing_secret_blocked(self):
        """Content with a <script> tag embedding a Stripe key is blocked."""
        from src.workflows.code_change import validate_proposal

        files = [
            {
                "path": "docs/page.html",
                "content": '<script>var key = "sk_live_' + 'x' * 24 + '";</script>',
                "action": "create",
            }
        ]
        result = validate_proposal(files, "holly/xss", "Add page")
        self.assertFalse(result["valid"])
        self.assertIn("stripe_secret_key", result["reason"])

    def test_rapid_fire_proposals_exceed_rate_limit(self):
        """Submitting 6 proposals rapidly exceeds the hourly rate limit."""
        from src.workflows.code_change import validate_proposal

        for i in range(5):
            files = [{"path": f"tests/test_rapid_{i}.py", "content": "# ok", "action": "create"}]
            result = validate_proposal(files, f"holly/rapid-{i}", f"Rapid change {i}")
            self.assertTrue(result["valid"], f"Proposal {i} should have passed")

        # 6th proposal should be rate-limited
        files = [{"path": "tests/test_rapid_6.py", "content": "# too many", "action": "create"}]
        result = validate_proposal(files, "holly/rapid-6", "One too many")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "rate_limit_exceeded")

    def test_file_cooldown_within_ten_minutes(self):
        """Proposing the same file again within 10 minutes triggers cooldown."""
        from src.workflows.code_change import validate_proposal

        files = [{"path": "tests/test_cooldown.py", "content": "# first", "action": "create"}]
        result1 = validate_proposal(files, "holly/cool-1", "First change")
        self.assertTrue(result1["valid"])

        # Second proposal for the same file immediately
        files2 = [{"path": "tests/test_cooldown.py", "content": "# second", "action": "update"}]
        result2 = validate_proposal(files2, "holly/cool-2", "Second change")
        self.assertFalse(result2["valid"])
        self.assertEqual(result2["reason"], "cooldown_active")


if __name__ == "__main__":
    unittest.main()
