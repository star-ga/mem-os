# Mem OS for OpenClaw (latest)

**Best-in-class memory stack for OpenClaw agents — local-first, auditable, self-correcting.**

This repository is a drop-in memory layer designed specifically for OpenClaw (latest). It upgrades an OpenClaw bot from "chat history + notes" to a governed Memory OS with:

- persistent structured memory (decisions / tasks / entities / incidents)
- deterministic contradiction + drift detection
- proposals + safe apply + rollback
- audit trail + integrity validation
- optional semantic recall (vector) with local-first defaults

If you want the strongest memory you can reasonably run with OpenClaw — this is it.

---

## What this gives your OpenClaw bot

### Persistent memory that stays correct over months/years

Not just "store everything" — but store it with:
- schemas
- validation
- provenance ("no source = no memory claim")
- supersede chains (no silent edits)

### An "immune system" for memory

Mem OS continuously checks and reports:
- contradictions between decisions
- drift (dead decisions, stalled tasks, repeated incidents)
- coverage score (are decisions actually enforced?)
- integrity regressions

### Safe evolution (no silent corruption)

All changes flow through: `detect_only` → `propose` → `enforce`

With:
- proposal queue
- apply engine with snapshot + receipt + DIFF
- automatic rollback if validation fails

---

## Designed for OpenClaw (latest)

Mem OS integrates with OpenClaw workflows in two ways:

1. **Workspace-native files** (Markdown blocks)
2. **Optional hooks/skills** (session start/stop, `/scan`, `/apply`, `/recall`)

No daemon required. It is just files + scripts.

---

## Recall (search memory like a human)

**Default: Local lexical recall (zero dependencies)**

Field-weighted TF-IDF ranking across decisions, tasks, entities, specs/docs. Fast and deterministic.

**Optional: Vector recall (pluggable)**

If you want semantic similarity search:
- local embeddings + local vector DB (recommended)
- or Pinecone (if you already run it)

Vector is optional — governance and integrity remain the same.

---

## Auto-capture (safe)

At session end, Mem OS can detect "decision-like" language and:
- generate proposals (not auto-write into DECISIONS/TASKS)
- flag unfiled decisions in SIGNALS
- keep the memory consistent without manual bookkeeping

All captured signals go through `/apply` before becoming formal blocks — no memory poisoning.

---

## Quick comparison

| Capability | Typical "memory plugin" | Mem OS for OpenClaw |
|---|---|---|
| Persist memory | Yes | Yes |
| Semantic recall | Yes (usually cloud) | Optional (local-first) |
| Auto-capture | Yes (auto-write) | Proposal-based (safe) |
| Contradictions / drift | No | Yes |
| Integrity validation | No | Yes |
| Safe apply + rollback | No | Yes |
| Audit trail | Rare | Yes |
| Mode governance | No | Yes |
| Local-only operation | Sometimes | Yes |

---

## Quick Start

### 1. Clone into your OpenClaw workspace

```bash
cd /path/to/your/openclaw/workspace
git clone https://github.com/star-ga/mem-os.git .mem-os
```

### 2. Initialize memory structure

```bash
python3 .mem-os/scripts/init_workspace.py .
```

This scaffolds all directories, copies templates, and creates `mem-os.json`. Never overwrites existing files.

### 3. Run your first integrity scan

```bash
python3 maintenance/intel_scan.py .
```

You should see `0 critical | 0 warnings` on a fresh workspace.

### 4. Validate structure

```bash
bash maintenance/validate.sh .
```

80+ structural checks. All should pass on a fresh init.

### 5. Add skills to OpenClaw config (optional)

Copy the skills into your OpenClaw skills directory:

```bash
cp -r .mem-os/skills/* .claude/skills/ 2>/dev/null || true
```

This gives you `/scan`, `/apply`, and `/recall` commands.

### 6. Add hooks (optional)

Add to your `.claude/hooks.json` or merge with existing:

```json
{
  "hooks": [
    {
      "event": "SessionStart",
      "command": "bash .mem-os/hooks/session-start.sh"
    },
    {
      "event": "Stop",
      "command": "bash .mem-os/hooks/session-end.sh"
    }
  ]
}
```

### 7. Verify it works

```bash
python3 scripts/recall.py --query "test" --workspace .
# Should return: No results found. (empty workspace)

python3 scripts/capture.py .
# Should return: capture: no daily log for YYYY-MM-DD, nothing to scan
```

You're live. Start in `detect_only` mode for the first week, then move to `propose`.

---

## Commands

- `/scan` — Run integrity scan (contradictions, drift, dead decisions, impact graph)
- `/apply` — Review and apply proposals from scan results
- `/recall` — Search across all memory files

---

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
    ├── intel_scan.py         # Integrity scanner
    ├── apply_engine.py       # Proposal apply engine
    ├── block_parser.py       # Markdown block parser
    └── validate.sh           # Structural validator
```

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

---

## Governance modes (recommended rollout)

1. **detect_only** — Scan + validate + report only. Start here.
2. **propose** — Generate fix proposals into `intelligence/proposed/` (no auto-apply). Move here after a clean observation week.
3. **enforce** — Bounded auto-supersede and self-healing within invariant constraints. Production mode.

---

## Configuration

See `mem-os.example.json` for all options:

- `auto_capture` — Run capture engine on session end (default: true)
- `auto_recall` — Enable recall on session start (default: true)
- `self_correcting_mode` — "detect_only", "propose", or "enforce"
- `recall.backend` — "tfidf" (default) or "vector" (requires recall_vector.py)
- `recall.vector` — Vector backend config (provider, model, url, collection)
- `proposal_budget` — Limits on auto-generated proposals per run/day
- `scan_schedule` — "daily" or "manual"

## Requirements

- Python 3.8+
- Bash (for hooks and validate.sh)
- No external packages required

## License

MIT License. Copyright 2026 STARGA Inc.
