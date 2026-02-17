# Changelog

All notable changes to Mem-OS are documented in this file.

## v10_full10_validated (2026-02-17)

**Full 10-conv LoCoMo validated: 67.3% Acc>=50 (+9.1pp over v3)**

This release represents a generational improvement in Mem-OS retrieval quality, moving from keyword search to a deterministic reasoning pipeline.

### Benchmark Results

| Metric | v3 | v10 | Delta |
|---|---|---|---|
| Acc>=50 | 58.2% | **67.3%** | +9.1pp |
| Mean Score | 54.3 | **61.4** | +7.1 |
| Acc>=75 | 36.5% | **48.8%** | +12.3pp |

Per-category Acc>=50: Open-domain +10.8pp, Single-hop +12.8pp, Temporal +7.3pp, Multi-hop +6.9pp, Adversarial +5.6pp.

### Changes

#### Retrieval Pipeline (Phase D)
- Wide retrieval: increased candidate pool to top-200 before rerank
- Deterministic rerank with speaker-match, time-proximity, entity-overlap, bigram-coherence, and recency-decay signals
- Speaker-aware extraction and boosting

#### Recall Hardening (Phase E)
- Month name normalization (January→1, etc.)
- Irregular verb lemmatization (went→go, said→say, etc.)
- Controlled synonym expansion with domain-aware terms
- Context packing (append-only post-retrieval):
  - Rule 1: Dialog adjacency (question-answer pair recovery)
  - Rule 2: Multi-entity diversity enforcement
  - Rule 3: Pronoun rescue (antecedent recovery)

#### Adversarial Gating (Phase E.1)
- Verification-intent regex for broader adversarial detection
- `morph_only` expansion mode for adversarial queries (lemma + months, no semantic synonyms)
- Gated synonym expansion based on query type classification

#### Infrastructure
- SQLite FTS5 backend with scan fallback
- Safe tar restore with path traversal protection
- Enforced MCP token authentication for HTTP transport
- Minimal snapshot apply (O(touched), copy2)

### Tags

| Tag | Description |
|---|---|
| `v8_phaseD_wide_speaker_extractor` | Wide retrieval + speaker-aware rerank |
| `v9_phaseE_recall_hardening` | Month norm, irregular verbs, synonyms, context pack |
| `v9_1_adv_gate_expansion` | Adversarial synonym gating |
| `v10_full10_validated` | Full 10-conv validated (this release) |

---

## v3 (baseline)

Initial LoCoMo benchmark baseline.

- BM25F retrieval with Porter stemming
- Basic query expansion
- 58.2% Acc>=50 on full 10-conv (1986 questions)
