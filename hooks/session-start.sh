#!/usr/bin/env bash
# mem-os SessionStart hook — prints health summary for context injection
set -euo pipefail

WS="${MEM_OS_WORKSPACE:-.}"
STATE="$WS/memory/intel-state.json"

if [ ! -f "$STATE" ]; then
  echo "SessionStart:compact mem-os not initialized. Run: python3 scripts/init_workspace.py"
  exit 0
fi

# Parse JSON with python3 (robust, no jq dependency)
read -r MODE LAST CONTRADICTIONS < <(python3 -c "
import json, sys
try:
    d = json.load(open('$STATE'))
    print(d.get('self_correcting_mode', 'unknown'),
          d.get('last_scan', 'never'),
          d.get('contradictions_open', 0))
except Exception:
    print('unknown never 0')
")

echo "SessionStart:compact mem-os health: mode=$MODE last_scan=$LAST contradictions=$CONTRADICTIONS"
