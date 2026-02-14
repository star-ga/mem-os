# mem-os

**Memory + Immune System for AI agents.**

Most memory plugins store and retrieve. mem-os also detects contradictions, catches drift, and self-corrects — giving your agent an integrity layer on top of recall.

## What It Does

**Recall** — TF-IDF search across all structured memory (decisions, tasks, entities, incidents)

**Integrity** — Automated detection of:
- Contradictions between decisions
- Drift (informal decisions never formalized)
- Dead decisions (active but never referenced)
- Orphan tasks (referencing non-existent decisions)
- Missing cross-references

**Self-Correction** — Graduated autonomy:
- `detect_only` — Report issues (default, safe)
- `propose` — Report + generate fix proposals
- `apply` — Auto-apply approved fixes with rollback

**Auto-Capture** — Session-end hook scans daily logs for decision-like language that wasn't formalized, appends signals for review

## Quick Start

### 1. Install
```bash
# Clone or install as OpenClaw plugin
git clone https://github.com/star-ga/mem-os.git
```

### 2. Initialize Workspace
```bash
python3 scripts/init_workspace.py /path/to/your/workspace
```

This creates the directory structure, copies templates, and generates `mem-os.json` config. Never overwrites existing files.

### 3. Run Integrity Scan
```bash
python3 scripts/intel_scan.py /path/to/your/workspace
```

### 4. Search Memory
```bash
python3 scripts/recall.py --query "authentication" --workspace /path/to/your/workspace
```

## Commands

- `/scan` — Run integrity scan (contradictions, drift, dead decisions)
- `/apply` — Review and apply proposals from scan results
- `/recall` — Search across all memory files

## Architecture

```
your-workspace/
├── mem-os.json              # Config
├── MEMORY.md                # Protocol rules
├── decisions/DECISIONS.md   # Formal decisions [D-YYYYMMDD-###]
├── tasks/TASKS.md           # Tasks [T-YYYYMMDD-###]
├── entities/
│   ├── projects.md          # Projects [PRJ-###]
│   ├── people.md            # People [PER-###]
│   ├── tools.md             # Tools [TOOL-###]
│   └── incidents.md         # Incidents [INC-###]
├── memory/
│   ├── YYYY-MM-DD.md        # Daily logs (append-only)
│   └── intel-state.json     # Scanner state
├── intelligence/
│   ├── CONTRADICTIONS.md    # Detected contradictions
│   ├── DRIFT.md             # Drift detections
│   ├── SIGNALS.md           # Auto-captured signals
│   ├── IMPACT.md            # Decision impact graph
│   ├── BRIEFINGS.md         # Weekly briefings
│   ├── AUDIT.md             # Applied proposal audit trail
│   ├── SCAN_LOG.md          # Scan history
│   └── proposed/            # Staged proposals
├── summaries/
│   └── weekly/              # Weekly summaries
└── maintenance/
    ├── intel_scan.py         # Local copy of scanner
    ├── apply_engine.py       # Local copy of apply engine
    ├── block_parser.py       # Markdown block parser
    └── validate.sh           # Structural validator
```

## How It Compares

**Recall-only plugins** (Supermemory, Mem0, claude-mem):
- Store and retrieve memories
- No contradiction detection
- No drift analysis
- No self-correction
- No structural validation

**mem-os**:
- Everything above PLUS integrity checking
- Detects when decisions contradict each other
- Catches decisions made informally but never formalized
- Finds dead decisions nobody references anymore
- Self-correcting with graduated autonomy and rollback safety
- Structural validation with 80+ checks
- Zero external dependencies (Python 3.8+ stdlib only)

## Block Format

All structured data uses a simple markdown format:

```markdown
## [D-20260213-001]
Date: 2026-02-13
Status: active
Statement: Use PostgreSQL for the user database
Tags: database, infrastructure
Rationale: Better JSON support than MySQL for our use case
```

Blocks are parsed by `block_parser.py` which extracts key-value pairs from markdown headers.

## Configuration

See `mem-os.example.json` for all options:

- `auto_capture` — Run capture engine on session end (default: true)
- `auto_recall` — Enable recall on session start (default: true)
- `self_correcting_mode` — "detect_only", "propose", or "apply"
- `proposal_budget` — Limits on auto-generated proposals per run/day
- `scan_schedule` — "daily" or "manual"

## Requirements

- Python 3.8+
- Bash (for hooks and validate.sh)
- No external packages required

## License

MIT License. Copyright 2026 STARGA Inc.
