#!/usr/bin/env bash
# mem-os Stop hook — runs auto-capture if enabled
set -euo pipefail

WS="${MEM_OS_WORKSPACE:-.}"
CONFIG="$WS/mem-os.json"

# Check if auto_capture is enabled
if [ -f "$CONFIG" ]; then
  AUTO=$(grep -o '"auto_capture"[[:space:]]*:[[:space:]]*\(true\|false\)' "$CONFIG" 2>/dev/null | head -1 | sed 's/.*: *//')
  if [ "$AUTO" = "false" ]; then
    exit 0
  fi
fi

# Run capture
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$SCRIPT_DIR/scripts/capture.py" "$WS" 2>/dev/null || true
