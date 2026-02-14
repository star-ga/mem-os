# /scan — Memory Integrity Scan

Run the intelligence scanner to detect contradictions, drift, dead decisions, and missing cross-references across the entire memory workspace.

## When to Use
- After a session with significant decisions or changes
- During weekly maintenance
- When something "feels wrong" about the memory state
- Before making architectural decisions (verify no contradictions)

## How to Run

```bash
python3 scripts/intel_scan.py "${MEM_OS_WORKSPACE:-.}"
```

## What It Checks
1. **Contradictions** — Decisions that conflict with each other (via ConstraintSignatures)
2. **Drift** — Decisions referenced in daily logs but never formalized
3. **Dead decisions** — Active decisions with no recent references
4. **Orphan tasks** — Tasks referencing non-existent decisions
5. **Impact graph** — Downstream effects of each decision
6. **Coverage** — How many files are monitored vs total

## Output
- Updates `intelligence/CONTRADICTIONS.md`, `intelligence/DRIFT.md`
- Generates proposals in `intelligence/proposed/` (if in propose mode)
- Updates `intelligence/SCAN_LOG.md` with run results
- Updates `memory/intel-state.json` with latest metrics

## Modes
- `detect_only` — Report issues, never propose changes (default)
- `propose` — Report issues AND generate fix proposals
- `apply` — Auto-apply approved proposals (use with caution)

Check current mode: `cat memory/intel-state.json | grep self_correcting_mode`
