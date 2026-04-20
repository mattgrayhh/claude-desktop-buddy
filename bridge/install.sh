#!/usr/bin/env bash
# Installs the buddy-bridge daemon + Claude Code hook on macOS.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
PLIST_SRC="$REPO_DIR/com.claude.buddy-bridge.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.claude.buddy-bridge.plist"

echo "==> creating venv + installing bleak"
VENV="$REPO_DIR/.venv"
if [ ! -x "$VENV/bin/python3" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet bleak
VENV_PYTHON="$VENV/bin/python3"

echo "==> installing hook to $HOOKS_DIR/buddy_state.py"
mkdir -p "$HOOKS_DIR"
cp "$REPO_DIR/buddy_state.py" "$HOOKS_DIR/buddy_state.py"
chmod +x "$HOOKS_DIR/buddy_state.py"

echo "==> merging hook entries into $SETTINGS"
python3 - "$SETTINGS" "$REPO_DIR/settings-hooks.json" <<'PY'
import json, sys, os
settings_path, snippet_path = sys.argv[1], sys.argv[2]
settings = {}
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
snippet = json.load(open(snippet_path))
hooks = settings.setdefault("hooks", {})
added = 0
for event, entries in snippet["hooks"].items():
    bucket = hooks.setdefault(event, [])
    for ent in entries:
        cmd = ent["hooks"][0]["command"]
        already = any(
            h.get("command") == cmd for existing in bucket for h in existing.get("hooks", [])
        )
        if not already:
            bucket.append(ent)
            added += 1
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
print(f"added {added} hook entries")
PY

echo "==> installing launchd agent to $PLIST_DST"
mkdir -p "$(dirname "$PLIST_DST")"
sed -e "s|__PYTHON__|$VENV_PYTHON|g" \
    -e "s|__SCRIPT__|$REPO_DIR/buddy_bridge.py|g" \
    -e "s|__HOME__|$HOME|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo ""
echo "done."
echo "  log:  tail -f ~/Library/Logs/claude-buddy-bridge.log"
echo "  stop: launchctl unload $PLIST_DST"
echo ""
echo "NOTE: Claude Desktop's Hardware Buddy bridge and this daemon both try"
echo "to hold the stick's BLE connection. Disconnect Desktop's bridge before"
echo "using this (close the Hardware Buddy window, or quit Claude Desktop)."
