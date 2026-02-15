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
- [MCP Server](#mcp-server)
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

### Benchmark Results

Mem-OS recall engine evaluated on two standard long-term memory benchmarks. Zero dependencies, pure BM25 + Porter stemming + domain-aware query expansion.

**LongMemEval (ICLR 2025, 470 questions):**

| Category | N | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| **Overall** | **470** | **73.2%** | **85.3%** | **88.1%** | **0.784** |
| Multi-session | 121 | 83.5% | 95.9% | 95.9% | 0.885 |
| Temporal reasoning | 127 | 76.4% | 91.3% | 92.9% | 0.826 |
| Knowledge update | 72 | 80.6% | 88.9% | 91.7% | 0.844 |
| Single-session assistant | 56 | 82.1% | 89.3% | 89.3% | 0.847 |

**LoCoMo (Snap Research, 1986 questions):**

| Category | N | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| **Overall** | **1986** | **35.7%** | **58.5%** | **66.9%** | **0.453** |
| Multi-hop | 321 | 47.4% | 66.4% | 71.0% | 0.549 |
| Open-domain | 841 | 38.4% | 62.1% | 70.0% | 0.484 |

**Context:** These are pure retrieval metrics (no LLM judge). Mem0 reports 66.9–68.5% on LoCoMo via LLM-as-judge accuracy (graph variant). Letta's plain-file baseline scored 74.0% with gpt-4o-mini — demonstrating that simple storage + agentic tool use outperforms engineered retrieval pipelines on LoCoMo. Mem-OS's Markdown-file + BM25 approach is architecturally aligned with these high-performing baselines while adding integrity guarantees no other system provides.

Run benchmarks yourself: `python3 benchmarks/locomo_harness.py` or `python3 benchmarks/longmemeval_harness.py`

### Persistent Memory
Structured, validated, append-only decisions / tasks / entities / incidents with provenance and supersede chains.

### Immune System
Continuous integrity checking: contradictions, drift, dead decisions, orphan tasks, coverage scoring, regression detection.

### Safe Self-Correction
All changes flow through graduated modes: `detect_only` → `propose` → `enforce`. Apply engine with snapshot, receipt, DIFF, and automatic rollback on validation failure.

### BM25 Hybrid Recall
BM25 scoring with Porter stemming, domain-aware query expansion, field boosts, recency weighting, and optional graph-based cross-reference neighbor boosting. Zero dependencies. Fast and deterministic.

### Graph-Based Recall
Cross-reference neighbor boosting — when a keyword match is found, blocks that reference or are referenced by the match get boosted. Surfaces related decisions, tasks, and entities that share no keywords but are structurally connected. Zero dependencies.

### Vector Recall (optional)
Pluggable embedding backend — local (Qdrant + Ollama) or cloud (Pinecone). Falls back to BM25 when unavailable.

### Auto-Capture with Structured Extraction
Session-end hook detects decision/task language (26 patterns with confidence classification), extracts structured metadata (subject, object, tags), and writes to `SIGNALS.md` only. Never touches source of truth directly. All signals go through `/apply`. Supports batch scanning of recent logs.

### Concurrency Safety
Cross-platform advisory file locking (`fcntl`/`msvcrt`/atomic create) protects all concurrent write paths. Stale lock detection with PID-based cleanup. Zero dependencies.

### Compaction & GC
Automated workspace maintenance: archive completed blocks, clean up old snapshots, compact resolved signals, archive daily logs into yearly files. Configurable thresholds with dry-run mode.

### Observability
Structured JSON logging (via stdlib), in-process metrics counters, and timing context managers. All scripts emit machine-parseable events. Controlled via `MEM_OS_LOG_LEVEL` env var.

### Multi-Agent Namespaces & ACL
Workspace-level + per-agent private namespaces with JSON-based ACL. fnmatch pattern matching for agent policies. Shared fact ledger for cross-agent propagation with dedup and review gate.

### Automated Conflict Resolution
Graduated resolution pipeline: timestamp priority, confidence priority, scope specificity, manual fallback. Generates supersede proposals with integrity hashes. Human veto loop — never auto-applies without review.

### Write-Ahead Log (WAL) + Backup/Restore
Crash-safe writes via journal-based WAL. Full workspace backup (tar.gz), git-friendly JSONL export, selective restore with conflict detection and path traversal protection.

### Transcript JSONL Capture
Scans Claude Code / OpenClaw transcript files for user corrections, convention discoveries, bug fix insights, and architectural decisions. 16 transcript-specific patterns with role filtering and confidence classification.

### 74+ Structural Checks + 369 Unit Tests
`validate.sh` checks schemas, cross-references, ID formats, status values, supersede chains, ConstraintSignatures, and more. Backed by 369 pytest unit tests covering parser, recall (BM25 + stemming + expansion), capture (structured extraction + confidence), compaction, file locking, observability, namespaces, conflict resolution, WAL/backup, transcript capture, apply, intel_scan, schema migration, MCP server, and edge cases.

### Audit Trail
Every applied proposal logged with timestamp, receipt, and DIFF. Full traceability from signal → proposal → decision.

---

## Quick Start

Get from zero to validated workspace in under 3 minutes.

### 1. Clone

```bash
cd /path/to/your/project
git clone https://github.com/star-ga/mem-os.git .mem-os
```

### 2. Initialize workspace

```bash
python3 .mem-os/scripts/init_workspace.py .
```

Creates 12 directories, 19 template files, and `mem-os.json` config. **Never overwrites existing files.**

### 3. Validate

```bash
bash maintenance/validate.sh .
# or cross-platform:
python3 maintenance/validate_py.py .
```

Expected: `74 checks | 74 passed | 0 issues`. If you see an error about `mem-os.json`, you're running in the repo root instead of an initialized workspace.

### 4. First scan

```bash
python3 maintenance/intel_scan.py .
```

Expected: `0 critical | 0 warnings` on a fresh workspace.

### 5. Verify recall + capture

```bash
python3 maintenance/recall.py --query "test" --workspace .
# → No results found. (empty workspace — correct)

python3 maintenance/capture.py .
# → capture: no daily log for YYYY-MM-DD, nothing to scan (correct)
```

### 6. Add skills (optional)

```bash
cp -r .mem-os/skills/* .claude/skills/ 2>/dev/null || true
```

Gives you `/scan`, `/apply`, and `/recall` slash commands in Claude Code.

### 7. Add hooks (optional)

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

You're live. Start in `detect_only` for one week, then move to `propose`.

### Smoke Test (optional)

Run the full end-to-end verification:

```bash
bash .mem-os/scripts/smoke_test.sh
```

Creates a temp workspace, runs init → validate → scan → recall → capture → pytest, then cleans up. All 11 checks should pass.

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

> Note: validate.sh check count scales with data — fresh workspaces have 74 checks, populated workspaces have more. The 1 warning is expected (no weekly summaries yet). Additionally, 316 pytest unit tests cover all core modules.

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
├── mcp_server.py            # MCP server (FastMCP)
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
│   ├── proposed/            # Staged proposals + resolution proposals
│   │   ├── DECISIONS_PROPOSED.md
│   │   ├── TASKS_PROPOSED.md
│   │   ├── EDITS_PROPOSED.md
│   │   └── RESOLUTIONS_PROPOSED.md
│   ├── applied/             # Snapshot archives (rollback)
│   └── state/snapshots/     # State snapshots
│
├── shared/                  # Multi-agent shared namespace
│   ├── decisions/
│   ├── tasks/
│   ├── entities/
│   └── intelligence/
│       └── LEDGER.md        # Cross-agent fact ledger
│
├── agents/                  # Per-agent private namespaces
│   └── <agent-id>/
│       ├── decisions/
│       ├── tasks/
│       └── memory/
│
├── mem-os-acl.json          # Multi-agent access control
├── .mem-os-wal/             # Write-ahead log (crash recovery)
│
└── maintenance/
    ├── intel_scan.py         # Integrity scanner
    ├── apply_engine.py       # Proposal apply engine
    ├── block_parser.py       # Markdown block parser (typed)
    ├── recall.py             # Recall engine (BM25 + stemming + graph)
    ├── capture.py            # Auto-capture (26 patterns + structured extraction)
    ├── compaction.py         # Compaction/GC/archival engine
    ├── filelock.py           # Cross-platform advisory file locking
    ├── observability.py      # Structured JSON logging + metrics
    ├── namespaces.py         # Multi-agent namespace & ACL engine
    ├── conflict_resolver.py  # Automated conflict resolution pipeline
    ├── backup_restore.py     # WAL + backup/restore + JSONL export
    ├── transcript_capture.py # Transcript JSONL signal extraction
    ├── validate.sh           # Structural validator (bash, 74+ checks)
    └── validate_py.py        # Structural validator (Python, cross-platform)
```

---

## How It Compares

### Full Feature Matrix

Compared against every major memory solution for AI agents (as of 2026):

| Capability | [Mem0](https://github.com/mem0ai/mem0) | [Supermemory](https://supermemory.ai) | [claude-mem](https://github.com/thedotmack/claude-mem) | [Letta](https://www.letta.com) | [Zep](https://www.getzep.com) | [LangMem](https://github.com/langchain-ai) | [Cognee](https://www.cognee.ai) | [Graphlit](https://www.graphlit.com) | **Mem OS** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Recall & Search** | | | | | | | | | |
| Semantic recall (vector) | Cloud | Cloud | ChromaDB | Yes | Yes | Yes | Yes | Yes | **Optional (local/cloud)** |
| Lexical recall (keyword) | Filter | No | No | No | No | No | No | No | **BM25 with stemming + expansion** |
| Graph-based recall | Yes | No | No | No | Yes | No | Yes | Yes | **Yes (xref neighbor boost)** |
| Hybrid search | Partial | No | No | No | Yes | No | Yes | Yes | **BM25 + graph + optional vector** |
| **Memory Persistence** | | | | | | | | | |
| Structured memory | JSON | JSON | SQLite | Memory blocks | Graph | KV store | Graph | Graph | **Markdown blocks** |
| Entity tracking | Yes | Yes | No | Yes | Yes | Yes | Yes | Yes | **Yes (people/projects/tools)** |
| Temporal awareness | No | No | No | No | Yes | No | No | No | **Yes (date-indexed)** |
| Supersede chains | No | No | No | Yes | Yes | No | No | No | **Yes (never edit, supersede)** |
| Append-only logs | No | No | No | No | No | No | No | No | **Yes (daily logs)** |
| **Integrity & Safety** | | | | | | | | | |
| Contradiction detection | No | No | No | No | No | No | No | No | **Yes (ConstraintSignatures)** |
| Drift analysis | No | No | No | No | No | No | No | No | **Yes (dead decisions, orphans)** |
| Structural validation | No | No | No | No | No | No | No | No | **74+ checks + 369 tests** |
| Impact graph | No | No | No | No | No | No | No | No | **Yes (decision → task/entity)** |
| Coverage scoring | No | No | No | No | No | No | No | No | **Yes (% decisions enforced)** |
| Provenance gate | No | No | No | No | Partial | No | No | No | **Yes (no source = no claim)** |
| Multi-agent namespaces | No | No | No | Yes | No | No | No | No | **Yes (ACL + shared ledger)** |
| Conflict resolution | No | No | No | No | No | No | No | No | **Yes (graduated auto-resolve)** |
| WAL / crash recovery | No | No | No | No | No | No | No | No | **Yes (journal-based)** |
| Backup / restore | No | No | No | No | No | No | No | No | **Yes (tar.gz + JSONL export)** |
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
| MCP server | No | No | No | No | No | No | No | No | **Yes (FastMCP, stdio + HTTP)** |

### What Each Tool Does Best

| Tool | Strength | Trade-off |
|---|---|---|
| **Mem0** | Fast managed service, graph memory, multi-user scoping | Cloud-dependent, no integrity checking |
| **Supermemory** | Fastest retrieval (ms), auto-ingestion from Drive/Notion | Cloud-dependent, auto-writes without review |
| **claude-mem** | Purpose-built for Claude Code, ChromaDB vectors, lifecycle hooks | Requires ChromaDB + Express worker, no integrity |
| **Letta** | Self-editing memory blocks, sleep-time compute, 74% LoCoMo (plain-file baseline) | Full agent runtime (heavy), not just memory |
| **Zep** | Temporal knowledge graph, bi-temporal model, sub-second at scale | Cloud service, complex architecture |
| **LangMem** | Native LangChain/LangGraph integration | Tied to LangChain ecosystem |
| **Cognee** | Advanced chunking, web content bridging | Research-oriented, complex setup |
| **Graphlit** | Multimodal ingestion, semantic search, managed platform | Cloud-only, managed service |
| **Mem OS** | Integrity + self-correction + zero deps + local-first | BM25 + graph recall by default (vector optional) |

### The Gap Mem OS Fills

Every tool above does **storage + retrieval**. None of them answer:

- "Do any of my decisions contradict each other?"
- "Which decisions are active but nobody references anymore?"
- "Did I make a decision in chat that was never formalized?"
- "What's the downstream impact if I change this decision?"
- "Is my memory state structurally valid right now?"

**Mem OS focuses on memory governance and integrity — an area most memory systems do not address directly.**

### Why Plain Files Outperform Fancy Retrieval

Letta's August 2025 analysis showed that a plain-file baseline (full conversations stored as files + agent filesystem tools) scored **74.0% on LoCoMo** with gpt-4o-mini — beating Mem0's top graph variant at 68.5%. Key reasons:

- **LLMs excel at tool-based retrieval.** Agents can iteratively query/refine file searches better than single-shot vector retrieval that might miss subtle connections.
- **Benchmarks reward recall + reasoning over storage sophistication.** Strong judge LLMs handle the rest once relevant chunks are loaded.
- **Overhead hurts.** Specialized pipelines introduce failure modes (bad embeddings, chunking errors, stale indexes) that simple file access avoids.
- **For text-heavy agentic use cases, "how well the agent manages context" > "how smart the retrieval index is."**

Mem-OS's Markdown-file + BM25 approach is architecturally aligned with these findings — and adds integrity, governance, and self-correction that no plain-file baseline provides.

---

## Recall

### Default: BM25 Hybrid

```bash
python3 maintenance/recall.py --query "authentication" --workspace .
python3 maintenance/recall.py --query "auth" --json --limit 5 --workspace .
python3 maintenance/recall.py --query "deadline" --active-only --workspace .
```

BM25 scoring (k1=1.2, b=0.75) with Porter stemming, domain-aware query expansion, field boosts for recency, active status, and priority. Searches across all structured files. Zero dependencies.

**Query expansion:** Searching "auth" automatically expands to include "authentication", "login", "oauth", "jwt", "session". Domain-aware synonyms cover auth, database, API, deployment, testing, security, performance, and infrastructure terms.

**Stemming:** "queries" matches "query", "deployed" matches "deployment", "authenticating" matches "authentication". Simplified Porter stemmer with zero dependencies.

### Graph-Based (cross-reference neighbor boost)

```bash
python3 maintenance/recall.py --query "database" --graph --workspace .
```

Adds graph traversal to BM25: when a block matches your query, its 1-hop cross-reference neighbors also appear in results (tagged `[graph]`). This surfaces related blocks that share no keywords but are structurally connected via `AlignsWith`, `Dependencies`, `Supersedes`, `Sources`, ConstraintSignature scopes, and any other block ID mention.

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

Implement `RecallBackend` interface in `maintenance/recall_vector.py`. Falls back to BM25 automatically if vector backend is unavailable.

---

## Auto-Capture

```
Session end
    ↓
capture.py scans daily log (or --scan-all for batch)
    ↓
Detects decision/task language (26 patterns, 3 confidence levels)
    ↓
Extracts structured metadata (subject, object, tags)
    ↓
Classifies confidence (high/medium/low → P1/P2/P3)
    ↓
Writes to intelligence/SIGNALS.md ONLY
    ↓
User reviews signals
    ↓
/apply promotes to DECISIONS.md or TASKS.md
```

**Batch scanning:** `python3 maintenance/capture.py . --scan-all` scans the last 7 days of daily logs at once.

**Safety guarantee:** `capture.py` never writes to `decisions/` or `tasks/` directly. All signals must go through the apply engine to become formal blocks.

---

## Multi-Agent Memory

### Namespace Setup

```bash
python3 maintenance/namespaces.py workspace/ --init coder-1 reviewer-1
```

Creates `shared/` (visible to all) and `agents/coder-1/`, `agents/reviewer-1/` (private) directories with ACL config (`mem-os-acl.json`).

### Access Control

Each agent sees only its own namespace + shared. ACL supports exact match, fnmatch patterns, and wildcard fallback:

```json
{
  "default_policy": "read",
  "agents": {
    "coder-1": {"namespaces": ["shared", "agents/coder-1"], "write": ["agents/coder-1"], "read": ["shared"]},
    "reviewer-*": {"namespaces": ["shared"], "write": [], "read": ["shared"]},
    "*": {"namespaces": ["shared"], "write": [], "read": ["shared"]}
  }
}
```

### Shared Fact Ledger

High-confidence facts can be proposed to `shared/intelligence/LEDGER.md`, where they become visible to all agents after review. Append-only with dedup and file locking.

### Conflict Resolution

```bash
python3 maintenance/conflict_resolver.py workspace/ --analyze
python3 maintenance/conflict_resolver.py workspace/ --propose
```

Graduated resolution: confidence priority (ConstraintSignature delta >= 2) > scope specificity (field count delta >= 2) > timestamp priority (newer wins) > manual fallback. Proposals written to `intelligence/proposed/RESOLUTIONS_PROPOSED.md` for human review.

### Transcript Capture

```bash
python3 maintenance/transcript_capture.py workspace/ --transcript path/to/session.jsonl
python3 maintenance/transcript_capture.py workspace/ --scan-recent --days 3
python3 maintenance/transcript_capture.py workspace/ --scan-recent --role user
```

Scans Claude Code JSONL transcripts for user corrections ("never use X", "always do Y"), convention discoveries, bug fix insights, and architectural decisions. 16 patterns with confidence classification.

### Backup & Restore

```bash
python3 maintenance/backup_restore.py backup workspace/ --output backup.tar.gz
python3 maintenance/backup_restore.py export workspace/ --output export.jsonl
python3 maintenance/backup_restore.py restore workspace/ --input backup.tar.gz
python3 maintenance/backup_restore.py wal-replay workspace/
```

Full workspace backup, git-friendly JSONL export, selective restore with conflict detection, and WAL replay for crash recovery.

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
    "backend": "bm25"
  },
  "proposal_budget": {
    "per_run": 3,
    "per_day": 6,
    "backlog_limit": 30
  },
  "compaction": {
    "archive_days": 90,
    "snapshot_days": 30,
    "log_days": 180,
    "signal_days": 60
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
| `recall.backend` | `"bm25"` | `"bm25"` or `"vector"` |
| `recall.vector.provider` | — | Vector backend: `"qdrant"` or `"pinecone"` (optional) |
| `recall.vector.model` | — | Embedding model name (optional) |
| `recall.vector.url` | — | Vector DB endpoint (optional) |
| `proposal_budget.per_run` | `3` | Max proposals generated per scan |
| `proposal_budget.per_day` | `6` | Max proposals per day |
| `proposal_budget.backlog_limit` | `30` | Max pending proposals before pausing generation |
| `compaction.archive_days` | `90` | Archive completed blocks older than N days |
| `compaction.snapshot_days` | `30` | Remove apply snapshots older than N days |
| `compaction.log_days` | `180` | Archive daily logs older than N days into yearly files |
| `compaction.signal_days` | `60` | Remove resolved/rejected signals older than N days |
| `scan_schedule` | `"daily"` | `"daily"` or `"manual"` |

---

## MCP Server

Mem-OS ships with a [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes memory as resources and tools to any MCP-compatible client. For a step-by-step walkthrough, see the [Claude Desktop Setup Guide](docs/claude-desktop-setup.md).

### Install

```bash
pip install fastmcp
```

### Claude Desktop

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mem-os": {
      "command": "python3",
      "args": ["/path/to/mem-os/mcp_server.py"],
      "env": {"MEM_OS_WORKSPACE": "/path/to/your/workspace"}
    }
  }
}
```

### Cursor / Windsurf

Add to your MCP config (`.cursor/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "mem-os": {
      "command": "python3",
      "args": ["/path/to/mem-os/mcp_server.py"],
      "env": {"MEM_OS_WORKSPACE": "."}
    }
  }
}
```

### OpenClaw (Claude Code)

```bash
# stdio transport (default)
MEM_OS_WORKSPACE=/path/to/workspace python3 mcp_server.py

# HTTP transport (multi-client)
MEM_OS_WORKSPACE=/path/to/workspace python3 mcp_server.py --transport http --port 8765
```

### Resources (read-only)

| URI | Description |
|---|---|
| `mem-os://decisions` | Active decisions |
| `mem-os://tasks` | All tasks |
| `mem-os://entities/{type}` | Entities (projects, people, tools, incidents) |
| `mem-os://signals` | Auto-captured signals pending review |
| `mem-os://contradictions` | Detected contradictions |
| `mem-os://health` | Workspace health summary (block counts, metrics) |
| `mem-os://recall/{query}` | BM25 recall search results |
| `mem-os://ledger` | Shared fact ledger (multi-agent) |

### Tools

| Tool | Description |
|---|---|
| `recall` | Search memory with BM25 (query, limit, active_only) |
| `propose_update` | Propose a decision/task — writes to SIGNALS.md only, never source of truth |
| `approve_apply` | Apply a staged proposal (dry_run=True by default for safety) |
| `rollback_proposal` | Rollback an applied proposal by receipt timestamp (YYYYMMDD-HHMMSS) |
| `scan` | Run integrity scan (contradictions, drift, signals) |
| `list_contradictions` | List contradictions with auto-resolution analysis |

### Token Auth (HTTP)

For remote deployments, set a bearer token to protect the HTTP endpoint:

```bash
# Via environment variable
MEM_OS_TOKEN=your-secret python3 mcp_server.py --transport http --port 8765

# Via CLI argument
python3 mcp_server.py --transport http --port 8765 --token your-secret
```

### Auto-Discovery

Drop-in `.mcp.json` manifest lets MCP clients auto-discover the server:

```json
{
  "name": "mem-os",
  "version": "1.0.0",
  "server": {
    "command": "python3",
    "args": ["mcp_server.py"],
    "env": { "MEM_OS_WORKSPACE": "." }
  },
  "transport": "stdio"
}
```

### Safety Guarantees

- **`propose_update` never writes to DECISIONS.md or TASKS.md.** All proposals go to `intelligence/SIGNALS.md` and must be promoted via `/apply`.
- **`approve_apply` defaults to dry_run=True.** Agents must explicitly set `dry_run=False` to apply. Creates a snapshot before applying for rollback support.
- **All resources are read-only.** No MCP client can mutate source of truth through resources.
- **Namespace-aware.** Multi-agent workspaces scope resources by agent ACL.

### Tags

`persistent-memory` `governance` `append-only` `contradiction-safe` `audit-trail` `zero-dependencies` `local-first`

---

## Requirements

- **Python 3.8+**
- **Bash** (for hooks and validate.sh; optional — `validate_py.py` is the cross-platform alternative)
- **No external packages** — stdlib only

### Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | Full | Primary target |
| macOS | Full | POSIX-compliant shell scripts |
| Windows (WSL/Git Bash) | Full | Use WSL2 or Git Bash for shell hooks |
| Windows (native) | Python only | Use `validate_py.py` instead of `validate.sh`; hooks require WSL |

---

## Security

### Threat Model

| What we protect | How |
|---|---|
| Memory integrity | 74+ structural checks, ConstraintSignature validation |
| Accidental overwrites | Proposal-based mutations only (never direct writes to source of truth) |
| Rollback safety | Snapshot before every apply, atomic `os.replace()` for state files |
| Symlink attacks | Symlink detection in restore_snapshot (both SNAPSHOT_DIRS and intel subdirs) |
| Path traversal | All paths resolved via `os.path.abspath()`, workspace-relative only |

| What we do NOT protect against | Why |
|---|---|
| Malicious local user | Single-user CLI tool — if you have filesystem access, you own the data |
| Network attacks | No network calls, no listening ports, no telemetry |
| Encrypted storage | Files are plaintext Markdown — use disk encryption if needed |

### No Network Calls

Mem OS makes **zero network calls**. No telemetry, no phoning home, no cloud dependencies. All operations are local filesystem reads and writes. Verify with:

```bash
grep -rn "http\|socket\|urllib\|requests\|httpx" scripts/ | grep -v "^#\|\.pyc"
# → Should return nothing
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `validate.sh` says "No mem-os.json found" | You're running in the repo root, not a workspace. Run `init_workspace.py` first. |
| `validate.sh` shows FAIL on fresh init | Should not happen — run `bash scripts/smoke_test.sh` to verify. |
| `recall` returns no results | Workspace is empty. Add decisions/tasks first, then search. |
| `capture` says "no daily log" | No `memory/YYYY-MM-DD.md` file for today. Write something first. |
| `intel_scan` finds 0 contradictions | That's good — means no conflicting decisions. |
| Tests fail on Windows | Use `validate_py.py` instead of `validate.sh`. Hooks require WSL. |
| `pip install -e .` fails | Ensure Python 3.8+ and setuptools >= 64. |

---

## Contributing

Contributions welcome. Please open an issue first to discuss what you'd like to change.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE) — Copyright 2026 STARGA Inc.
