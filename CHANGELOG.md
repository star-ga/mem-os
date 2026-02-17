# Changelog

All notable changes to Mem-OS are documented in this file.

## 1.0.2 (2026-02-17)

**Cross-platform CI hardening + professional polish**

Fixes all CI failures across Ubuntu, macOS, and Windows. Every platform × Python version combination now passes.

### Fixes

#### macOS
- Fix `/var` → `/private/var` symlink path traversal in apply engine and WAL — `os.path.realpath()` now resolves workspace paths at all entry points

#### Windows
- Skip bash-dependent tests (`validate.sh`) on Windows
- Fix `FileLock` repr test to use `tempfile.gettempdir()` instead of hardcoded `/tmp`
- Skip `test_lock_file_contains_pid` (PermissionError on open fd)
- Fix path separator in namespace corpus path assertions
- Add monotonic counter to WAL entry IDs (prevents Windows timestamp collision)

#### Thread Safety
- Rewrite `FileLock` with two-layer locking: `threading.Lock` for intra-process + `O_CREAT|O_EXCL` + `flock`/`msvcrt` for cross-process contention
- Stale lock detection with PID-based cleanup

#### CI
- Install `fastmcp>=2.0` in CI (fixes 30+ ModuleNotFoundError failures)
- Drop Python 3.8/3.9 from matrix (FastMCP requires 3.10+)
- Add `fail-fast: false` to prevent single-platform cancellation cascade
- Fix 2 unused variable lint errors in recall.py

#### Docs
- Update Python requirement to 3.10+ in README badge, requirements, and troubleshooting
- Add Claude Code MCP configuration section to README
- Update security section: `os.path.abspath()` → `os.path.realpath()`

---

## 1.0.1 (2026-02-17)

**Full 10-conv LoCoMo validated: 67.3% Acc>=50 (+9.1pp over 1.0.0)**

This release represents a generational improvement in Mem-OS retrieval quality, moving from keyword search to a deterministic reasoning pipeline.

### Benchmark Results

| Metric | 1.0.0 | 1.0.1 | Delta |
|---|---|---|---|
| Acc>=50 | 58.2% | **67.3%** | +9.1pp |
| Mean Score | 54.3 | **61.4** | +7.1 |
| Acc>=75 | 36.5% | **48.8%** | +12.3pp |

Per-category Acc>=50: Open-domain +10.8pp, Single-hop +12.8pp, Temporal +7.3pp, Multi-hop +6.9pp, Adversarial +5.6pp.

### Changes

#### Retrieval Pipeline
- Wide retrieval: increased candidate pool to top-200 before rerank
- Deterministic rerank with speaker-match, time-proximity, entity-overlap, bigram-coherence, and recency-decay signals
- Speaker-aware extraction and boosting

#### Recall Hardening
- Month name normalization (January->1, etc.)
- Irregular verb lemmatization (went->go, said->say, etc.)
- Controlled synonym expansion with domain-aware terms
- Context packing (append-only post-retrieval):
  - Rule 1: Dialog adjacency (question-answer pair recovery)
  - Rule 2: Multi-entity diversity enforcement
  - Rule 3: Pronoun rescue (antecedent recovery)

#### Adversarial Gating
- Verification-intent regex for broader adversarial detection
- `morph_only` expansion mode for adversarial queries (lemma + months, no semantic synonyms)
- Gated synonym expansion based on query type classification

#### Infrastructure
- SQLite FTS5 backend with scan fallback
- Safe tar restore with path traversal protection
- Enforced MCP token authentication for HTTP transport
- Minimal snapshot apply (O(touched), copy2)
- CI: install pytest in workflow, fix 92 ruff lint warnings

---

## 1.0.0

Initial release.

- BM25F retrieval with Porter stemming
- Basic query expansion
- 58.2% Acc>=50 on full 10-conv LoCoMo (1986 questions)
- Governance engine: contradiction detection, drift analysis, proposal queue
- Multi-agent namespaces with ACL
- MCP server with token auth
- WAL + backup/restore
- 478 unit tests
