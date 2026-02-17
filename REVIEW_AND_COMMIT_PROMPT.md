# Mem-OS 1.0 Review & Commit Task

## Context

A previous session implemented all 8 fixes from a critical code review to bring mem-os to genuine 1.0 quality. All 391 tests pass. Nothing has been committed yet — all changes are unstaged.

## What Was Implemented (8 fixes)

### Fix 1: WAL Wired Into Apply Engine
- `scripts/apply_engine.py` — WAL already existed in `backup_restore.py` but wasn't used during applies. Now every op in `apply_proposal()` calls `wal.begin()` before mutation, `wal.commit()` on success, `wal.rollback()` on failure. On startup, `wal.replay()` recovers from prior crashes.

### Fix 2: recall_vector.py Created (682 lines)
- **NEW FILE**: `scripts/recall_vector.py` — full vector recall backend with 3 providers:
  - `local`: sentence-transformers embeddings + JSON index (zero external deps for the index itself)
  - `qdrant`: Qdrant vector DB
  - `pinecone`: Pinecone vector DB
- CLI with `--index` and `--query` modes
- Optional dependency: `pip install mem-os[embeddings]`

### Fix 3: pyproject.toml Entry Points + __init__.py
- `pyproject.toml` — added 4 new entry points: `mem-os-migrate`, `mem-os-backup`, `mem-os-compact`, `mem-os-resolve`
- `scripts/__init__.py` — proper package docstring with `__version__ = "1.0.0"` and module listing
- Keywords updated: "self-correcting" → "governance-aware"

### Fix 4: Workspace-Wide Lock in Apply Engine
- `scripts/apply_engine.py` — `FileLock` (from project's own `scripts/filelock.py`, not third-party) wraps the entire apply pipeline via `_get_workspace_lock_path()` + `_apply_proposal_locked()`. 30-second timeout. Prevents concurrent applies from corrupting state.

### Fix 5: gpt-4o-mini Benchmark Results
- 7/10 conversations complete (1347/1986 questions) with gpt-4o-mini as both answerer and judge
- Result: 37.5% accuracy — directly comparable to Mem0 (68.5%) and Letta (74.0%)
- README updated with honest framing: BM25 retrieval is the bottleneck, Mem-OS value is in governance
- Benchmark result files: `benchmarks/locomo_judge_results_4omini.json.conv{0-6}.jsonl`

### Fix 6: Namespace ACL Wired Into recall.py and apply_engine.py
- `scripts/recall.py` — added `agent_id` parameter; filters corpus files by ACL, also searches agent-private namespace `agents/{agent_id}/...`
- `scripts/apply_engine.py` — added `agent_id` parameter to `apply_proposal()`; checks `ns.can_write()` for every target file before executing

### Fix 7: Renamed "self-correcting" → "governance"
- `self_correcting_mode` → `governance_mode` across ~17 files
- Schema version bumped 2.0.0 → 2.1.0 with idempotent migration `_migrate_v2_to_v21()`
- `_get_mode()` reads both old and new field names for backward compat
- All references in README, templates, hooks, tests, plugin config updated

### Fix 8: Concurrent Integration Tests (22 tests, 1142 lines)
- **NEW FILE**: `tests/test_concurrent_integration.py` — 8 test classes:
  - `TestConcurrentApply` — parallel applies, lock contention
  - `TestPartialFailureRollback` — mid-apply crash, state consistency
  - `TestWALCrashRecovery` — WAL replay after simulated crash
  - `TestConcurrentRecall` — parallel recall queries
  - `TestFileLockContention` — lock timeout, stale lock cleanup
  - `TestApplyDuringRecall` — reader-writer isolation
  - `TestPostCheckFailureRollback` — post-check abort rollback
  - `TestSnapshotRestoreFidelity` — backup/restore round-trip

## Your Task: Review, Fix Issues, Commit

### Step 1: Run Full Test Suite
```bash
cd /home/n/mem-os && python3 -m pytest tests/ -q
```
Verify 391 tests pass. If any fail, fix them.

### Step 2: Review Critical Issues to Fix

**Issue A: "Zero Dependencies" claim is now misleading**
- The README badge says "Zero Dependencies" and many sections repeat this claim
- `recall_vector.py` requires `sentence-transformers` (optional dep, OK)
- `filelock.py` is the project's own stdlib-based implementation (OK)
- But verify: does `apply_engine.py`'s `from filelock import FileLock` resolve to `scripts/filelock.py`? The import works because `scripts/` is on `sys.path` — confirm this is reliable
- If the zero-deps claim holds (all deps are optional), keep it. If not, update the claim.

**Issue B: Incomplete gpt-4o-mini benchmark (7/10 conversations)**
- Conversations 7, 8, 9 are missing. Check if result files exist:
  ```bash
  ls benchmarks/locomo_judge_results_4omini.json.conv{7,8,9}.jsonl
  ```
- If they exist now, re-aggregate and update README with full 1986-question numbers
- If they don't exist, the README already says "1347/1986 questions" — this is fine for now
- To run missing conversations (each takes ~10-20 min with gpt-4o-mini):
  ```bash
  source ~/.claude-ultimate/.env
  python3 benchmarks/locomo_judge.py --answerer-model gpt-4o-mini --judge-model gpt-4o-mini --top-k 10 --single-conv 7 -o benchmarks/locomo_judge_results_4omini.json
  # repeat for conv 8, 9
  ```

**Issue C: Verify schema migration actually works**
```bash
cd /home/n/mem-os
python3 -c "
import tempfile, json, os, shutil
# Create a fake v2.0 workspace
ws = tempfile.mkdtemp()
os.makedirs(os.path.join(ws, 'memory'))
with open(os.path.join(ws, 'mem-os.json'), 'w') as f:
    json.dump({'schema_version': '2.0.0', 'self_correcting_mode': 'detect_only'}, f)
with open(os.path.join(ws, 'memory/intel-state.json'), 'w') as f:
    json.dump({'self_correcting_mode': 'detect_only'}, f)

import sys; sys.path.insert(0, 'scripts')
from schema_version import ensure_schema_version
ensure_schema_version(ws)

with open(os.path.join(ws, 'mem-os.json')) as f:
    cfg = json.load(f)
with open(os.path.join(ws, 'memory/intel-state.json')) as f:
    st = json.load(f)
print('config:', cfg)
print('state:', st)
assert cfg.get('governance_mode') == 'detect_only', 'Migration failed for config'
assert st.get('governance_mode') == 'detect_only', 'Migration failed for state'
assert 'self_correcting_mode' not in cfg, 'Old key still in config'
assert 'self_correcting_mode' not in st, 'Old key still in state'
print('Migration OK')
shutil.rmtree(ws)
"
```

**Issue D: recall_vector.py — verify it's properly importable**
```bash
cd /home/n/mem-os
python3 -c "
import sys; sys.path.insert(0, 'scripts')
# Should import without error even without sentence-transformers
try:
    import recall_vector
    print('Import OK, classes:', dir(recall_vector))
except ImportError as e:
    if 'sentence_transformers' in str(e):
        print('OK - graceful ImportError for optional dep')
    else:
        raise
"
```

### Step 3: Check for Remaining Stale References
```bash
cd /home/n/mem-os
# Should find ZERO matches (all should be renamed to governance_mode)
grep -rn "self_correcting_mode" scripts/ tests/ templates/ hooks/ skills/ --include="*.py" --include="*.json" --include="*.sh" --include="*.md" | grep -v __pycache__ | grep -v ".pyc"
```
If any remain, rename them.

### Step 4: Aggregate Benchmark Results (if conv7-9 exist)
```bash
cd /home/n/mem-os
python3 -c "
import json, glob
files = sorted(glob.glob('benchmarks/locomo_judge_results_4omini.json.conv*.jsonl'))
total = correct = 0
for f in files:
    with open(f) as fh:
        for line in fh:
            r = json.loads(line)
            total += 1
            if r.get('judge_score', 0) >= 50:
                correct += 1
print(f'Files: {len(files)}, Questions: {total}, Correct: {correct}, Accuracy: {correct/total*100:.1f}%')
"
```

### Step 5: Commit Everything

Stage all modified and new files (NOT benchmark result .jsonl files — those are large data):

```bash
cd /home/n/mem-os

# Stage code changes
git add scripts/apply_engine.py scripts/recall.py scripts/recall_vector.py \
       scripts/schema_version.py scripts/__init__.py \
       pyproject.toml README.md package.json \
       .claude-plugin/plugin.json \
       hooks/session-start.sh \
       mem-os.example.json \
       templates/intel-state.json \
       scripts/intel_scan.py scripts/init_workspace.py \
       skills/integrity-scan/SKILL.md \
       tests/test_apply_engine.py tests/test_mcp_server.py \
       tests/test_concurrent_integration.py \
       benchmarks/locomo_judge.py

# Do NOT stage benchmark result .jsonl files (large data, keep in .gitignore)

# Commit
git commit --author="STARGA Inc <noreply@star.ga>" -m "Implement all 8 critical review fixes for 1.0 release

- Wire WAL crash recovery into apply pipeline (begin/commit/rollback per op)
- Create recall_vector.py: semantic search with local/Qdrant/Pinecone backends
- Add 4 CLI entry points (migrate, backup, compact, resolve) and fix __init__.py
- Add workspace-wide FileLock to prevent concurrent apply corruption
- Update LoCoMo LLM-as-judge benchmarks with gpt-4o-mini (37.5%, 1347 questions)
- Wire namespace ACL into recall.py and apply_engine.py (agent_id filtering)
- Rename self_correcting_mode to governance_mode with v2.0->v2.1 migration
- Add 22 concurrent integration tests (lock contention, WAL recovery, rollback)

391 tests passing. Schema version 2.1.0."
```

### Step 6: Verify
```bash
git log --oneline -3
git status
python3 -m pytest tests/ -q  # one more run to be safe
```

## Important Notes

- **Git author**: STARGA Inc <noreply@star.ga> — NO co-author lines, NO AI mentions
- **Do NOT stage** benchmark `.jsonl` result files (they're large data artifacts)
- **Do NOT push** — just commit locally
- The `.gitignore` may need a line for `benchmarks/*.jsonl` if not already there
- If any test fails, fix the root cause, don't skip the test
