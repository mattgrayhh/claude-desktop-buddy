# buddy-bridge

Forwards Claude Code CLI session state to a Hardware Buddy stick over BLE, so
your terminal sessions drive the same busy / attention / idle animations that
Claude Desktop does.

```
~/.claude/hooks/buddy_state.py  →  /tmp/claude-buddy.sock  →  buddy_bridge.py  →  BLE (Nordic UART)  →  M5StickC Plus
```

Speaks the heartbeat protocol from [`../REFERENCE.md`](../REFERENCE.md), so no
firmware changes needed.

## Install

```bash
./install.sh
```

This:
1. `pip install --user bleak`
2. Copies `buddy_state.py` → `~/.claude/hooks/`
3. Merges 13 hook entries into `~/.claude/settings.json` (idempotent; won't duplicate)
4. Installs a launchd agent at `~/Library/LaunchAgents/com.claude.buddy-bridge.plist` and loads it

Watch it run:

```bash
tail -f ~/Library/Logs/claude-buddy-bridge.log
```

## BLE connection conflict

The stick accepts one BLE central at a time. **Claude Desktop's Hardware
Buddy bridge will contest the connection** with this daemon. Pick one:

- **CLI tracking (this daemon):** close Claude Desktop's *Hardware Buddy…*
  window, or quit Claude Desktop. The daemon will grab the link.
- **Desktop tracking (default):** `launchctl unload ~/Library/LaunchAgents/com.claude.buddy-bridge.plist`
  and reopen the Hardware Buddy window in Desktop.

On first connect, macOS will prompt for Bluetooth permission for `python3`
(or whatever `python3` resolves to) — grant it.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.claude.buddy-bridge.plist
rm ~/Library/LaunchAgents/com.claude.buddy-bridge.plist
rm ~/.claude/hooks/buddy_state.py
# then remove the 13 buddy_state.py entries from ~/.claude/settings.json by hand
```

## What gets sent

On every Claude Code hook event the daemon recomputes a heartbeat:

| Field     | Source                                                              |
| --------- | ------------------------------------------------------------------- |
| `total`   | live CLI sessions (sessions idle >10min are dropped)                |
| `running` | sessions in `processing` or `running_tool`                          |
| `waiting` | sessions in `waiting_for_approval`                                  |
| `msg`     | short display: `approve: Bash`, `Bash`, `running 2`, `idle`         |
| `entries` | last 8 event lines (tool calls, session start/end)                  |
| `prompt`  | when a session is blocked on a `PermissionRequest` (id + tool only) |
| `tokens`  | always 0 in v1 — hooks don't expose token counts                    |

Keepalive is 10s. If the stick doesn't hear from us for ~30s it goes to sleep.

## Limitations

- **No approve/deny from the stick yet** — the hook sends the `PermissionRequest`
  state but doesn't block for a response. That's v2: it requires a pending-
  permission map keyed by `tool_use_id` so the daemon can route the stick's
  `{"cmd":"permission","id":..,"decision":..}` back to the right blocked hook.
- **Single-stick.** The scanner picks the first device with a name starting
  with `Claude`. If you have two sticks, set `BUDDY_DEVICE_ADDR` env var
  (not yet implemented).
- **macOS only.** The launchd plist and `id -F` owner-name lookup are macOS.
  The Python code itself runs anywhere bleak runs.
