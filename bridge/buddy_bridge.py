#!/usr/bin/env python3
"""
buddy-bridge: forwards Claude Code CLI hook events to a Hardware Buddy stick
over BLE, speaking the same heartbeat protocol as the Claude Desktop bridge.

Architecture:
  ~/.claude/hooks/buddy_state.py  -> /tmp/claude-buddy.sock  -> this daemon -> BLE (Nordic UART)

Conflicts with Claude Desktop's Hardware Buddy bridge — only one can hold the
BLE link at a time. Disconnect Desktop's bridge (close Hardware Buddy window
or quit Claude Desktop) before starting this daemon.
"""

import asyncio
import json
import os
import signal
import sys
import time
from collections import OrderedDict

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.stderr.write("bleak not installed. Run: pip3 install bleak\n")
    sys.exit(1)

NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # desktop -> device (write)
NUS_TX_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # device -> desktop (notify)

SOCKET_PATH = "/tmp/claude-buddy.sock"
DEVICE_NAME_PREFIX = "Claude"
KEEPALIVE_SEC = 10
SESSION_STALE_SEC = 600  # drop sessions inactive for >10min


class BuddyState:
    """In-memory aggregation of all active CLI sessions."""

    def __init__(self):
        self.sessions = OrderedDict()  # session_id -> dict
        self.entries = []  # recent event log lines (newest first)
        self.dirty = True
        self.tokens = 0
        self.tokens_today = 0

    def apply(self, ev: dict):
        sid = ev.get("session_id", "unknown")
        status = ev.get("status", "unknown")
        now = time.time()

        sess = self.sessions.get(sid)
        if not sess:
            sess = {"status": "unknown", "tool": None, "cwd": ev.get("cwd"), "last": now,
                    "tool_use_id": None, "tool_input": None}
            self.sessions[sid] = sess

        if ev.get("event") == "SessionEnd":
            self.sessions.pop(sid, None)
        else:
            sess["status"] = status
            sess["tool"] = ev.get("tool")
            sess["tool_input"] = ev.get("tool_input")
            sess["tool_use_id"] = ev.get("tool_use_id")
            sess["cwd"] = ev.get("cwd") or sess["cwd"]
            sess["last"] = now

        # Build a short log line
        line = _event_to_line(ev)
        if line:
            self.entries.insert(0, line)
            del self.entries[8:]

        self._sweep_stale(now)
        self.dirty = True

    def _sweep_stale(self, now):
        stale = [sid for sid, s in self.sessions.items() if now - s["last"] > SESSION_STALE_SEC]
        for sid in stale:
            self.sessions.pop(sid, None)

    def heartbeat(self) -> dict:
        running = sum(1 for s in self.sessions.values()
                      if s["status"] in ("processing", "running_tool"))
        waiting = sum(1 for s in self.sessions.values()
                      if s["status"] == "waiting_for_approval")
        total = len(self.sessions)

        hb = {
            "total": total,
            "running": running,
            "waiting": waiting,
            "msg": self._msg(total, running, waiting),
            "entries": list(self.entries),
            "tokens": self.tokens,
            "tokens_today": self.tokens_today,
        }

        # Include prompt block if any session is waiting for approval
        for s in self.sessions.values():
            if s["status"] == "waiting_for_approval" and s.get("tool_use_id"):
                hb["prompt"] = {
                    "id": s["tool_use_id"],
                    "tool": s["tool"] or "?",
                    "hint": _hint(s.get("tool_input")),
                }
                break
        return hb

    def _msg(self, total, running, waiting):
        if waiting:
            for s in self.sessions.values():
                if s["status"] == "waiting_for_approval":
                    return f"approve: {s['tool'] or '?'}"
            return "waiting"
        if running:
            for s in self.sessions.values():
                if s["status"] == "running_tool" and s["tool"]:
                    return f"{s['tool']}"
            return f"running {running}"
        if total:
            return "idle"
        return "no sessions"


def _event_to_line(ev: dict) -> str:
    hhmm = time.strftime("%H:%M")
    status = ev.get("status", "")
    tool = ev.get("tool")
    if status == "running_tool" and tool:
        hint = _hint(ev.get("tool_input"))
        return f"{hhmm} {tool}: {hint}" if hint else f"{hhmm} {tool}"
    if status == "waiting_for_approval":
        return f"{hhmm} approve: {tool or '?'}"
    if status == "waiting_for_input":
        return f"{hhmm} idle"
    if status == "processing":
        return ""  # too noisy
    if ev.get("event") == "SessionStart":
        return f"{hhmm} session start"
    if ev.get("event") == "SessionEnd":
        return f"{hhmm} session end"
    return ""


def _hint(tool_input) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for k in ("command", "file_path", "pattern", "url", "description"):
        if k in tool_input and tool_input[k]:
            s = str(tool_input[k])
            return s[:60] + ("…" if len(s) > 60 else "")
    return ""


class BLELink:
    def __init__(self, state: BuddyState):
        self.state = state
        self.client: BleakClient | None = None
        self.rx_buf = b""

    async def connect_loop(self):
        while True:
            try:
                print("scanning for Claude-* device…", flush=True)
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: d.name and d.name.startswith(DEVICE_NAME_PREFIX),
                    timeout=15,
                )
                if not device:
                    await asyncio.sleep(3)
                    continue
                print(f"connecting to {device.name} [{device.address}]…", flush=True)
                async with BleakClient(device) as client:
                    self.client = client
                    await client.start_notify(NUS_TX_CHAR, self._on_notify)
                    # One-shot on connect: time sync + owner
                    tz_offset = -time.timezone if time.localtime().tm_isdst == 0 else -time.altzone
                    await self._send({"time": [int(time.time()), tz_offset]})
                    owner = os.environ.get("BUDDY_OWNER_NAME") or _mac_first_name() or "You"
                    await self._send({"cmd": "owner", "name": owner})
                    print("connected. streaming heartbeats.", flush=True)
                    await self._stream_heartbeats()
            except Exception as e:
                print(f"BLE error: {e}. retrying in 5s", flush=True)
                self.client = None
                await asyncio.sleep(5)

    async def _stream_heartbeats(self):
        last_sent = 0
        while self.client and self.client.is_connected:
            now = time.time()
            if self.state.dirty or now - last_sent >= KEEPALIVE_SEC:
                await self._send(self.state.heartbeat())
                self.state.dirty = False
                last_sent = now
            await asyncio.sleep(0.5)

    async def _send(self, obj: dict):
        if not (self.client and self.client.is_connected):
            return
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode()
        # Write in MTU-sized chunks; 180 bytes is safe on most stacks
        for i in range(0, len(data), 180):
            await self.client.write_gatt_char(NUS_RX_CHAR, data[i:i + 180], response=False)

    def _on_notify(self, _handle, data: bytearray):
        self.rx_buf += bytes(data)
        while b"\n" in self.rx_buf:
            line, self.rx_buf = self.rx_buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line.decode())
            except Exception:
                continue
            asyncio.create_task(self._handle_incoming(msg))

    async def _handle_incoming(self, msg: dict):
        cmd = msg.get("cmd")
        if cmd == "status":
            await self._send({"ack": "status", "ok": True, "data": {
                "name": "buddy-bridge", "sec": False,
                "sys": {"up": int(time.time()), "heap": 0},
            }})
        elif cmd in ("name", "owner", "unpair"):
            await self._send({"ack": cmd, "ok": True, "n": 0})
        # permission responses: deferred to v2


def _mac_first_name():
    try:
        import subprocess
        r = subprocess.run(["id", "-F"], capture_output=True, text=True, timeout=2)
        return r.stdout.strip().split()[0] if r.returncode == 0 else None
    except Exception:
        return None


async def _socket_server(state: BuddyState):
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            raw = await asyncio.wait_for(reader.read(16384), timeout=5)
            if raw:
                try:
                    state.apply(json.loads(raw.decode()))
                except Exception as e:
                    print(f"bad event: {e}", flush=True)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    srv = await asyncio.start_unix_server(handle, path=SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)
    print(f"listening on {SOCKET_PATH}", flush=True)
    async with srv:
        await srv.serve_forever()


async def main():
    state = BuddyState()
    link = BLELink(state)

    def _shutdown(*_):
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    await asyncio.gather(
        _socket_server(state),
        link.connect_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
