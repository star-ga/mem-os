#!/usr/bin/env bash
# mem-os Stop hook — runs auto-capture if enabled
set -euo pipefail

WS="${MEM_OS_WORKSPACE:-.}"
CONFIG="$WS/mem-os.json"

# Check if auto_capture is enabled (use python3 for robust JSON parsing)
if [ -f "$CONFIG" ]; then
  AUTO=$(python3 -c "
import json, sys
try:
    d = json.load(open('$CONFIG'))
    print('true' if d.get('auto_capture', True) else 'false')
except Exception:
    print('true')
" 2>/dev/null || echo "true")
  if [ "$AUTO" = "false" ]; then
    exit 0
  fi
fi

# Run capture — log errors to stderr but don't fail the hook
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$SCRIPT_DIR/scripts/capture.py" "$WS" || echo "mem-os: capture failed (non-fatal)" >&2
