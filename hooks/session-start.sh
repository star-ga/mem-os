#!/usr/bin/env bash
# mem-os SessionStart hook — prints health summary for context injection
set -euo pipefail

WS="${MEM_OS_WORKSPACE:-.}"
STATE="$WS/memory/intel-state.json"

if [ ! -f "$STATE" ]; then
  echo "SessionStart:compact mem-os not initialized. Run: python3 scripts/init_workspace.py"
  exit 0
fi

# Extract key fields from intel-state.json using grep/sed (no jq dependency)
MODE=$(grep -o '"self_correcting_mode"[[:space:]]*:[[:space:]]*"[^"]*"' "$STATE" 2>/dev/null | head -1 | sed 's/.*: *"\(.*\)"/\1/' || true)
LAST=$(grep -o '"last_scan"[[:space:]]*:[[:space:]]*"[^"]*"' "$STATE" 2>/dev/null | head -1 | sed 's/.*: *"\(.*\)"/\1/' || true)
CONTRADICTIONS=$(grep -o '"contradictions_open"[[:space:]]*:[[:space:]]*[0-9]*' "$STATE" 2>/dev/null | head -1 | sed 's/.*: *//' || true)

MODE="${MODE:-unknown}"
LAST="${LAST:-never}"
CONTRADICTIONS="${CONTRADICTIONS:-0}"

echo "SessionStart:compact mem-os health: mode=$MODE last_scan=$LAST contradictions=$CONTRADICTIONS"
