"""Tests for the GitHub Writer MCP server (src/mcp/servers/github_writer.py).

Covers all 7 tools, HTTP helper functions, error handling, base64 encoding,
multi-file commit flow, PR labels, and the MCP stdio main() loop.

~30 tests, unittest.TestCase style, all independent.
"""

from __future__ import annotations

import base64
import io
import json
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from urllib.error import HTTPError

from src.mcp.servers.github_writer import (
    _create_branch,
    _create_or_update_file,
    _commit_multiple_files,
    _create_pull_request,
    _delete_file,
    _get_pull_request,
    _github_request,
    _merge_pull_request,
    main,
)


def _mock_urlopen_response(body: dict, status: int = 200):
    """Build a MagicMock that behaves like an urllib response context manager."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = json.dumps(body).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _mock_urlopen_sequence(bodies: list[dict]):
    """Return a side_effect list for urlopen that yields successive responses."""
    return [_mock_urlopen_response(b) for b in bodies]


class TestGitHubRequest(unittest.TestCase):
    """Tests for the low-level _github_request helper."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_get_returns_parsed_json(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({"sha": "abc123"})
        result = _github_request("GET", "/repos/o/r/git/ref/heads/main")
        self.assertEqual(result["sha"], "abc123")

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_http_error_returns_error_dict(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.github.com/repos/o/r/git/ref/heads/nope",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b"branch not found"),
        )
        result = _github_request("GET", "/repos/o/r/git/ref/heads/nope")
        self.assertIn("error", result)
        self.assertIn("404", result["error"])
        self.assertIn("branch not found", result["detail"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_generic_exception_returns_error_dict(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("connection refused")
        result = _github_request("GET", "/repos/o/r")
        self.assertIn("error", result)
        self.assertIn("connection refused", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_empty_response_body_returns_empty_dict(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"   "
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = _github_request("DELETE", "/repos/o/r/contents/file.txt", {"sha": "x"})
        self.assertEqual(result, {})


class TestCreateBranch(unittest.TestCase):
    """Tests for the create_branch tool."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_happy_path(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"object": {"sha": "abc123"}},   # GET base ref
            {"ref": "refs/heads/feature-x"},  # POST create ref
        ])
        result = json.loads(_create_branch({"name": "feature-x", "base": "main"}))
        self.assertTrue(result["created"])
        self.assertEqual(result["branch"], "feature-x")
        self.assertEqual(result["sha"], "abc123")
        self.assertEqual(result["base"], "main")

    def test_missing_name_returns_error(self):
        result = json.loads(_create_branch({}))
        self.assertIn("error", result)
        self.assertIn("name is required", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_base_branch_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.github.com/repos/o/r/git/ref/heads/nope",
            code=404, msg="Not Found", hdrs=None,
            fp=io.BytesIO(b"ref not found"),
        )
        result = json.loads(_create_branch({"name": "feat", "base": "nope"}))
        self.assertIn("error", result)
        self.assertIn("Cannot find base branch", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_base_sha_missing_in_response(self, mock_urlopen):
        # Response is valid JSON but missing object.sha
        mock_urlopen.return_value = _mock_urlopen_response({"object": {}})
        result = json.loads(_create_branch({"name": "feat"}))
        self.assertIn("error", result)
        self.assertIn("Cannot find SHA", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_create_ref_api_error(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"object": {"sha": "abc123"}},  # GET base ref succeeds
        ]) + [HTTPError(
            url="x", code=422, msg="Unprocessable", hdrs=None,
            fp=io.BytesIO(b"ref already exists"),
        )]
        result = json.loads(_create_branch({"name": "existing-branch"}))
        self.assertIn("error", result)


class TestCreateOrUpdateFile(unittest.TestCase):
    """Tests for the create_or_update_file tool."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_create_file_happy_path(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "commit": {"sha": "commit123"},
            "content": {"sha": "blob456"},
        })
        result = json.loads(_create_or_update_file({
            "path": "src/new_file.py",
            "content": "print('hello')",
            "branch": "feature-x",
        }))
        self.assertEqual(result["path"], "src/new_file.py")
        self.assertEqual(result["branch"], "feature-x")
        self.assertEqual(result["commit_sha"], "commit123")
        self.assertEqual(result["action"], "created")

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_update_file_with_sha(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "commit": {"sha": "commit789"},
        })
        result = json.loads(_create_or_update_file({
            "path": "README.md",
            "content": "# Updated",
            "branch": "main",
            "sha": "old_sha_abc",
        }))
        self.assertEqual(result["action"], "updated")
        self.assertEqual(result["commit_sha"], "commit789")

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_base64_encoding_of_content(self, mock_urlopen):
        """Verify the tool base64-encodes file content before sending."""
        mock_urlopen.return_value = _mock_urlopen_response({
            "commit": {"sha": "c1"},
        })
        content = "line1\nline2\nspecial chars: \u00e9\u00e0\u00fc"
        _create_or_update_file({
            "path": "test.txt",
            "content": content,
            "branch": "dev",
        })
        # Inspect the data sent to urlopen
        req_obj = mock_urlopen.call_args[0][0]
        sent_body = json.loads(req_obj.data.decode("utf-8"))
        expected_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        self.assertEqual(sent_body["content"], expected_b64)

    def test_missing_path_returns_error(self):
        result = json.loads(_create_or_update_file({"content": "x", "branch": "b"}))
        self.assertIn("error", result)
        self.assertIn("path is required", result["error"])

    def test_missing_branch_returns_error(self):
        result = json.loads(_create_or_update_file({"path": "a.txt", "content": "x"}))
        self.assertIn("error", result)
        self.assertIn("branch is required", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_api_error_propagated(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="x", code=409, msg="Conflict", hdrs=None,
            fp=io.BytesIO(b"sha mismatch"),
        )
        result = json.loads(_create_or_update_file({
            "path": "f.txt", "content": "x", "branch": "b",
        }))
        self.assertIn("error", result)
        self.assertIn("409", result["error"])


class TestDeleteFile(unittest.TestCase):
    """Tests for the delete_file tool."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_happy_path(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "commit": {"sha": "del_commit_abc"},
        })
        result = json.loads(_delete_file({
            "path": "old_file.py",
            "branch": "cleanup",
            "sha": "file_sha_123",
        }))
        self.assertTrue(result["deleted"])
        self.assertEqual(result["path"], "old_file.py")
        self.assertEqual(result["commit_sha"], "del_commit_abc")

    def test_missing_path(self):
        result = json.loads(_delete_file({"branch": "b", "sha": "s"}))
        self.assertIn("path is required", result["error"])

    def test_missing_branch(self):
        result = json.loads(_delete_file({"path": "f", "sha": "s"}))
        self.assertIn("branch is required", result["error"])

    def test_missing_sha(self):
        result = json.loads(_delete_file({"path": "f", "branch": "b"}))
        self.assertIn("sha is required", result["error"])


class TestCommitMultipleFiles(unittest.TestCase):
    """Tests for the commit_multiple_files tool (Git Data API flow)."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_happy_path_two_creates(self, mock_urlopen):
        """Full flow: get ref -> get commit -> create blobs -> create tree -> create commit -> update ref."""
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"object": {"sha": "ref_sha"}},           # 1. GET ref
            {"tree": {"sha": "base_tree_sha"}},        # 2. GET commit
            {"sha": "blob_sha_1"},                     # 3. POST blob 1
            {"sha": "blob_sha_2"},                     # 4. POST blob 2
            {"sha": "new_tree_sha"},                   # 5. POST tree
            {"sha": "new_commit_sha"},                 # 6. POST commit
            {"object": {"sha": "new_commit_sha"}},     # 7. PATCH ref
        ])
        result = json.loads(_commit_multiple_files({
            "branch": "feature",
            "message": "Add two files",
            "files": [
                {"path": "a.py", "content": "print('a')", "action": "create"},
                {"path": "b.py", "content": "print('b')", "action": "create"},
            ],
        }))
        self.assertTrue(result["committed"])
        self.assertEqual(result["branch"], "feature")
        self.assertEqual(result["commit_sha"], "new_commit_sha")
        self.assertEqual(result["files_count"], 2)
        self.assertEqual(result["message"], "Add two files")

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_delete_action_uses_null_sha(self, mock_urlopen):
        """Delete action should put sha=None in tree item (no blob creation)."""
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"object": {"sha": "ref_sha"}},
            {"tree": {"sha": "base_tree_sha"}},
            # No blob creation for delete
            {"sha": "new_tree_sha"},                   # POST tree
            {"sha": "new_commit_sha"},                 # POST commit
            {"object": {"sha": "new_commit_sha"}},     # PATCH ref
        ])
        result = json.loads(_commit_multiple_files({
            "branch": "cleanup",
            "message": "Delete file",
            "files": [
                {"path": "old.py", "action": "delete"},
            ],
        }))
        self.assertTrue(result["committed"])
        # Check tree creation call includes sha=None for the deleted file
        tree_call = mock_urlopen.call_args_list[2]  # 3rd call = POST tree
        tree_req = tree_call[0][0]
        tree_body = json.loads(tree_req.data.decode("utf-8"))
        self.assertIsNone(tree_body["tree"][0]["sha"])

    def test_missing_branch(self):
        result = json.loads(_commit_multiple_files({
            "message": "m",
            "files": [{"path": "a.py", "action": "create", "content": "x"}],
        }))
        self.assertIn("branch is required", result["error"])

    def test_missing_files(self):
        result = json.loads(_commit_multiple_files({"branch": "b", "message": "m"}))
        self.assertIn("files list is required", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_blob_creation_failure(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"object": {"sha": "ref_sha"}},
            {"tree": {"sha": "base_tree_sha"}},
        ]) + [HTTPError(
            url="x", code=500, msg="Internal", hdrs=None,
            fp=io.BytesIO(b"blob error"),
        )]
        result = json.loads(_commit_multiple_files({
            "branch": "b",
            "message": "m",
            "files": [{"path": "f.py", "content": "x", "action": "create"}],
        }))
        self.assertIn("error", result)
        self.assertIn("Failed to create blob", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_branch_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="x", code=404, msg="Not Found", hdrs=None,
            fp=io.BytesIO(b"ref not found"),
        )
        result = json.loads(_commit_multiple_files({
            "branch": "nonexistent",
            "message": "m",
            "files": [{"path": "f.py", "content": "x", "action": "create"}],
        }))
        self.assertIn("error", result)
        self.assertIn("Cannot find branch", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_mixed_create_and_delete(self, mock_urlopen):
        """One create + one delete in the same commit."""
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"object": {"sha": "ref_sha"}},
            {"tree": {"sha": "base_tree_sha"}},
            {"sha": "blob_sha_new"},                   # blob for the create
            {"sha": "new_tree_sha"},
            {"sha": "new_commit_sha"},
            {"object": {"sha": "new_commit_sha"}},
        ])
        result = json.loads(_commit_multiple_files({
            "branch": "refactor",
            "message": "Rename file",
            "files": [
                {"path": "new.py", "content": "content", "action": "create"},
                {"path": "old.py", "action": "delete"},
            ],
        }))
        self.assertTrue(result["committed"])
        self.assertEqual(result["files_count"], 2)


class TestCreatePullRequest(unittest.TestCase):
    """Tests for the create_pull_request tool."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_happy_path_without_labels(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "number": 42,
            "html_url": "https://github.com/o/r/pull/42",
        })
        result = json.loads(_create_pull_request({
            "title": "Add feature",
            "body": "Description here",
            "head": "feature-branch",
            "base": "main",
        }))
        self.assertTrue(result["created"])
        self.assertEqual(result["pr_number"], 42)
        self.assertEqual(result["pr_url"], "https://github.com/o/r/pull/42")
        # Only one call (no labels call)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_labels_are_added(self, mock_urlopen):
        mock_urlopen.side_effect = _mock_urlopen_sequence([
            {"number": 10, "html_url": "https://github.com/o/r/pull/10"},
            [{"name": "holly"}, {"name": "auto"}],  # labels response
        ])
        result = json.loads(_create_pull_request({
            "title": "Automated PR",
            "head": "holly/fix",
            "labels": ["holly", "auto"],
        }))
        self.assertTrue(result["created"])
        self.assertEqual(result["pr_number"], 10)
        # Two calls: create PR + add labels
        self.assertEqual(mock_urlopen.call_count, 2)
        # Verify labels call
        labels_req = mock_urlopen.call_args_list[1][0][0]
        labels_body = json.loads(labels_req.data.decode("utf-8"))
        self.assertEqual(labels_body["labels"], ["holly", "auto"])

    def test_missing_title(self):
        result = json.loads(_create_pull_request({"head": "branch"}))
        self.assertIn("title is required", result["error"])

    def test_missing_head(self):
        result = json.loads(_create_pull_request({"title": "PR"}))
        self.assertIn("head branch is required", result["error"])


class TestMergePullRequest(unittest.TestCase):
    """Tests for the merge_pull_request tool."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_happy_path(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "merged": True,
            "sha": "merge_sha_abc",
            "message": "Pull Request successfully merged",
        })
        result = json.loads(_merge_pull_request({"pr_number": 42}))
        self.assertTrue(result["merged"])
        self.assertEqual(result["pr_number"], 42)
        self.assertEqual(result["merge_sha"], "merge_sha_abc")

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_custom_merge_method(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "merged": True, "sha": "m1", "message": "ok",
        })
        _merge_pull_request({"pr_number": 5, "merge_method": "rebase"})
        req_obj = mock_urlopen.call_args[0][0]
        sent_body = json.loads(req_obj.data.decode("utf-8"))
        self.assertEqual(sent_body["merge_method"], "rebase")

    def test_missing_pr_number(self):
        result = json.loads(_merge_pull_request({}))
        self.assertIn("pr_number is required", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_merge_conflict(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="x", code=405, msg="Method Not Allowed", hdrs=None,
            fp=io.BytesIO(b"merge conflict"),
        )
        result = json.loads(_merge_pull_request({"pr_number": 99}))
        self.assertIn("error", result)
        self.assertIn("405", result["error"])


class TestGetPullRequest(unittest.TestCase):
    """Tests for the get_pull_request tool."""

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_happy_path(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response({
            "number": 42,
            "state": "open",
            "title": "My PR",
            "mergeable": True,
            "merged": False,
            "head": {"sha": "head_sha_abc"},
            "html_url": "https://github.com/o/r/pull/42",
            "labels": [{"name": "bug"}, {"name": "priority"}],
        })
        result = json.loads(_get_pull_request({"pr_number": 42}))
        self.assertEqual(result["pr_number"], 42)
        self.assertEqual(result["state"], "open")
        self.assertEqual(result["title"], "My PR")
        self.assertTrue(result["mergeable"])
        self.assertFalse(result["merged"])
        self.assertEqual(result["head_sha"], "head_sha_abc")
        self.assertEqual(result["labels"], ["bug", "priority"])

    def test_missing_pr_number(self):
        result = json.loads(_get_pull_request({}))
        self.assertIn("pr_number is required", result["error"])

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_pr_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="x", code=404, msg="Not Found", hdrs=None,
            fp=io.BytesIO(b"not found"),
        )
        result = json.loads(_get_pull_request({"pr_number": 999}))
        self.assertIn("error", result)
        self.assertIn("404", result["error"])


class TestMainStdioLoop(unittest.TestCase):
    """Tests for the main() MCP stdio protocol loop."""

    def _run_main(self, messages: list[dict]) -> list[dict]:
        """Feed JSON-RPC messages to main() and capture output."""
        input_lines = [json.dumps(m) + "\n" for m in messages]
        captured: list[str] = []

        with patch("sys.stdin", io.StringIO("".join(input_lines))):
            with patch("sys.stdout") as mock_stdout:
                # Capture writes
                mock_stdout.write = lambda s: captured.append(s)
                mock_stdout.flush = MagicMock()
                main()

        results = []
        for line in captured:
            line = line.strip()
            if line:
                results.append(json.loads(line))
        return results

    def test_initialize(self):
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        ])
        self.assertEqual(len(responses), 1)
        r = responses[0]
        self.assertEqual(r["id"], 1)
        self.assertEqual(r["result"]["serverInfo"]["name"], "github-writer")
        self.assertEqual(r["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_tools_list(self):
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        tools_resp = responses[1]
        tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
        self.assertIn("create_branch", tool_names)
        self.assertIn("create_or_update_file", tool_names)
        self.assertIn("delete_file", tool_names)
        self.assertIn("commit_multiple_files", tool_names)
        self.assertIn("create_pull_request", tool_names)
        self.assertIn("merge_pull_request", tool_names)
        self.assertIn("get_pull_request", tool_names)
        self.assertEqual(len(tool_names), 7)

    def test_tools_call_dispatches_correctly(self):
        """tools/call with a known tool should invoke the handler and return content."""
        # Use a tool that requires no HTTP (validation error path)
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "create_branch",
                "arguments": {},  # Missing required 'name'
            }},
        ])
        self.assertEqual(len(responses), 1)
        content = responses[0]["result"]["content"]
        self.assertEqual(content[0]["type"], "text")
        text_data = json.loads(content[0]["text"])
        self.assertIn("name is required", text_data["error"])

    def test_unknown_tool_returns_error(self):
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            }},
        ])
        self.assertEqual(len(responses), 1)
        self.assertIn("error", responses[0])
        self.assertEqual(responses[0]["error"]["code"], -32601)
        self.assertIn("Unknown tool", responses[0]["error"]["message"])

    def test_unknown_method_returns_error(self):
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
        ])
        self.assertEqual(len(responses), 1)
        self.assertIn("error", responses[0])
        self.assertIn("Unknown method", responses[0]["error"]["message"])

    def test_notification_without_id_is_ignored(self):
        """Messages without an id (notifications) should be silently ignored."""
        responses = self._run_main([
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        ])
        # Only the ping should produce a response
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 1)

    def test_empty_and_invalid_lines_are_skipped(self):
        """Blank lines and malformed JSON should not crash the server."""
        input_text = "\n\nnot-json\n{\"bad\": true}\n" + json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        ) + "\n"
        captured: list[str] = []
        with patch("sys.stdin", io.StringIO(input_text)):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.write = lambda s: captured.append(s)
                mock_stdout.flush = MagicMock()
                ret = main()
        self.assertEqual(ret, 0)
        results = [json.loads(l.strip()) for l in captured if l.strip()]
        # Only the ping should produce a response
        self.assertEqual(len(results), 1)

    def test_ping_returns_empty_result(self):
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 99, "method": "ping"},
        ])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 99)
        self.assertEqual(responses[0]["result"], {})

    @patch("src.mcp.servers.github_writer.urllib.request.urlopen")
    def test_tools_call_with_real_tool(self, mock_urlopen):
        """Full round-trip: main() dispatches to get_pull_request which makes HTTP call."""
        mock_urlopen.return_value = _mock_urlopen_response({
            "number": 7,
            "state": "closed",
            "title": "Fix bug",
            "mergeable": None,
            "merged": True,
            "head": {"sha": "deadbeef"},
            "html_url": "https://github.com/o/r/pull/7",
            "labels": [],
        })
        responses = self._run_main([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "get_pull_request",
                "arguments": {"pr_number": 7},
            }},
        ])
        content_text = json.loads(responses[0]["result"]["content"][0]["text"])
        self.assertEqual(content_text["state"], "closed")
        self.assertTrue(content_text["merged"])

    def test_tools_call_handler_exception(self):
        """If a handler raises, main() should catch it and return error JSON in content."""
        with patch("src.mcp.servers.github_writer._TOOL_DISPATCH", {
            "exploding_tool": MagicMock(side_effect=RuntimeError("kaboom")),
            **{k: v for k, v in __import__("src.mcp.servers.github_writer", fromlist=["_TOOL_DISPATCH"])._TOOL_DISPATCH.items()},
        }):
            responses = self._run_main([
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                    "name": "exploding_tool",
                    "arguments": {},
                }},
            ])
            content_text = json.loads(responses[0]["result"]["content"][0]["text"])
            self.assertIn("kaboom", content_text["error"])


if __name__ == "__main__":
    unittest.main()
