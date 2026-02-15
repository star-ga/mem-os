<p align="center">
  <h1 align="center">Mem OS</h1>
  <p align="center">
    <strong>Memory + Immune System for OpenClaw agents</strong>
  </p>
  <p align="center">
    Local-first &bull; Auditable &bull; Self-correcting
  </p>
  <p align="center">
    <a href="https://github.com/star-ga/mem-os/blob/main/LICENSE"><img src="https://img.shields.io/github/license/star-ga/mem-os?style=flat-square&color=blue" alt="License"></a>
    <a href="https://github.com/star-ga/mem-os/releases"><img src="https://img.shields.io/github/v/release/star-ga/mem-os?style=flat-square&color=green" alt="Release"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.8+">
    <img src="https://img.shields.io/badge/dependencies-zero-brightgreen?style=flat-square" alt="Zero Dependencies">
    <a href="https://github.com/star-ga/mem-os/stargazers"><img src="https://img.shields.io/github/stars/star-ga/mem-os?style=flat-square" alt="Stars"></a>
    <img src="https://img.shields.io/badge/OpenClaw-latest-purple?style=flat-square" alt="OpenClaw latest">
  </p>
</p>

---

Drop-in memory layer for [OpenClaw](https://github.com/anthropics/claude-code) (latest). Upgrades your agent from "chat history + notes" to a governed **Memory OS** with structured persistence, contradiction detection, drift analysis, safe self-correction, and full audit trail.

> **If your agent runs for weeks, it will drift. Mem OS prevents silent drift.**

### Trust Signals

| Principle | What it means |
|---|---|
| **Deterministic** | Same input → same output. No ML, no probabilistic mutations. |
| **Auditable** | Every apply logged with timestamp, receipt, and DIFF. Full traceability. |
| **Local-first** | All data stays on disk. No cloud calls, no telemetry, no phoning home. |
| **No vendor lock-in** | Plain Markdown files. Move to any system, any time. |
| **Zero magic** | Every check is a grep, every mutation is a file write. Read the source in 30 min. |
| **No silent mutation** | Nothing writes to source of truth without explicit `/apply`. Ever. |

---

## Table of Contents

- [Why Mem OS](#why-mem-os)
- [Features](#features)
- [Quick Start](#quick-start) (3 minutes)
- [Health Summary](#health-summary)
- [Commands](#commands)
- [Architecture](#architecture)
- [How It Compares](#how-it-compares)
- [Recall](#recall)
- [Auto-Capture](#auto-capture)
- [Governance Modes](#governance-modes)
- [Block Format](#block-format)
- [Specification](#specification)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Why Mem OS

Most memory plugins **store and retrieve**. That's table stakes.

Mem OS also **detects when your memory is wrong** — contradictions between decisions, drift from informal choices never formalized, dead decisions nobody references, orphan tasks pointing at nothing — and offers a safe path to fix it.

| Problem | What happens without Mem OS | What Mem OS does |
|---|---|---|
| Two decisions contradict each other | Agent follows whichever it saw last | Flags contradiction, links both, proposes resolution |
| Decision made in chat, never formalized | Lost after session ends | Auto-captured as signal, proposed for formalization |
| Old decision nobody follows anymore | Zombie decision confuses future sessions | Detected as "dead", flagged for supersede or archive |
| Task references deleted decision | Silent breakage | Caught as orphan reference in integrity scan |

---

## Features

### Persistent Memory
Structured, validated, append-only decisions / tasks / entities / incidents with provenance and supersede chains.

### Immune System
Continuous integrity checking: contradictions, drift, dead decisions, orphan tasks, coverage scoring, regression detection.

### Safe Self-Correction
All changes flow through graduated modes: `detect_only` → `propose` → `enforce`. Apply engine with snapshot, receipt, DIFF, and automatic rollback on validation failure.

### Lexical Recall
Field-weighted TF-IDF search across all memory. Zero dependencies. Fast and deterministic.

### Graph-Based Recall
Cross-reference neighbor boosting — when a keyword match is found, blocks that reference or are referenced by the match get boosted. Surfaces related decisions, tasks, and entities that share no keywords but are structurally connected. Zero dependencies.

### Vector Recall (optional)
Pluggable embedding backend — local (Qdrant + Ollama) or cloud (Pinecone). Falls back to TF-IDF when unavailable.

### Auto-Capture (safe)
Session-end hook detects decision-like language and writes to `SIGNALS.md` only. Never touches source of truth directly. All signals go through `/apply`.

### 74+ Structural Checks
`validate.sh` checks schemas, cross-references, ID formats, status values, supersede chains, ConstraintSignatures, and more.

### Audit Trail
Every applied proposal logged with timestamp, receipt, and DIFF. Full traceability from signal → proposal → decision.

---

## Quick Start

### 1. Clone

```bash
cd /path/to/your/openclaw/workspace
git clone https://github.com/star-ga/mem-os.git .mem-os
```

### 2. Initialize

```bash
python3 .mem-os/scripts/init_workspace.py .
```

Creates 12 directories, 19 template files, and `mem-os.json` config. **Never overwrites existing files.**

### 3. First scan

```bash
python3 maintenance/intel_scan.py .
```

Expected output: `0 critical | 0 warnings` on a fresh workspace.

### 4. Validate

```bash
bash maintenance/validate.sh .
```

74+ structural checks. All pass on fresh init.

### 5. Add skills (optional)

```bash
cp -r .mem-os/skills/* .claude/skills/ 2>/dev/null || true
```

Gives you `/scan`, `/apply`, and `/recall` commands.

### 6. Add hooks (optional)

Merge into your `.claude/hooks.json`:

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

### 7. Verify

```bash
python3 maintenance/recall.py --query "test" --workspace .
# → No results found. (empty workspace — correct)

python3 maintenance/capture.py .
# → capture: no daily log for YYYY-MM-DD, nothing to scan (correct)
```

You're live. Start in `detect_only` for one week, then move to `propose`.

---

## Health Summary

After setup, this is what a healthy workspace looks like:

```
$ python3 maintenance/intel_scan.py .

Mem OS Intelligence Scan Report v2.0
Mode: detect_only

=== 1. CONTRADICTION DETECTION ===
  OK: No contradictions found among 25 signatures.

=== 2. DRIFT ANALYSIS ===
  OK: All active decisions referenced or exempt.
  INFO: Metrics: active_decisions=17, active_tasks=7, blocked=0,
        dead_decisions=0, incidents=3, decision_coverage=100%

=== 3. DECISION IMPACT GRAPH ===
  OK: Built impact graph: 11 decision(s) with edges.

=== 4. STATE SNAPSHOT ===
  OK: Snapshot saved.

=== 5. WEEKLY BRIEFING ===
  OK: Briefing generated.

TOTAL: 0 critical | 0 warnings | 16 info
```

```
$ bash maintenance/validate.sh .

TOTAL: 74 checks | 74 passed | 0 issues | 1 warnings
```

> Note: Check count scales with data — fresh workspaces have 74 checks, populated workspaces have more. The 1 warning is expected (no weekly summaries yet).

---

## Commands

| Command | What it does |
|---|---|
| `/scan` | Run integrity scan — contradictions, drift, dead decisions, impact graph, snapshot, briefing |
| `/apply` | Review and apply proposals from scan results (dry-run first, then apply) |
| `/recall <query>` | Search across all memory files with ranked results (add `--graph` for cross-reference boosting) |

---

## Architecture

```
your-workspace/
├── mem-os.json              # Config
├── MEMORY.md                # Protocol rules
│
├── decisions/
│   └── DECISIONS.md         # Formal decisions [D-YYYYMMDD-###]
├── tasks/
│   └── TASKS.md             # Tasks [T-YYYYMMDD-###]
├── entities/
│   ├── projects.md          # [PRJ-###]
│   ├── people.md            # [PER-###]
│   ├── tools.md             # [TOOL-###]
│   └── incidents.md         # [INC-###]
│
├── memory/
│   ├── YYYY-MM-DD.md        # Daily logs (append-only)
│   ├── intel-state.json     # Scanner state + metrics
│   └── maint-state.json     # Maintenance state
│
├── summaries/
│   ├── weekly/              # Weekly summaries
│   └── daily/               # Daily summaries
│
├── intelligence/
│   ├── CONTRADICTIONS.md    # Detected contradictions
│   ├── DRIFT.md             # Drift detections
│   ├── SIGNALS.md           # Auto-captured signals
│   ├── IMPACT.md            # Decision impact graph
│   ├── BRIEFINGS.md         # Weekly briefings
│   ├── AUDIT.md             # Applied proposal audit trail
│   ├── SCAN_LOG.md          # Scan history
│   ├── proposed/            # Staged proposals
│   │   ├── DECISIONS_PROPOSED.md
│   │   ├── TASKS_PROPOSED.md
│   │   └── EDITS_PROPOSED.md
│   ├── applied/             # Snapshot archives (rollback)
│   └── state/snapshots/     # State snapshots
│
└── maintenance/
    ├── intel_scan.py         # Integrity scanner
    ├── apply_engine.py       # Proposal apply engine
    ├── block_parser.py       # Markdown block parser
    ├── recall.py             # Recall engine (TF-IDF + graph)
    ├── capture.py            # Auto-capture engine
    └── validate.sh           # Structural validator (74+ checks)
```

---

## How It Compares

### Full Feature Matrix

Compared against every major memory solution for AI agents (as of 2026):

| Capability | [Mem0](https://github.com/mem0ai/mem0) | [Supermemory](https://supermemory.ai) | [claude-mem](https://github.com/thedotmack/claude-mem) | [Letta](https://www.letta.com) | [Zep](https://www.getzep.com) | [LangMem](https://github.com/langchain-ai) | [Cognee](https://www.cognee.ai) | [Graphlit](https://www.graphlit.com) | **Mem OS** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Recall & Search** | | | | | | | | | |
| Semantic recall (vector) | Cloud | Cloud | ChromaDB | Yes | Yes | Yes | Yes | Yes | **Optional (local/cloud)** |
| Lexical recall (keyword) | Filter | No | No | No | No | No | No | No | **TF-IDF with field boosts** |
| Graph-based recall | Yes | No | No | No | Yes | No | Yes | Yes | **Yes (xref neighbor boost)** |
| Hybrid search | Partial | No | No | No | Yes | No | Yes | Yes | **TF-IDF + optional vector** |
| **Memory Persistence** | | | | | | | | | |
| Structured memory | JSON | JSON | SQLite | Memory blocks | Graph | KV store | Graph | Graph | **Markdown blocks** |
| Entity tracking | Yes | Yes | No | Yes | Yes | Yes | Yes | Yes | **Yes (people/projects/tools)** |
| Temporal awareness | No | No | No | No | Yes | No | No | No | **Yes (date-indexed)** |
| Supersede chains | No | No | No | Yes | Yes | No | No | No | **Yes (never edit, supersede)** |
| Append-only logs | No | No | No | No | No | No | No | No | **Yes (daily logs)** |
| **Integrity & Safety** | | | | | | | | | |
| Contradiction detection | No | No | No | No | No | No | No | No | **Yes (ConstraintSignatures)** |
| Drift analysis | No | No | No | No | No | No | No | No | **Yes (dead decisions, orphans)** |
| Structural validation | No | No | No | No | No | No | No | No | **74+ checks** |
| Impact graph | No | No | No | No | No | No | No | No | **Yes (decision → task/entity)** |
| Coverage scoring | No | No | No | No | No | No | No | No | **Yes (% decisions enforced)** |
| Provenance gate | No | No | No | No | Partial | No | No | No | **Yes (no source = no claim)** |
| **Self-Correction** | | | | | | | | | |
| Auto-capture | Auto-write | Auto-write | Auto-write | Self-edit | Auto-extract | Auto-extract | Auto-extract | Auto-ingest | **Proposal-based (safe)** |
| Proposal queue | No | No | No | No | No | No | No | No | **Yes (proposed/)** |
| Apply with rollback | No | No | No | No | No | No | No | No | **Yes (snapshot + DIFF)** |
| Mode governance | No | No | No | No | No | No | No | No | **3 modes** |
| Audit trail | No | Partial | No | No | No | No | No | No | **Full (every apply logged)** |
| **Operations** | | | | | | | | | |
| Local-only operation | No | No | Yes | No | No | No | No | No | **Yes** |
| Zero dependencies | No | No | No | No | No | No | No | No | **Yes (stdlib only)** |
| No daemon required | No | No | No | No | No | Yes | No | No | **Yes (just files + scripts)** |
| Git-friendly (plain text) | No | No | No | Partial | No | No | No | No | **Yes (all Markdown)** |
| OpenClaw native | No | Plugin | Plugin | No | No | Plugin | No | No | **Yes (hooks + skills)** |

### What Each Tool Does Best

| Tool | Strength | Trade-off |
|---|---|---|
| **Mem0** | Fast managed service, graph memory, multi-user scoping | Cloud-dependent, no integrity checking |
| **Supermemory** | Fastest retrieval (ms), auto-ingestion from Drive/Notion | Cloud-dependent, auto-writes without review |
| **claude-mem** | Purpose-built for Claude Code, ChromaDB vectors, lifecycle hooks | Requires ChromaDB + Express worker, no integrity |
| **Letta** | Self-editing memory blocks, sleep-time compute, skill learning | Full agent runtime (heavy), not just memory |
| **Zep** | Temporal knowledge graph, bi-temporal model, sub-second at scale | Cloud service, complex architecture |
| **LangMem** | Native LangChain/LangGraph integration | Tied to LangChain ecosystem |
| **Cognee** | Advanced chunking, web content bridging | Research-oriented, complex setup |
| **Graphlit** | Multimodal ingestion, semantic search, managed platform | Cloud-only, managed service |
| **Mem OS** | Integrity + self-correction + zero deps + local-first | Lexical + graph recall by default (vector optional) |

### The Gap Mem OS Fills

Every tool above does **storage + retrieval**. None of them answer:

- "Do any of my decisions contradict each other?"
- "Which decisions are active but nobody references anymore?"
- "Did I make a decision in chat that was never formalized?"
- "What's the downstream impact if I change this decision?"
- "Is my memory state structurally valid right now?"

**Mem OS focuses on memory governance and integrity — an area most memory systems do not address directly.**

---

## Recall

### Default: Lexical (TF-IDF)

```bash
python3 maintenance/recall.py --query "authentication" --workspace .
python3 maintenance/recall.py --query "auth" --json --limit 5 --workspace .
python3 maintenance/recall.py --query "deadline" --active-only --workspace .
```

Field-weighted TF-IDF with boosts for recency, active status, and priority. Searches across all structured files. Zero dependencies.

### Graph-Based (cross-reference neighbor boost)

```bash
python3 maintenance/recall.py --query "database" --graph --workspace .
```

Adds graph traversal to TF-IDF: when a block matches your query, its 1-hop cross-reference neighbors also appear in results (tagged `[graph]`). This surfaces related blocks that share no keywords but are structurally connected via `AlignsWith`, `Dependencies`, `Supersedes`, `Sources`, ConstraintSignature scopes, and any other block ID mention.

### Optional: Vector (pluggable)

Set in `mem-os.json`:

```json
{
  "recall": {
    "backend": "vector",
    "vector": {
      "provider": "qdrant",
      "model": "all-MiniLM-L6-v2",
      "url": "http://localhost:6333"
    }
  }
}
```

Implement `RecallBackend` interface in `maintenance/recall_vector.py`. Falls back to TF-IDF automatically if vector backend is unavailable.

---

## Auto-Capture

```
Session end
    ↓
capture.py scans daily log
    ↓
Detects decision-like language (16 patterns)
    ↓
Writes to intelligence/SIGNALS.md ONLY
    ↓
User reviews signals
    ↓
/apply promotes to DECISIONS.md or TASKS.md
```

**Safety guarantee:** `capture.py` never writes to `decisions/` or `tasks/` directly. All signals must go through the apply engine to become formal blocks.

---

## Governance Modes

| Mode | What it does | When to use |
|---|---|---|
| `detect_only` | Scan + validate + report only | **Start here.** First week after install. |
| `propose` | Report + generate fix proposals in `proposed/` | After a clean observation week with zero critical issues. |
| `enforce` | Bounded auto-supersede + self-healing within constraints | Production mode. Requires explicit opt-in. |

**Recommended rollout:**
1. Install → run in `detect_only` for 7 days
2. Review scan logs → if clean, switch to `propose`
3. Triage proposals for 2-3 weeks → if confident, enable `enforce`

---

## Block Format

All structured data uses a simple, parseable markdown format:

```markdown
[D-20260213-001]
Date: 2026-02-13
Status: active
Statement: Use PostgreSQL for the user database
Tags: database, infrastructure
Rationale: Better JSON support than MySQL for our use case
ConstraintSignatures:
- id: CS-db-engine
  domain: infrastructure
  subject: database
  predicate: engine
  object: postgresql
  modality: must
  priority: 9
  scope: {projects: [PRJ-myapp]}
  evidence: Benchmarked JSON performance
  axis:
    key: database.engine
  relation: standalone
  enforcement: structural
```

Blocks are parsed by `block_parser.py` — a zero-dependency markdown parser that extracts `[ID]` headers and `Key: Value` fields into structured dicts.

---

## Specification

For the formal grammar, invariant rules, state machine, and atomicity guarantees, see **[SPEC.md](SPEC.md)**.

Covers:
- Block grammar (EBNF)
- Proposal grammar
- ConstraintSignature grammar
- Mode state machine
- Apply atomicity guarantees
- Invariant lock rules

---

## Configuration

All settings in `mem-os.json` (created by `init_workspace.py`):

```json
{
  "version": "1.0.0",
  "workspace_path": ".",
  "auto_capture": true,
  "auto_recall": true,
  "self_correcting_mode": "detect_only",
  "recall": {
    "backend": "tfidf"
  },
  "proposal_budget": {
    "per_run": 3,
    "per_day": 6,
    "backlog_limit": 30
  },
  "scan_schedule": "daily"
}
```

| Key | Default | Description |
|---|---|---|
| `version` | `"1.0.0"` | Config schema version |
| `auto_capture` | `true` | Run capture engine on session end |
| `auto_recall` | `true` | Show recall context on session start |
| `self_correcting_mode` | `"detect_only"` | Governance mode |
| `recall.backend` | `"tfidf"` | `"tfidf"` or `"vector"` |
| `recall.vector.provider` | — | Vector backend: `"qdrant"` or `"pinecone"` (optional) |
| `recall.vector.model` | — | Embedding model name (optional) |
| `recall.vector.url` | — | Vector DB endpoint (optional) |
| `proposal_budget.per_run` | `3` | Max proposals generated per scan |
| `proposal_budget.per_day` | `6` | Max proposals per day |
| `proposal_budget.backlog_limit` | `30` | Max pending proposals before pausing generation |
| `scan_schedule` | `"daily"` | `"daily"` or `"manual"` |

---

## Requirements

- **Python 3.8+**
- **Bash** (for hooks and validate.sh)
- **No external packages** — stdlib only

### Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | Full | Primary target |
| macOS | Full | POSIX-compliant shell scripts |
| Windows (WSL/Git Bash) | Full | Use WSL2 or Git Bash for shell hooks |
| Windows (native) | Python only | Shell hooks require WSL; Python scripts work natively |

---

## Contributing

Contributions welcome. Please open an issue first to discuss what you'd like to change.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE) — Copyright 2026 STARGA Inc.
