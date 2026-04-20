#!/usr/bin/env python3
"""
Claude Code hook -> buddy-bridge daemon.

Fires on every Claude Code hook event, maps it to a status, and sends the
event to the buddy-bridge Unix socket fire-and-forget. Keep this script fast
and dependency-free — it runs in the hot path of the CLI.
"""
import json
import os
import socket
import sys

SOCKET_PATH = "/tmp/claude-buddy.sock"
CONNECT_TIMEOUT = 0.3  # don't block the CLI if the daemon isn't running


def _status_for_event(event: str, data: dict) -> str:
    if event == "UserPromptSubmit":
        return "processing"
    if event == "PreToolUse":
        return "running_tool"
    if event in ("PostToolUse", "PostToolUseFailure", "PermissionDenied",
                 "SubagentStart", "SubagentStop", "PostCompact"):
        return "processing"
    if event == "PermissionRequest":
        return "waiting_for_approval"
    if event == "Notification":
        return "waiting_for_input" if data.get("notification_type") == "idle_prompt" else "notification"
    if event == "Stop" or event == "StopFailure":
        return "waiting_for_input"
    if event == "SessionStart":
        return "waiting_for_input"
    if event == "SessionEnd":
        return "ended"
    if event == "PreCompact":
        return "compacting"
    return "unknown"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    event = data.get("hook_event_name", "")
    state = {
        "session_id": data.get("session_id", "unknown"),
        "cwd": data.get("cwd", ""),
        "event": event,
        "status": _status_for_event(event, data),
        "tool": data.get("tool_name"),
        "tool_input": data.get("tool_input"),
        "tool_use_id": data.get("tool_use_id"),
    }

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(CONNECT_TIMEOUT)
        s.connect(SOCKET_PATH)
        s.sendall(json.dumps(state).encode())
        s.close()
    except (socket.error, OSError, FileNotFoundError):
        # daemon not running — don't stall the CLI
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
