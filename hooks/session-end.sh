#!/usr/bin/env bash
# mem-os Stop hook — runs auto-capture if enabled
set -euo pipefail

WS="${MEM_OS_WORKSPACE:-.}"
CONFIG="$WS/mem-os.json"

# Check if auto_capture is enabled (use python3 for robust JSON parsing)
# Also check auto_ingest.enabled for the ingestion pipeline
# Pass path via env var to prevent injection from paths with special chars
AUTO="true"
INGEST="false"
if [ -f "$CONFIG" ]; then
  read -r AUTO INGEST < <(MEM_OS_CONFIG="$CONFIG" python3 -c "
import json, os
try:
    d = json.load(open(os.environ['MEM_OS_CONFIG']))
    auto = 'true' if d.get('auto_capture', True) else 'false'
    ingest = 'true' if d.get('auto_ingest', {}).get('enabled', False) else 'false'
    print(auto, ingest)
except Exception:
    print('true false')
" 2>/dev/null || echo "true false")
  if [ "$AUTO" = "false" ]; then
    exit 0
  fi
fi

# Run capture — log errors to stderr but don't fail the hook
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$SCRIPT_DIR/scripts/capture.py" "$WS" || echo "mem-os: capture failed (non-fatal)" >&2

# Auto-ingest pipeline: transcript scan + session summary (backgrounded, non-blocking)
if [ "$INGEST" = "true" ]; then
  CLAUDE_PROJECTS_DIR="$HOME/.claude/projects"
  if [ -d "$CLAUDE_PROJECTS_DIR" ]; then
    # Find most recently modified JSONL in ~/.claude/projects/ (within last 5 min)
    RECENT_JSONL=$(find "$CLAUDE_PROJECTS_DIR" -name '*.jsonl' -mmin -5 -printf '%T@\t%p\n' 2>/dev/null \
      | sort -rn | head -1 | cut -f2-)
    if [ -n "$RECENT_JSONL" ]; then
      # Run transcript capture (backgrounded, non-fatal)
      (python3 "$SCRIPT_DIR/scripts/transcript_capture.py" "$WS" --transcript "$RECENT_JSONL" 2>&1 \
        || echo "mem-os: transcript_capture failed (non-fatal)" >&2) &

      # Run session summarizer (backgrounded, non-fatal)
      (python3 "$SCRIPT_DIR/scripts/session_summarizer.py" "$WS" --transcript "$RECENT_JSONL" 2>&1 \
        || echo "mem-os: session_summarizer failed (non-fatal)" >&2) &
    fi
  fi
fi
