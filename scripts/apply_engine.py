#!/usr/bin/env python3
"""Mem OS Apply Engine v1.0 — Atomic proposal application with rollback.

Reads proposals from intelligence/proposed/, validates, executes Ops,
runs post-checks, and rolls back on failure.

Usage:
    python3 maintenance/apply_engine.py <ProposalId> [workspace_path]
    python3 maintenance/apply_engine.py P-20260213-002
    python3 maintenance/apply_engine.py P-20260213-002 --dry-run
    python3 maintenance/apply_engine.py --rollback <ReceiptTS>

Exit codes: 0 = applied, 1 = failed (rolled back), 2 = validation error
"""

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta

# Import block parser from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_parser import parse_file, parse_blocks, get_by_id


# ═══════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════

VALID_OPS = {
    "append_block", "insert_after_block", "update_field",
    "append_list_item", "replace_range", "set_status",
    "supersede_decision"
}

VALID_RISKS = {"low", "medium", "high"}
VALID_STATUSES = {"staged", "applied", "rejected", "deferred", "expired", "rolled_back"}
VALID_TYPES = {"decision", "task", "edit"}

PROPOSED_FILES = [
    "intelligence/proposed/DECISIONS_PROPOSED.md",
    "intelligence/proposed/TASKS_PROPOSED.md",
    "intelligence/proposed/EDITS_PROPOSED.md",
]

# Files to snapshot for rollback
SNAPSHOT_DIRS = [
    "decisions", "tasks", "entities", "summaries", "intelligence", "memory", "maintenance"
]
SNAPSHOT_FILES = ["AGENTS.md", "MEMORY.md", "IDENTITY.md"]


# ═══════════════════════════════════════════════
# Proposal Discovery & Validation
# ═══════════════════════════════════════════════

def find_proposal(ws, proposal_id):
    """Find a proposal block by ProposalId across all proposed files."""
    for pfile in PROPOSED_FILES:
        path = os.path.join(ws, pfile)
        if not os.path.isfile(path):
            continue
        blocks = parse_file(path)
        for b in blocks:
            if b.get("ProposalId") == proposal_id or b.get("_id") == proposal_id:
                return b, path
    return None, None


def validate_proposal(proposal):
    """Validate a proposal block before execution. Returns list of errors."""
    errors = []

    # Required fields
    for field in ("ProposalId", "Type", "Risk", "Status", "Evidence", "Rollback"):
        if not proposal.get(field):
            errors.append(f"Missing required field: {field}")

    # Enum checks
    if proposal.get("Risk") not in VALID_RISKS:
        errors.append(f"Invalid Risk: {proposal.get('Risk')} (must be {VALID_RISKS})")
    if proposal.get("Type") not in VALID_TYPES:
        errors.append(f"Invalid Type: {proposal.get('Type')} (must be {VALID_TYPES})")
    if proposal.get("Status") != "staged":
        errors.append(f"Status must be 'staged' to apply (got '{proposal.get('Status')}')")

    # Evidence must be non-empty
    evidence = proposal.get("Evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not evidence or evidence == [""] or evidence == []:
        errors.append("Evidence is empty")

    # Ops validation
    ops = proposal.get("Ops", [])
    if not ops:
        errors.append("No Ops defined")
    for i, op in enumerate(ops):
        op_type = op.get("op")
        if op_type not in VALID_OPS:
            errors.append(f"Ops[{i}]: invalid op type '{op_type}'")
        if not op.get("file"):
            errors.append(f"Ops[{i}]: missing 'file'")
        if op_type in ("update_field", "append_list_item", "set_status", "replace_range",
                        "insert_after_block", "supersede_decision") and not op.get("target"):
            errors.append(f"Ops[{i}]: op '{op_type}' requires 'target'")

    # FilesTouched must match Ops files
    files_touched = set(proposal.get("FilesTouched", []))
    ops_files = set(op.get("file", "") for op in ops)
    if files_touched and ops_files and not ops_files.issubset(files_touched):
        errors.append(f"Ops reference files not in FilesTouched: {ops_files - files_touched}")

    return errors


# ═══════════════════════════════════════════════
# Precondition Checks
# ═══════════════════════════════════════════════

def check_preconditions(ws):
    """Run validate.sh and intel_scan.py. Returns (ok, report)."""
    report = []

    # P2: validate.sh
    try:
        result = subprocess.run(
            ["bash", os.path.join(ws, "maintenance/validate.sh"), ws],
            capture_output=True, text=True, timeout=60
        )
        # Find the TOTAL line (contains "issues")
        total_line = ""
        for line in result.stdout.strip().split("\n"):
            if "issues" in line and "TOTAL" in line:
                total_line = line.strip()
                break
        if "0 issues" in total_line:
            report.append(f"validate: PASS ({total_line})")
        else:
            report.append(f"validate: FAIL ({total_line or 'no TOTAL line found'})")
            return False, report
    except Exception as e:
        report.append(f"validate: ERROR ({e})")
        return False, report

    # P3: intel_scan.py
    try:
        result = subprocess.run(
            ["python3", os.path.join(ws, "maintenance/intel_scan.py"), ws],
            capture_output=True, text=True, timeout=60
        )
        # Find the TOTAL line
        total_line = ""
        for line in result.stdout.strip().split("\n"):
            if "critical" in line and "TOTAL" in line:
                total_line = line.strip()
                break
        if "0 critical" in total_line:
            report.append(f"intel_scan: PASS ({total_line})")
        else:
            report.append(f"intel_scan: FAIL ({total_line or 'no TOTAL line found'})")
            return False, report
    except Exception as e:
        report.append(f"intel_scan: ERROR ({e})")
        return False, report

    return True, report


# ═══════════════════════════════════════════════
# Snapshot & Rollback
# ═══════════════════════════════════════════════

def create_snapshot(ws, ts):
    """Create a pre-apply snapshot for rollback."""
    snap_dir = os.path.join(ws, "intelligence/applied", ts)
    os.makedirs(snap_dir, exist_ok=True)

    for d in SNAPSHOT_DIRS:
        src = os.path.join(ws, d)
        dst = os.path.join(snap_dir, d)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)

    for f in SNAPSHOT_FILES:
        src = os.path.join(ws, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(snap_dir, f))

    return snap_dir


def restore_snapshot(ws, snap_dir):
    """Restore workspace from snapshot."""
    for d in SNAPSHOT_DIRS:
        src = os.path.join(snap_dir, d)
        dst = os.path.join(ws, d)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)

    for f in SNAPSHOT_FILES:
        src = os.path.join(snap_dir, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(ws, f))


# ═══════════════════════════════════════════════
# Apply Receipt
# ═══════════════════════════════════════════════

def write_receipt(snap_dir, proposal, ts, pre_checks, status="in_progress"):
    """Write APPLY_RECEIPT.md."""
    receipt_path = os.path.join(snap_dir, "APPLY_RECEIPT.md")
    lines = [
        f"[AR-{ts}]",
        f"ProposalId: {proposal.get('ProposalId', '?')}",
        f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}",
        f"Time: {ts}",
        f"Mode: {_get_mode()}",
        f"Risk: {proposal.get('Risk', '?')}",
        f"TargetBlock: {proposal.get('TargetBlock', '?')}",
        "FilesTouched:",
    ]
    for f in proposal.get("FilesTouched", []):
        lines.append(f"- {f}")
    lines.append("PreChecks:")
    for c in pre_checks:
        lines.append(f"- {c}")
    lines.append(f"RollbackPlan: {proposal.get('Rollback', ['?'])[0] if isinstance(proposal.get('Rollback'), list) else proposal.get('Rollback', '?')}")
    lines.append(f"Status: {status}")
    lines.append("")

    with open(receipt_path, "w") as fh:
        fh.write("\n".join(lines))
    return receipt_path


def update_receipt(receipt_path, post_checks, delta, status):
    """Update receipt with post-check results."""
    with open(receipt_path, "a") as fh:
        fh.write("PostChecks:\n")
        for c in post_checks:
            fh.write(f"- {c}\n")
        fh.write("Delta:\n")
        for k, v in delta.items():
            fh.write(f"- {k}: {v}\n")
        # Replace Status line — simpler to just append
        fh.write(f"FinalStatus: {status}\n")


def _get_mode(ws="."):
    """Read current self_correcting_mode from intel-state.json."""
    try:
        with open(os.path.join(ws, "memory/intel-state.json")) as f:
            return json.load(f).get("self_correcting_mode", "unknown")
    except Exception:
        return "unknown"


# ═══════════════════════════════════════════════
# Op Executors
# ═══════════════════════════════════════════════

def execute_op(ws, op):
    """Execute a single op. Returns (success, message)."""
    op_type = op.get("op")
    filepath = os.path.join(ws, op.get("file", ""))

    if not os.path.isfile(filepath):
        return False, f"File not found: {filepath}"

    try:
        if op_type == "append_block":
            return _op_append_block(filepath, op)
        elif op_type == "insert_after_block":
            return _op_insert_after_block(filepath, op)
        elif op_type == "update_field":
            return _op_update_field(filepath, op)
        elif op_type == "append_list_item":
            return _op_append_list_item(filepath, op)
        elif op_type == "set_status":
            return _op_set_status(filepath, op)
        elif op_type == "replace_range":
            return _op_replace_range(filepath, op)
        elif op_type == "supersede_decision":
            return _op_supersede_decision(filepath, op)
        else:
            return False, f"Unknown op: {op_type}"
    except Exception as e:
        return False, f"Op {op_type} failed: {e}"


def _op_append_block(filepath, op):
    """Append a new block at end of file."""
    patch = op.get("patch", "")
    if not patch:
        return False, "append_block: empty patch"

    with open(filepath, "a") as f:
        f.write(f"\n{patch}\n")
    return True, "append_block: OK"


def _op_insert_after_block(filepath, op):
    """Insert block after target block ID."""
    target = op.get("target")
    patch = op.get("patch", "")
    if not target or not patch:
        return False, "insert_after_block: missing target or patch"

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Find end of target block (next block header or EOF)
    target_pattern = re.compile(rf"^\[{re.escape(target)}\]")
    found = False
    insert_at = None

    for i, line in enumerate(lines):
        if target_pattern.match(line):
            found = True
            continue
        if found and re.match(r"^\[[A-Z]+-[^\]]+\]\s*$", line):
            insert_at = i
            break

    if not found:
        return False, f"insert_after_block: target {target} not found"

    if insert_at is None:
        insert_at = len(lines)

    # Insert patch
    patch_lines = [l + "\n" for l in patch.split("\n")]
    lines[insert_at:insert_at] = ["\n"] + patch_lines

    with open(filepath, "w") as f:
        f.writelines(lines)
    return True, f"insert_after_block: inserted after {target}"


def _op_update_field(filepath, op):
    """Update a field value within a specific block."""
    target = op.get("target")
    field = op.get("field")
    value = op.get("value")
    if not target or not field:
        return False, "update_field: missing target or field"

    with open(filepath, "r") as f:
        lines = f.readlines()

    target_pattern = re.compile(rf"^\[{re.escape(target)}\]")
    in_target = False
    updated = False

    for i, line in enumerate(lines):
        if target_pattern.match(line):
            in_target = True
            continue
        if in_target and re.match(r"^\[[A-Z]+-[^\]]+\]\s*$", line):
            break
        if in_target:
            field_match = re.match(rf"^{re.escape(field)}:\s+.*$", line)
            if field_match:
                lines[i] = f"{field}: {value}\n"
                updated = True
                break

    if not updated:
        return False, f"update_field: field '{field}' not found in block {target}"

    with open(filepath, "w") as f:
        f.writelines(lines)
    return True, f"update_field: {target}.{field} = {value}"


def _op_append_list_item(filepath, op):
    """Append an item to a list field within a block."""
    target = op.get("target")
    list_field = op.get("list")
    item = op.get("item", "")
    if not target or not list_field:
        return False, "append_list_item: missing target or list"

    with open(filepath, "r") as f:
        lines = f.readlines()

    target_pattern = re.compile(rf"^\[{re.escape(target)}\]")
    in_target = False
    in_list = False
    insert_at = None

    for i, line in enumerate(lines):
        if target_pattern.match(line):
            in_target = True
            continue
        if in_target and re.match(r"^\[[A-Z]+-[^\]]+\]\s*$", line):
            break
        if in_target:
            # Find the list field
            if re.match(rf"^{re.escape(list_field)}:", line):
                in_list = True
                insert_at = i + 1
                continue
            if in_list:
                # Keep tracking list items
                if line.startswith("- ") or line.startswith("  -"):
                    insert_at = i + 1
                elif line.strip() == "":
                    insert_at = i
                    break
                else:
                    # New field = end of list
                    insert_at = i
                    break

    if insert_at is None:
        return False, f"append_list_item: list '{list_field}' not found in {target}"

    # Clean item — remove surrounding quotes if present
    item_clean = item.strip().strip('"').strip("'")
    lines.insert(insert_at, f"- {item_clean}\n")

    with open(filepath, "w") as f:
        f.writelines(lines)
    return True, f"append_list_item: added to {target}.{list_field}"


def _op_set_status(filepath, op):
    """Update Status field + auto-append History entry."""
    target = op.get("target")
    status = op.get("status")
    history = op.get("history", "")
    if not target or not status:
        return False, "set_status: missing target or status"

    # First update the Status field
    ok, msg = _op_update_field(filepath, {"target": target, "field": "Status", "value": status})
    if not ok:
        return False, f"set_status: field update failed: {msg}"

    # Then append History entry if provided
    if history:
        ok2, msg2 = _op_append_list_item(filepath, {
            "target": target, "list": "History", "item": history
        })
        if not ok2:
            return False, f"set_status: history append failed: {msg2}"

    return True, f"set_status: {target} -> {status}"


def _op_replace_range(filepath, op):
    """Replace content between start/end markers within a block."""
    target = op.get("target")
    range_spec = op.get("range", {})
    patch = op.get("patch", "")
    start_marker = range_spec.get("start", "")
    end_marker = range_spec.get("end", "")

    if not target or not start_marker or not end_marker:
        return False, "replace_range: missing target, range.start, or range.end"

    with open(filepath, "r") as f:
        lines = f.readlines()

    target_pattern = re.compile(rf"^\[{re.escape(target)}\]")
    in_target = False
    start_line = None
    end_line = None

    for i, line in enumerate(lines):
        if target_pattern.match(line):
            in_target = True
            continue
        if in_target and re.match(r"^\[[A-Z]+-[^\]]+\]\s*$", line):
            break
        if in_target:
            if start_marker in line and start_line is None:
                start_line = i
            if end_marker in line and start_line is not None:
                end_line = i
                break

    if start_line is None or end_line is None:
        return False, f"replace_range: markers not found in {target}"

    # Replace lines between markers (exclusive of end marker line)
    patch_lines = [l + "\n" for l in patch.split("\n")]
    lines[start_line:end_line] = patch_lines

    with open(filepath, "w") as f:
        f.writelines(lines)
    return True, f"replace_range: replaced {end_line - start_line} lines in {target}"


def _op_supersede_decision(filepath, op):
    """Atomic supersede: append new block + mark old as superseded."""
    target = op.get("target")
    new_block = op.get("new_block") or op.get("patch", "")
    if not target or not new_block:
        return False, "supersede_decision: missing target or new_block/patch"

    # Check that target exists and is not invariant enforcement
    blocks = parse_file(filepath)
    old = get_by_id(blocks, target)
    if not old:
        return False, f"supersede_decision: target {target} not found"

    # Invariant check
    sigs = old.get("ConstraintSignatures", [])
    has_invariant = any(s.get("enforcement") == "invariant" for s in sigs)
    if has_invariant:
        return False, f"supersede_decision: {target} has invariant enforcement (requires Risk=high + /confirm)"

    # Step 1: Mark old decision as superseded
    ok, msg = _op_update_field(filepath, {"target": target, "field": "Status", "value": "superseded"})
    if not ok:
        return False, f"supersede_decision step 1 (mark superseded): {msg}"

    # Step 2: Append new block
    ok2, msg2 = _op_append_block(filepath, {"patch": new_block})
    if not ok2:
        return False, f"supersede_decision step 2 (append new): {msg2}"

    return True, f"supersede_decision: {target} -> superseded, new block appended"


# ═══════════════════════════════════════════════
# v2.1.2 Operational Hardening
# ═══════════════════════════════════════════════

def compute_fingerprint(proposal):
    """Deterministic fingerprint from proposal content. Prevents duplicates."""
    canon = json.dumps({
        "type": proposal.get("Type", ""),
        "target": proposal.get("TargetBlock", ""),
        "ops": [
            {"op": op.get("op"), "file": op.get("file"), "target": op.get("target")}
            for op in proposal.get("Ops", [])
        ]
    }, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def check_fingerprint_dedup(ws, proposal):
    """Check if a proposal with same fingerprint already exists (staged or deferred)."""
    fp = compute_fingerprint(proposal)
    for pfile in PROPOSED_FILES:
        path = os.path.join(ws, pfile)
        if not os.path.isfile(path):
            continue
        blocks = parse_file(path)
        for b in blocks:
            if b.get("Status") in ("staged", "deferred"):
                existing_fp = b.get("Fingerprint", "")
                if existing_fp == fp:
                    return True, b.get("ProposalId", b.get("_id", "?"))
    return False, None


def check_backlog_limit(ws):
    """Count staged proposals. Returns (count, limit_exceeded)."""
    state = _load_intel_state(ws)
    limit = state.get("proposal_budget", {}).get("backlog_limit", 30)
    count = 0
    for pfile in PROPOSED_FILES:
        path = os.path.join(ws, pfile)
        if not os.path.isfile(path):
            continue
        blocks = parse_file(path)
        count += sum(1 for b in blocks if b.get("Status") == "staged")
    return count, count >= limit


def check_no_touch_window(ws):
    """Check if enough time has passed since last apply. Returns (ok, reason)."""
    state = _load_intel_state(ws)
    last_ts = state.get("last_apply_ts")
    if not last_ts:
        return True, "No previous apply"
    try:
        last = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        now = datetime.now(last.tzinfo) if last.tzinfo else datetime.utcnow()
        delta = now - last.replace(tzinfo=None) if last.tzinfo else now - last
        if delta < timedelta(minutes=10):
            remaining = timedelta(minutes=10) - delta
            return False, f"No-touch window: {remaining.seconds // 60}m {remaining.seconds % 60}s remaining"
    except (ValueError, TypeError):
        pass
    return True, "Cooldown clear"


def check_deferred_cooldown(ws, proposal):
    """Check if a rejected/deferred proposal for same target is still in cooldown."""
    state = _load_intel_state(ws)
    cooldown_days = state.get("defer_cooldown_days", 7)
    target = proposal.get("TargetBlock", "")
    if not target:
        return True, "No target"

    cutoff = datetime.utcnow() - timedelta(days=cooldown_days)

    for pfile in PROPOSED_FILES:
        path = os.path.join(ws, pfile)
        if not os.path.isfile(path):
            continue
        blocks = parse_file(path)
        for b in blocks:
            if b.get("Status") in ("rejected", "deferred") and b.get("TargetBlock") == target:
                created = b.get("Created", "")
                try:
                    created_dt = datetime.fromisoformat(created)
                    if created_dt > cutoff:
                        return False, f"Target {target} has {b.get('Status')} proposal {b.get('ProposalId')} within {cooldown_days}d cooldown"
                except (ValueError, TypeError):
                    pass
    return True, "No cooldown conflict"


def update_last_apply_ts(ws):
    """Record the timestamp of the last apply."""
    state = _load_intel_state(ws)
    state["last_apply_ts"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_intel_state(ws, state)


def generate_diff_artifact(ws, snap_dir, files_touched):
    """Generate DIFF.txt showing what changed during apply."""
    diff_lines = []
    for rel_path in files_touched:
        old_path = os.path.join(snap_dir, rel_path)
        new_path = os.path.join(ws, rel_path)

        old_lines = []
        new_lines = []
        if os.path.isfile(old_path):
            with open(old_path, "r", errors="replace") as f:
                old_lines = f.readlines()
        if os.path.isfile(new_path):
            with open(new_path, "r", errors="replace") as f:
                new_lines = f.readlines()

        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}",
            lineterm=""
        )
        diff_text = "\n".join(diff)
        if diff_text:
            diff_lines.append(diff_text)

    diff_path = os.path.join(snap_dir, "DIFF.txt")
    with open(diff_path, "w") as f:
        if diff_lines:
            f.write("\n\n".join(diff_lines))
        else:
            f.write("(no differences detected)\n")
    return diff_path


def _load_intel_state(ws):
    """Load intel-state.json."""
    path = os.path.join(ws, "memory/intel-state.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_intel_state(ws, state):
    """Save intel-state.json."""
    path = os.path.join(ws, "memory/intel-state.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


# ═══════════════════════════════════════════════
# Main Apply Pipeline
# ═══════════════════════════════════════════════

def apply_proposal(ws, proposal_id, dry_run=False):
    """Main apply pipeline. Returns (success, message)."""
    print(f"═══ Mem OS Apply Engine v1.0 ═══")
    print(f"Proposal: {proposal_id}")
    print(f"Workspace: {ws}")
    print(f"Dry run: {dry_run}")
    print()

    # 1. Find proposal
    proposal, source_file = find_proposal(ws, proposal_id)
    if not proposal:
        print(f"ERROR: Proposal {proposal_id} not found in proposed/ files.")
        return False, "Proposal not found"

    print(f"Found in: {source_file}")
    print(f"Type: {proposal.get('Type')}  Risk: {proposal.get('Risk')}  Status: {proposal.get('Status')}")

    # 2. Validate proposal
    errors = validate_proposal(proposal)
    if errors:
        print(f"\nVALIDATION ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        return False, f"Validation failed: {len(errors)} error(s)"

    print("Proposal validation: PASS")

    # 2b. Fingerprint
    fp = compute_fingerprint(proposal)
    print(f"Fingerprint: {fp}")

    # 2c. v2.1.2 hardening checks (hard fail)
    print("\n--- Hardening Checks ---")

    # Dedup check
    is_dup, dup_id = check_fingerprint_dedup(ws, proposal)
    if is_dup:
        print(f"  FAIL: Duplicate fingerprint — matches {dup_id}")
        return False, f"Duplicate proposal (matches {dup_id})"
    print("  Dedup: PASS")

    # Backlog limit
    backlog_count, over_limit = check_backlog_limit(ws)
    if over_limit:
        print(f"  FAIL: Backlog limit exceeded ({backlog_count} staged)")
        return False, f"Backlog limit exceeded ({backlog_count} staged)"
    print(f"  Backlog: PASS ({backlog_count} staged)")

    # Deferred cooldown
    ok_cool, cool_reason = check_deferred_cooldown(ws, proposal)
    if not ok_cool:
        print(f"  FAIL: {cool_reason}")
        return False, cool_reason
    print(f"  Cooldown: PASS")

    # No-touch window (warning on dry-run, hard fail on real apply)
    ok_touch, touch_reason = check_no_touch_window(ws)
    if not ok_touch and not dry_run:
        print(f"  FAIL: {touch_reason}")
        return False, touch_reason
    elif not ok_touch:
        print(f"  WARN: {touch_reason} (dry-run, continuing)")
    else:
        print(f"  No-touch window: PASS")

    # 3. Check preconditions
    print("\n--- Precondition Checks ---")
    ok, pre_report = check_preconditions(ws)
    for r in pre_report:
        print(f"  {r}")
    if not ok:
        print("PRECONDITIONS FAILED — aborting.")
        return False, "Precondition check failed"

    if dry_run:
        print("\n--- DRY RUN: would execute these ops ---")
        for i, op in enumerate(proposal.get("Ops", [])):
            print(f"  [{i}] {op.get('op')} -> {op.get('file')}:{op.get('target', 'eof')}")
        print("\nDry run complete. No changes made.")
        return True, "Dry run OK"

    # 4. Create snapshot
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    print(f"\n--- Creating Snapshot: {ts} ---")
    snap_dir = create_snapshot(ws, ts)
    receipt_path = write_receipt(snap_dir, proposal, ts, pre_report)
    print(f"  Snapshot: {snap_dir}")
    print(f"  Receipt: {receipt_path}")

    # 5. Execute ops
    print(f"\n--- Executing {len(proposal.get('Ops', []))} Ops ---")
    delta = {"created": [], "modified": []}
    for i, op in enumerate(proposal.get("Ops", [])):
        ok, msg = execute_op(ws, op)
        print(f"  [{i}] {op.get('op')}: {msg}")
        if not ok:
            print(f"\nOP FAILED at step {i} — rolling back.")
            restore_snapshot(ws, snap_dir)
            update_receipt(receipt_path, ["ABORTED: op failure"], delta, "rolled_back")
            return False, f"Op {i} failed: {msg}"
        # Track delta
        target = op.get("target", "")
        if op.get("op") in ("append_block", "insert_after_block", "supersede_decision"):
            delta["created"].append(target or "new")
        else:
            delta["modified"].append(target)

    # 6. Post-checks
    print("\n--- Post-checks ---")
    ok, post_report = check_preconditions(ws)
    for r in post_report:
        print(f"  {r}")

    if not ok:
        print("\nPOST-CHECKS FAILED — rolling back.")
        restore_snapshot(ws, snap_dir)
        update_receipt(receipt_path, post_report, delta, "rolled_back")
        # Also mark proposal as rolled back
        _mark_proposal_status(source_file, proposal_id, "rolled_back")
        return False, "Post-checks failed, rolled back"

    # 7. Generate DIFF.txt
    files_touched = proposal.get("FilesTouched", [])
    diff_path = generate_diff_artifact(ws, snap_dir, files_touched)
    print(f"  Diff artifact: {diff_path}")

    # 8. Commit receipt + mark proposal as applied + update last_apply_ts
    update_receipt(receipt_path, post_report, delta, "applied")
    _mark_proposal_status(source_file, proposal_id, "applied")
    update_last_apply_ts(ws)
    print(f"\n═══ APPLIED: {proposal_id} ═══")
    print(f"Receipt: {receipt_path}")
    return True, f"Applied successfully. Receipt: {receipt_path}"


def _mark_proposal_status(source_file, proposal_id, new_status):
    """Update the Status field in the proposal's source file."""
    try:
        with open(source_file, "r") as f:
            content = f.read()
        # Find the proposal block and update its Status
        # Simple approach: find line with "ProposalId: <id>" then find "Status:" nearby
        lines = content.split("\n")
        in_proposal = False
        for i, line in enumerate(lines):
            if f"ProposalId: {proposal_id}" in line:
                in_proposal = True
                continue
            if in_proposal and line.startswith("Status:"):
                lines[i] = f"Status: {new_status}"
                break
            if in_proposal and re.match(r"^\[[A-Z]+-[^\]]+\]", line):
                break
        with open(source_file, "w") as f:
            f.write("\n".join(lines))
    except Exception:
        pass  # Non-critical — receipt is the primary record


def rollback(ws, receipt_ts):
    """Rollback from a receipt timestamp."""
    snap_dir = os.path.join(ws, "intelligence/applied", receipt_ts)
    if not os.path.isdir(snap_dir):
        print(f"ERROR: Snapshot directory not found: {snap_dir}")
        return False

    print(f"Restoring from snapshot: {snap_dir}")
    restore_snapshot(ws, snap_dir)

    # Re-run checks
    print("\n--- Post-rollback checks ---")
    ok, report = check_preconditions(ws)
    for r in report:
        print(f"  {r}")

    # Update receipt
    receipt_path = os.path.join(snap_dir, "APPLY_RECEIPT.md")
    if os.path.isfile(receipt_path):
        with open(receipt_path, "a") as f:
            f.write(f"\nRolledBack: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
            f.write(f"FinalStatus: rolled_back\n")

    print(f"\n═══ ROLLED BACK from {receipt_ts} ═══")
    return True


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mem OS Apply Engine v1.0")
    parser.add_argument("proposal_id", nargs="?", help="ProposalId to apply (e.g. P-20260213-002)")
    parser.add_argument("workspace", nargs="?", default=".", help="Workspace path")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show ops without executing")
    parser.add_argument("--rollback", metavar="TS", help="Rollback to receipt timestamp")
    args = parser.parse_args()

    ws = os.path.abspath(args.workspace)
    os.chdir(ws)

    if args.rollback:
        ok = rollback(ws, args.rollback)
        sys.exit(0 if ok else 1)

    if not args.proposal_id:
        parser.error("proposal_id is required (or use --rollback)")

    ok, msg = apply_proposal(ws, args.proposal_id, dry_run=args.dry_run)
    print(f"\n{msg}")
    sys.exit(0 if ok else 1)
