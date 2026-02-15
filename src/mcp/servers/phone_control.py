"""Phone Control MCP server — ADB-based Android device control over stdio.

Stdio MCP server exposing tools for full phone control:
- phone_status: Device info, battery, storage, IP
- phone_shell: Run arbitrary shell command on phone
- phone_unlock / phone_lock / phone_wake: Screen control
- phone_screenshot: Capture screen as base64 PNG
- phone_sms: Read recent SMS messages (inbox, sent, or conversation with contact)
- phone_send_sms: Send SMS text message via Samsung Messages UI automation
- phone_notifications: Read current notifications
- phone_apps: List installed apps
- phone_open_url: Open URL in phone browser
- phone_call: Initiate phone call
- phone_clipboard: Send text to phone input
- phone_push / phone_pull: File transfer
- phone_install: Install APK
- phone_relay_start / phone_relay_stop / phone_relay_status: EC2 tunnel mgmt
- phone_remote / phone_remote_stop / phone_remote_status: Remote ADB access

Uses subprocess to call ADB directly — no external Python dependencies.
Runs as: python server.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_ADB = os.environ.get("ADB_PATH", r"C:\Users\seanp\tools\platform-tools\adb.exe")
_PHONE_IP = os.environ.get("ANDROID_WIFI_IP", "10.0.0.57")
_PIN = os.environ.get("ANDROID_PIN", "")
_EC2_HOST = os.environ.get("EC2_RELAY_PUBLIC_IP", "3.145.133.132")
_EC2_USER = os.environ.get("EC2_RELAY_USER", "ec2-user")
_EC2_KEY = os.environ.get("EC2_RELAY_KEY", r"C:\Users\seanp\.ssh\id_rsa")
_TEMP = tempfile.gettempdir()

# ---------------------------------------------------------------------------
# ADB helpers
# ---------------------------------------------------------------------------


def _get_device_serial() -> str | None:
    """Auto-select device: USB > WiFi IP:port > TLS mDNS."""
    try:
        out = subprocess.run(
            [_ADB, "devices"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return None

    usb = wifi = tls = None
    for line in out.splitlines():
        m = re.match(r"^(\S+)\s+device$", line)
        if not m:
            continue
        serial = m.group(1)
        if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial):
            if not wifi:
                wifi = serial
        elif serial.startswith("adb-"):
            if not tls:
                tls = serial
        else:
            if not usb:
                usb = serial

    return usb or wifi or tls


def _adb(*args: str, serial: str | None = None, timeout: int = 30) -> str:
    """Run an ADB command and return stdout."""
    serial = serial or _get_device_serial()
    cmd = [_ADB]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "ERROR: ADB command timed out"
    except Exception as e:
        return f"ERROR: {e}"


def _adb_shell(command: str, serial: str | None = None, timeout: int = 30) -> str:
    """Run a shell command on the phone."""
    return _adb("shell", command, serial=serial, timeout=timeout)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _phone_status(args: dict) -> str:
    serial = _get_device_serial()
    if not serial:
        return json.dumps({"error": "No device connected"})

    model = _adb_shell("getprop ro.product.model", serial=serial)
    brand = _adb_shell("getprop ro.product.brand", serial=serial)
    android = _adb_shell("getprop ro.build.version.release", serial=serial)
    sdk = _adb_shell("getprop ro.build.version.sdk", serial=serial)

    battery_out = _adb_shell("dumpsys battery", serial=serial)
    level_m = re.search(r"level:\s*(\d+)", battery_out)
    status_m = re.search(r"status:\s*(\d)", battery_out)
    level = level_m.group(1) if level_m else "?"
    status_code = status_m.group(1) if status_m else "0"
    charge_map = {"2": "Charging", "5": "Full"}
    charge_status = charge_map.get(status_code, "Not charging")

    ip_out = _adb_shell("ip route", serial=serial)
    ip_m = re.search(r"src (\d+\.\d+\.\d+\.\d+)", ip_out)
    ip = ip_m.group(1) if ip_m else "unknown"

    storage = _adb_shell("df /data | tail -1", serial=serial)

    screen_state = _adb_shell("dumpsys window | grep isKeyguardShowing", serial=serial)
    locked = "isKeyguardShowing=true" in screen_state

    return json.dumps({
        "serial": serial,
        "brand": brand,
        "model": model,
        "android_version": android,
        "sdk_version": sdk,
        "battery_level": f"{level}%",
        "battery_status": charge_status,
        "wifi_ip": ip,
        "storage": storage,
        "screen_locked": locked,
    })


def _phone_shell(args: dict) -> str:
    command = args.get("command", "")
    if not command:
        return json.dumps({"error": "command is required"})
    timeout = int(args.get("timeout", 30))
    output = _adb_shell(command, timeout=timeout)
    return json.dumps({"command": command, "output": output})


def _phone_unlock(args: dict) -> str:
    serial = _get_device_serial()
    if not serial:
        return json.dumps({"error": "No device connected"})

    # Check if already unlocked
    kg = _adb_shell("dumpsys window | grep isKeyguardShowing", serial=serial)
    if "isKeyguardShowing=false" in kg:
        return json.dumps({"status": "already_unlocked"})

    pin = args.get("pin", _PIN)
    if not pin:
        return json.dumps({"error": "PIN required (pass as arg or set ANDROID_PIN env)"})

    # Build keyevent sequence: KEYCODE_0=7 ... KEYCODE_9=16
    key_events = ""
    for digit in pin:
        keycode = 7 + int(digit)
        key_events += f" && input keyevent {keycode}"

    cmd = f"input keyevent KEYCODE_WAKEUP && sleep 1 && input swipe 540 1800 540 800 300 && sleep 1{key_events} && input keyevent 66"
    _adb_shell(cmd, serial=serial, timeout=15)
    time.sleep(1.5)

    kg_after = _adb_shell("dumpsys window | grep isKeyguardShowing", serial=serial)
    unlocked = "isKeyguardShowing=false" in kg_after
    return json.dumps({"status": "unlocked" if unlocked else "may_have_failed"})


def _phone_lock(args: dict) -> str:
    _adb_shell("input keyevent KEYCODE_POWER")
    return json.dumps({"status": "locked"})


def _phone_wake(args: dict) -> str:
    _adb_shell("input keyevent KEYCODE_WAKEUP")
    return json.dumps({"status": "screen_on"})


def _phone_screenshot(args: dict) -> str:
    serial = _get_device_serial()
    if not serial:
        return json.dumps({"error": "No device connected"})

    # Capture on phone, pull, encode
    remote_path = "/sdcard/mcp_screenshot_tmp.png"
    _adb_shell(f"screencap -p {remote_path}", serial=serial, timeout=10)

    local_path = os.path.join(_TEMP, "phone_screenshot.png")
    _adb("pull", remote_path, local_path, serial=serial, timeout=10)
    _adb_shell(f"rm {remote_path}", serial=serial)

    if not os.path.exists(local_path):
        return json.dumps({"error": "Screenshot capture failed"})

    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    size = os.path.getsize(local_path)
    os.remove(local_path)
    return json.dumps({"format": "png", "size_bytes": size, "base64": b64})


def _phone_sms(args: dict) -> str:
    limit = int(args.get("limit", 15))
    direction = args.get("direction", "all")  # inbox, sent, all
    contact = args.get("contact", "")

    uri_map = {"inbox": "content://sms/inbox", "sent": "content://sms/sent"}
    uri = uri_map.get(direction, "content://sms")

    out = _adb_shell(
        f"content query --uri {uri} --projection address:type:date:body"
        f" --sort 'date DESC LIMIT {limit}'"
    )
    messages = []
    for line in out.splitlines():
        m = re.match(
            r".*address=([^,]+),\s*type=(\d+),\s*date=(\d+),\s*body=(.*)",
            line,
        )
        if not m:
            continue
        addr = m.group(1).strip()
        if contact and contact not in addr:
            continue
        msg_type = m.group(2)
        messages.append({
            "from" if msg_type == "1" else "to": addr,
            "direction": "received" if msg_type == "1" else "sent",
            "body": m.group(4).strip(),
            "timestamp": m.group(3),
        })
    return json.dumps({"count": len(messages), "messages": messages})


def _phone_send_sms(args: dict) -> str:
    number = args.get("number", "").strip()
    message = args.get("message", "").strip()
    if not number or not message:
        return json.dumps({"error": "Both 'number' and 'message' are required"})

    # Escape single quotes for adb shell
    escaped_msg = message.replace("'", "'\\''")
    escaped_num = number.replace("'", "'\\''")

    # Open Samsung Messages with pre-filled recipient + body
    _adb_shell(
        f"am start -a android.intent.action.SENDTO"
        f" -d 'sms:{escaped_num}' --es sms_body '{escaped_msg}'"
    )
    time.sleep(3)

    # Dump UI hierarchy and find the Send button
    _adb_shell("uiautomator dump /sdcard/_mcp_ui.xml")
    ui_dump = _adb_shell("cat /sdcard/_mcp_ui.xml")
    _adb_shell("rm /sdcard/_mcp_ui.xml")

    patterns = [
        r'content-desc="[^"]*[Ss]end[^"]*"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*?content-desc="[^"]*[Ss]end[^"]*"',
        r'resource-id="[^"]*[Ss]end[^"]*"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
    ]
    for pat in patterns:
        m = re.search(pat, ui_dump)
        if m:
            x = (int(m.group(1)) + int(m.group(3))) // 2
            y = (int(m.group(2)) + int(m.group(4))) // 2
            _adb_shell(f"input tap {x} {y}")
            time.sleep(0.5)
            _adb_shell("input keyevent KEYCODE_HOME")
            return json.dumps({"status": "sent", "to": number, "message": message})

    # Fallback: message is composed but send button not found
    return json.dumps({
        "status": "composed",
        "to": number,
        "message": message,
        "note": "Message composed in Samsung Messages but Send button not auto-detected. May need manual tap.",
    })


def _phone_notifications(args: dict) -> str:
    out = _adb_shell("dumpsys notification --noredact")
    notifs = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if "NotificationRecord" in line:
            if current:
                notifs.append(current)
            current = {}
        if line.startswith("pkg="):
            current["package"] = line.split("=", 1)[1]
        if "android.title" in line:
            m = re.search(r"android\.title=(.+)", line)
            if m:
                current["title"] = m.group(1).strip()
        if "android.text" in line:
            m = re.search(r"android\.text=(.+)", line)
            if m:
                current["text"] = m.group(1).strip()
    if current:
        notifs.append(current)
    return json.dumps({"count": len(notifs), "notifications": notifs[:20]})


def _phone_apps(args: dict) -> str:
    out = _adb_shell("pm list packages -3")
    apps = sorted(line.replace("package:", "").strip() for line in out.splitlines() if line.startswith("package:"))
    return json.dumps({"count": len(apps), "apps": apps})


def _phone_open_url(args: dict) -> str:
    url = args.get("url", "")
    if not url:
        return json.dumps({"error": "url is required"})
    _adb_shell(f"am start -a android.intent.action.VIEW -d '{url}'")
    return json.dumps({"status": "opened", "url": url})


def _phone_call(args: dict) -> str:
    number = args.get("number", "")
    if not number:
        return json.dumps({"error": "number is required"})
    _adb_shell(f"am start -a android.intent.action.CALL -d 'tel:{number}'")
    return json.dumps({"status": "calling", "number": number})


def _phone_clipboard(args: dict) -> str:
    text = args.get("text", "")
    if not text:
        return json.dumps({"error": "text is required"})
    safe = text.replace(" ", "%s")
    _adb_shell(f"input text '{safe}'")
    return json.dumps({"status": "sent", "text": text})


def _phone_push(args: dict) -> str:
    local = args.get("local_path", "")
    remote = args.get("remote_path", "")
    if not local or not remote:
        return json.dumps({"error": "local_path and remote_path are required"})
    out = _adb("push", local, remote)
    return json.dumps({"status": "pushed", "output": out})


def _phone_pull(args: dict) -> str:
    remote = args.get("remote_path", "")
    local = args.get("local_path", "")
    if not remote:
        return json.dumps({"error": "remote_path is required"})
    if not local:
        local = os.path.join(_TEMP, os.path.basename(remote))
    out = _adb("pull", remote, local)
    return json.dumps({"status": "pulled", "local_path": local, "output": out})


def _phone_install(args: dict) -> str:
    apk_path = args.get("apk_path", "")
    if not apk_path:
        return json.dumps({"error": "apk_path is required"})
    out = _adb("install", apk_path, timeout=60)
    return json.dumps({"output": out})


def _phone_relay_start(args: dict) -> str:
    serial = _get_device_serial()
    if not serial:
        return json.dumps({"error": "No device connected locally"})

    pid_file = os.path.join(_TEMP, "phone-relay-tunnel.pid")

    # Kill existing
    if os.path.exists(pid_file):
        try:
            old_pid = open(pid_file).read().strip()
            if old_pid:
                subprocess.run(["taskkill", "/F", "/PID", old_pid],
                               capture_output=True, timeout=5)
        except Exception:
            pass

    # Start reverse tunnel (localhost-only binding)
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-i", _EC2_KEY,
        "-N",
        "-R", f"127.0.0.1:5555:{_PHONE_IP}:5555",
        f"{_EC2_USER}@{_EC2_HOST}",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    time.sleep(3)

    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    if proc.poll() is None:
        return json.dumps({
            "status": "active",
            "pid": proc.pid,
            "relay": f"{_EC2_HOST} localhost:5555",
        })
    return json.dumps({"status": "failed", "error": "SSH tunnel exited immediately"})


def _phone_relay_stop(args: dict) -> str:
    pid_file = os.path.join(_TEMP, "phone-relay-tunnel.pid")
    if not os.path.exists(pid_file):
        return json.dumps({"status": "not_running"})
    try:
        pid = open(pid_file).read().strip()
        if pid:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, timeout=5)
        os.remove(pid_file)
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"status": "stopped"})


def _phone_relay_status(args: dict) -> str:
    serial = _get_device_serial()
    pid_file = os.path.join(_TEMP, "phone-relay-tunnel.pid")

    result: dict[str, Any] = {
        "local_adb": serial is not None,
        "local_serial": serial,
    }

    if os.path.exists(pid_file):
        try:
            pid = open(pid_file).read().strip()
            # Check if process is alive
            check = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            result["relay_tunnel"] = "ssh.exe" in check.stdout.lower()
            result["relay_pid"] = pid
        except Exception:
            result["relay_tunnel"] = False
    else:
        result["relay_tunnel"] = False

    return json.dumps(result)


def _phone_remote(args: dict) -> str:
    ec2_host = args.get("ec2_host", _EC2_HOST)
    local_port = "15555"
    pid_file = os.path.join(_TEMP, "phone-remote-tunnel.pid")

    # Kill existing
    if os.path.exists(pid_file):
        try:
            old_pid = open(pid_file).read().strip()
            if old_pid:
                subprocess.run(["taskkill", "/F", "/PID", old_pid],
                               capture_output=True, timeout=5)
        except Exception:
            pass
    _adb("disconnect", f"localhost:{local_port}")

    # SSH local forward
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-i", _EC2_KEY,
        "-N",
        "-L", f"{local_port}:127.0.0.1:5555",
        f"{_EC2_USER}@{ec2_host}",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    time.sleep(3)

    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    if proc.poll() is not None:
        return json.dumps({"status": "failed", "error": "SSH tunnel exited immediately"})

    connect_out = _adb("connect", f"localhost:{local_port}")
    time.sleep(2)

    devices_out = subprocess.run(
        [_ADB, "devices"], capture_output=True, text=True, timeout=5
    ).stdout
    connected = f"localhost:{local_port}" in devices_out and "device" in devices_out

    return json.dumps({
        "status": "connected" if connected else "tunnel_up_adb_failed",
        "pid": proc.pid,
        "adb_output": connect_out,
    })


def _phone_remote_stop(args: dict) -> str:
    pid_file = os.path.join(_TEMP, "phone-remote-tunnel.pid")
    _adb("disconnect", "localhost:15555")
    if os.path.exists(pid_file):
        try:
            pid = open(pid_file).read().strip()
            if pid:
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, timeout=5)
            os.remove(pid_file)
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"status": "stopped"})


def _phone_remote_status(args: dict) -> str:
    pid_file = os.path.join(_TEMP, "phone-remote-tunnel.pid")
    result: dict[str, Any] = {}

    if os.path.exists(pid_file):
        try:
            pid = open(pid_file).read().strip()
            check = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            result["ssh_tunnel"] = "ssh.exe" in check.stdout.lower()
            result["tunnel_pid"] = pid
        except Exception:
            result["ssh_tunnel"] = False
    else:
        result["ssh_tunnel"] = False

    devices_out = subprocess.run(
        [_ADB, "devices"], capture_output=True, text=True, timeout=5
    ).stdout
    result["remote_adb"] = "localhost:15555" in devices_out and "device" in devices_out

    return json.dumps(result)


# ---------------------------------------------------------------------------
# MCP tool definitions
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "phone_status",
        "description": "Get phone device info: model, battery, storage, IP, lock state.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_shell",
        "description": "Run an arbitrary shell command on the Android phone via ADB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute on the phone"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "phone_unlock",
        "description": "Unlock the phone screen: wake + swipe + enter PIN.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pin": {"type": "string", "description": "PIN code (uses ANDROID_PIN env if omitted)"},
            },
        },
    },
    {
        "name": "phone_lock",
        "description": "Lock the phone screen (press power button).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_wake",
        "description": "Wake the phone screen without unlocking.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_screenshot",
        "description": "Take a screenshot of the phone screen. Returns base64-encoded PNG.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_sms",
        "description": "Read recent SMS messages. Supports inbox, sent, or all directions, and filtering by contact number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of messages to retrieve (default 15)"},
                "direction": {"type": "string", "enum": ["inbox", "sent", "all"], "description": "Message direction filter (default: all)"},
                "contact": {"type": "string", "description": "Filter messages by phone number (partial match)"},
            },
        },
    },
    {
        "name": "phone_send_sms",
        "description": "Send an SMS text message from the phone. Opens Samsung Messages, fills in recipient and body, and taps Send.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "number": {"type": "string", "description": "Recipient phone number (e.g. +15551234567)"},
                "message": {"type": "string", "description": "Text message body to send"},
            },
            "required": ["number", "message"],
        },
    },
    {
        "name": "phone_notifications",
        "description": "Read current notifications on the phone.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_apps",
        "description": "List all third-party installed apps on the phone.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_open_url",
        "description": "Open a URL in the phone's browser.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "phone_call",
        "description": "Initiate a phone call to a number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "number": {"type": "string", "description": "Phone number to call"},
            },
            "required": ["number"],
        },
    },
    {
        "name": "phone_clipboard",
        "description": "Send text to the phone's current input field.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to send"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "phone_push",
        "description": "Push a file from the local machine to the phone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "local_path": {"type": "string", "description": "Local file path"},
                "remote_path": {"type": "string", "description": "Destination path on phone (e.g. /sdcard/Download/)"},
            },
            "required": ["local_path", "remote_path"],
        },
    },
    {
        "name": "phone_pull",
        "description": "Pull a file from the phone to the local machine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "remote_path": {"type": "string", "description": "File path on phone"},
                "local_path": {"type": "string", "description": "Local destination (default: temp dir)"},
            },
            "required": ["remote_path"],
        },
    },
    {
        "name": "phone_install",
        "description": "Install an APK file on the phone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "apk_path": {"type": "string", "description": "Path to the APK file"},
            },
            "required": ["apk_path"],
        },
    },
    {
        "name": "phone_relay_start",
        "description": "Start the reverse SSH tunnel from home laptop to EC2 relay. Makes phone accessible remotely. Run on the home machine where phone is connected.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_relay_stop",
        "description": "Stop the reverse SSH tunnel to EC2 relay.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_relay_status",
        "description": "Check status of local ADB connection and EC2 relay tunnel.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_remote",
        "description": "Connect to phone via secure SSH tunnel through EC2 relay. Use from any machine with the SSH key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ec2_host": {"type": "string", "description": "EC2 relay IP (default: configured relay)"},
            },
        },
    },
    {
        "name": "phone_remote_stop",
        "description": "Disconnect the remote SSH tunnel to EC2.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "phone_remote_status",
        "description": "Check status of remote SSH tunnel and ADB connection.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_TOOL_DISPATCH = {
    "phone_status": _phone_status,
    "phone_shell": _phone_shell,
    "phone_unlock": _phone_unlock,
    "phone_lock": _phone_lock,
    "phone_wake": _phone_wake,
    "phone_screenshot": _phone_screenshot,
    "phone_sms": _phone_sms,
    "phone_send_sms": _phone_send_sms,
    "phone_notifications": _phone_notifications,
    "phone_apps": _phone_apps,
    "phone_open_url": _phone_open_url,
    "phone_call": _phone_call,
    "phone_clipboard": _phone_clipboard,
    "phone_push": _phone_push,
    "phone_pull": _phone_pull,
    "phone_install": _phone_install,
    "phone_relay_start": _phone_relay_start,
    "phone_relay_stop": _phone_relay_stop,
    "phone_relay_status": _phone_relay_status,
    "phone_remote": _phone_remote,
    "phone_remote_stop": _phone_remote_stop,
    "phone_remote_status": _phone_remote_status,
}

# ---------------------------------------------------------------------------
# MCP stdio protocol (JSON-RPC 2.0)
# ---------------------------------------------------------------------------


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

        # Notifications (no id) -- ignore
        if req_id is None:
            continue

        if method == "initialize":
            requested = (params or {}).get("protocolVersion") or "2025-11-25"
            _result(req_id, {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "phone-control", "version": "1.0.0"},
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

            # Screenshot returns base64 image — send as image content
            if name == "phone_screenshot" and "base64" in text:
                data = json.loads(text)
                if "base64" in data:
                    _result(req_id, {"content": [
                        {"type": "image", "data": data["base64"], "mimeType": "image/png"},
                    ]})
                    continue

            _result(req_id, {"content": [{"type": "text", "text": text}]})
            continue

        _error(req_id, -32601, f"Unknown method: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
