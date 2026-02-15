#!/usr/bin/env python3
"""mem-os Auto-Capture Engine. Zero external deps.

SAFETY: This engine ONLY writes to intelligence/SIGNALS.md.
It NEVER writes to decisions/DECISIONS.md or tasks/TASKS.md directly.
All captured signals must go through /apply to become formal blocks.
This prevents memory poisoning from automated extraction errors.

Scans today's daily log for decision-like language not cross-referenced
to a formal D-/T- block. Appends signals to intelligence/SIGNALS.md.

Usage:
    python3 scripts/capture.py [workspace_path]
    python3 scripts/capture.py .
"""

import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_parser import parse_file


# Patterns that suggest a decision or task was made but not formalized
DECISION_PATTERNS = [
    (r"\bwe(?:'ll| will| decided| agreed| chose| went with)\b", "decision"),
    (r"\bdecided to\b", "decision"),
    (r"\blet'?s go with\b", "decision"),
    (r"\bgoing forward\b", "decision"),
    (r"\bfrom now on\b", "decision"),
    (r"\bswitching to\b", "decision"),
    (r"\bno longer\b", "decision"),
    (r"\binstead of\b", "decision"),
    (r"\bneed to\b", "task"),
    (r"\bshould\b.*\bbefore\b", "task"),
    (r"\btodo\b", "task"),
    (r"\baction item\b", "task"),
    (r"\bfollow up\b", "task"),
    (r"\bdeadline\b", "task"),
    (r"\bby end of\b", "task"),
    (r"\bmust\b.*\bbefore\b", "task"),
]

# Patterns that indicate a line IS already cross-referenced
XREF_PATTERN = re.compile(r"\b[DT]-\d{8}-\d{3}\b")


def find_today_log(workspace):
    """Find today's daily log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(workspace, "memory", f"{today}.md")
    if os.path.isfile(path):
        return path, today
    return None, today


def scan_log(log_path):
    """Scan a daily log for uncaptured decisions/tasks."""
    signals = []
    with open(log_path, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Skip if already cross-referenced
        if XREF_PATTERN.search(stripped):
            continue

        for pattern, sig_type in DECISION_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                signals.append({
                    "line": i,
                    "type": sig_type,
                    "text": stripped[:150],
                    "pattern": pattern,
                })
                break  # one match per line is enough

    return signals


def append_signals(workspace, signals, date_str):
    """Append captured signals to SIGNALS.md."""
    signals_path = os.path.join(workspace, "intelligence", "SIGNALS.md")
    if not os.path.isfile(signals_path):
        return 0

    # Check existing signals to avoid duplicates
    existing = ""
    with open(signals_path, "r") as f:
        existing = f.read()

    new_signals = []
    for sig in signals:
        # Simple dedup: skip if the text excerpt already appears
        if sig["text"][:100] in existing:
            continue
        new_signals.append(sig)

    if not new_signals:
        return 0

    # Find next signal ID — filter by today's date to avoid cross-date max
    existing_ids = re.findall(r"\[SIG-(\d{8}-\d{3})\]", existing)
    today_compact = date_str.replace("-", "")
    today_ids = [eid for eid in existing_ids if eid.startswith(today_compact)]
    if today_ids:
        counter = max(int(eid[9:]) for eid in today_ids) + 1
    else:
        counter = 1

    with open(signals_path, "a") as f:
        for sig in new_signals:
            if counter > 999:
                break  # Cap at 999 signals per day to maintain ID format
            sig_id = f"SIG-{today_compact}-{counter:03d}"
            f.write(f"\n[{sig_id}]\n")
            f.write(f"Date: {date_str}\n")
            f.write(f"Type: auto-capture-{sig['type']}\n")
            f.write(f"Source: memory/{date_str}.md:{sig['line']}\n")
            f.write(f"Status: pending\n")
            f.write(f"Excerpt: {sig['text']}\n")
            f.write(f"Action: Review and formalize as {'D-' if sig['type'] == 'decision' else 'T-'} block if warranted\n")
            f.write("\n---\n")
            counter += 1

    return len(new_signals)


def main():
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    workspace = os.path.abspath(workspace)

    log_path, date_str = find_today_log(workspace)
    if not log_path:
        print(f"capture: no daily log for {date_str}, nothing to scan")
        return

    signals = scan_log(log_path)
    if not signals:
        print(f"capture: {date_str} — 0 uncaptured items")
        return

    written = append_signals(workspace, signals, date_str)
    print(f"capture: {date_str} — {len(signals)} detected, {written} new signals appended")


if __name__ == "__main__":
    main()
