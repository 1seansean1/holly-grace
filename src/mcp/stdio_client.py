"""Minimal MCP stdio client (newline-delimited JSON-RPC).

This module intentionally supports only what Holly Grace needs:
- initialize + notifications/initialized
- tools/list
- tools/call
- ping
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Kept in sync with the Node MCP SDK we already vendor in workspace (gmail-mcp-server).
_LATEST_PROTOCOL_VERSION = "2025-11-25"


@dataclass
class StdioServerSpec:
    command: str
    args: list[str]
    cwd: str | None = None
    env: dict[str, str] | None = None


class McpStdioClient:
    def __init__(self, spec: StdioServerSpec, *, timeout_s: float = 20.0) -> None:
        self._spec = spec
        self._timeout_s = float(timeout_s)
        self._proc: subprocess.Popen[str] | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=50)
        self._id = 0

    def __enter__(self) -> "McpStdioClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def stderr_tail(self) -> list[str]:
        return list(self._stderr_tail)

    def start(self) -> None:
        if self._proc is not None:
            return

        cmd = [self._spec.command, *list(self._spec.args or [])]
        logger.debug("Starting MCP stdio server: %s", cmd)
        self._proc = subprocess.Popen(
            cmd,
            cwd=self._spec.cwd,
            env=self._spec.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # line buffered
        )

        assert self._proc.stdout is not None
        assert self._proc.stderr is not None

        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def close(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc is None:
            return

        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass

        self._proc = None

    def _read_stdout(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        while not self._stop.is_set():
            line = self._proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if isinstance(msg, dict):
                    self._messages.put(msg)
            except Exception:
                logger.debug("Failed to parse MCP stdout line: %r", line)

    def _read_stderr(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None
        while not self._stop.is_set():
            line = self._proc.stderr.readline()
            if not line:
                break
            txt = line.rstrip("\r\n")
            if txt:
                self._stderr_tail.append(txt)
                logger.debug("mcp(stderr): %s", txt)

    def _send(self, message: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("MCP process not started")
        payload = json.dumps(message, default=str) + "\n"
        self._proc.stdin.write(payload)
        self._proc.stdin.flush()

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        req_id = self._next_id()
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        return self._wait_for_response(req_id, timeout_s=timeout_s)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def _wait_for_response(self, req_id: int, *, timeout_s: float | None) -> dict[str, Any]:
        deadline = time.time() + (timeout_s if timeout_s is not None else self._timeout_s)
        pending: list[dict[str, Any]] = []

        while time.time() < deadline:
            try:
                msg = self._messages.get(timeout=0.1)
            except queue.Empty:
                continue

            # Ignore notifications
            if "id" not in msg:
                continue

            if msg.get("id") != req_id:
                pending.append(msg)
                continue

            if "error" in msg and msg["error"]:
                err = msg["error"]
                raise RuntimeError(f"MCP error for {req_id}: {err}")

            return msg.get("result") or {}

        stderr = "\n".join(self.stderr_tail[-10:])
        raise TimeoutError(f"MCP request {req_id} timed out. stderr_tail:\n{stderr}")

    # ---------------------------------------------------------------------
    # MCP primitives
    # ---------------------------------------------------------------------

    def initialize(self, *, client_name: str = "holly-grace", client_version: str = "1.0.0") -> dict[str, Any]:
        result = self.request(
            "initialize",
            {
                "protocolVersion": _LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": client_name, "version": client_version},
            },
        )
        self.notify("notifications/initialized")
        return result

    def ping(self) -> dict[str, Any]:
        return self.request("ping", None)

    def list_tools(self) -> dict[str, Any]:
        return self.request("tools/list", None)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})

