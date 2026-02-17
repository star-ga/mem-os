# Mem-OS Research Task for GPT-5.2

## Your Role

You are a retrieval systems researcher. Your job is to deeply analyze the Mem-OS codebase and produce a concrete, prioritized improvement plan to push LoCoMo benchmark accuracy from 67.3% toward 75%+ (matching Memobase at 75.8%).

**Output format:** A single Markdown document at `/home/n/mem-os/RESEARCH_RESULTS.md` with all findings.

## Current State

Mem-OS is a deterministic memory system for AI agents. No embeddings, no vector DB, no LLM in the retrieval loop. Pure BM25 + rule-based reranking + context packing.

### Current Benchmark (v1.0.1, LoCoMo, N=1986, gpt-4o-mini judge)

| Category | N | Acc≥50 | Mean Score |
|---|--:|--:|--:|
| **Overall** | **1986** | **67.3%** | **61.4** |
| Open-domain | 841 | 86.6% | 78.3 |
| Temporal | 96 | 78.1% | 65.7 |
| Single-hop | 282 | 68.8% | 59.1 |
| Multi-hop | 321 | 55.5% | 48.4 |
| Adversarial | 446 | 36.3% | 39.5 |

### Competitors

| System | Acc≥50 | Approach |
|---|--:|---|
| Memobase | 75.8% | Specialized extraction |
| Letta | 74.0% | Files + agent tool use |
| Mem0 | 68.5% | Graph + LLM extraction |
| **Mem-OS** | **67.3%** | BM25 + deterministic rerank + context packing |

### Constraints (HARD — do not violate)

1. **No LLM in the retrieval loop.** Retrieval must be deterministic and fast. LLM is only used downstream (answerer + judge).
2. **No cloud calls during retrieval.** Everything must work offline and local-first.
3. **No embeddings required.** Optional vector recall exists but the core pipeline must work without it.
4. **Zero external dependencies for core.** stdlib Python only. No numpy, no torch, no transformers in the core path.
5. **Backward compatible.** Existing workspaces with `mem-os.json` must keep working.

## Key Files to Read (IN THIS ORDER)

Read these files carefully before producing any recommendations:

### Retrieval Pipeline (read all)
1. `scripts/recall.py` — Main recall engine. BM25F scoring, query expansion, reranking, context packing. **This is the most important file.**
2. `scripts/sqlite_index.py` — FTS5 backend for fast indexing
3. `scripts/evidence_packer.py` — Formats retrieved chunks into evidence for the answerer LLM
4. `scripts/extractor.py` — Structured extraction from conversation text
5. `scripts/observation_compress.py` — Observation compression layer

### Benchmark Pipeline (read all)
6. `benchmarks/locomo_judge.py` — Full judge pipeline: ingest → recall → answer → judge
7. `benchmarks/locomo_harness.py` — Retrieval-only harness (R@K metrics)
8. `benchmarks/REPORT_v1.0.1.md` — Detailed v1.0.1 results and architecture description

### Supporting (skim)
9. `scripts/block_parser.py` — Block format parser
10. `scripts/capture.py` — Auto-capture patterns
11. `mcp_server.py` — MCP tool definitions
12. `README.md` — Feature overview and architecture

## Research Questions (answer ALL of these)

### 1. Error Analysis (MOST IMPORTANT)

Sample and analyze 20-30 failure cases across the weak categories:
- **Adversarial (36.3%):** What patterns cause failures? Are they retrieval failures (wrong chunks) or answering failures (right chunks, wrong answer)?
- **Multi-hop (55.5%):** Does the 2-hop graph boost help? Are multi-hop failures from missing the second hop, or from retrieving both hops but failing to connect them?
- **Single-hop (68.8%):** What's the long tail of failures here?

For each failure, classify it:
- **Retrieval miss:** Correct chunk not in top-10
- **Retrieval noise:** Correct chunk present but drowned in irrelevant results
- **Packing failure:** Right chunks retrieved but evidence formatted poorly
- **Answerer failure:** Perfect retrieval, LLM still got it wrong
- **Adversarial trap:** Question is designed to mislead; system falls for the trap

### 2. Retrieval Architecture Analysis

Read `recall.py` deeply and answer:
- What is the BM25F field weighting? Is it optimal?
- How does query expansion work? What synonyms/morphs are added?
- How does the reranker combine its 5 signals? Are the weights tuned or hardcoded?
- What does context packing actually do? Does it help or hurt for adversarial queries?
- Is the top-200 → top-10 rerank ratio optimal? Would top-500 help?
- Does the FTS5 backend (sqlite_index.py) lose information vs the in-memory scan?

### 3. Adversarial Defense Deep Dive

Adversarial at 36.3% is the biggest gap. Research:
- What does LoCoMo's adversarial category actually test? (Read the dataset structure)
- How does the current `morph_only` gating work for adversarial queries?
- What adversarial-specific techniques exist in the literature for conversational memory?
- Could negation detection help? (e.g., "Did X NOT happen?" → retrieve X, then negate)
- Could temporal contradiction detection help? (e.g., "Did X change their mind about Y?")
- What would a "skeptical retrieval" mode look like?

### 4. Multi-Hop Improvement Strategies

Multi-hop at 55.5% is the second biggest gap. Research:
- How does the current 2-hop graph boost work? Is it actually firing?
- Would chain-of-retrieval help? (Retrieve for hop 1 → extract entities → retrieve for hop 2)
- Could entity co-occurrence indexing improve multi-hop? (Pre-compute which entities appear together)
- What's the overlap between multi-hop failures and adversarial failures?

### 5. Evidence Packing Optimization

Read `evidence_packer.py` and answer:
- How are chunks formatted for the answerer LLM?
- Does the packing order matter? (Chronological vs relevance-sorted vs interleaved)
- Is there a token budget? What happens when retrieved chunks exceed it?
- Could structured evidence (tables, timelines) help the answerer?

### 6. Competitive Technique Analysis

Research what Memobase, Letta, and Mem0 do differently:
- **Memobase (75.8%):** What is "specialized extraction"? Can we approximate it deterministically?
- **Letta (74.0%):** What does "files + agent tool use" mean for retrieval? Does Letta do iterative retrieval?
- **Mem0 (68.5%):** What does the knowledge graph add on top of basic retrieval?

Search for their papers, blog posts, or open-source code. Focus on techniques we could adapt without violating our constraints.

### 7. Low-Hanging Fruit

Identify 3-5 changes that could each add +1-3pp with minimal code changes:
- Query preprocessing improvements
- BM25 parameter tuning (k1, b values)
- Reranker weight optimization
- Context packing rule additions
- Evidence formatting changes

### 8. Architecture-Level Changes

Propose 2-3 larger changes (each might add +3-5pp) that stay within constraints:
- Would a TF-IDF reranker outperform the current feature-based reranker?
- Would pre-computed inverted indexes for entities/speakers/dates help?
- Would a "query decomposition" step (split multi-hop into sub-queries) help?
- Would conversation summarization at ingest time help recall?

## Output Format

Write `/home/n/mem-os/RESEARCH_RESULTS.md` with this structure:

```markdown
# Mem-OS Retrieval Research Results

## Executive Summary
[2-3 paragraphs: key findings, biggest opportunities, recommended priority order]

## 1. Error Analysis
### Adversarial Failures (N=XX analyzed)
[Failure classification breakdown, examples, patterns]

### Multi-Hop Failures (N=XX analyzed)
[Failure classification breakdown, examples, patterns]

### Single-Hop Failures (N=XX analyzed)
[Failure classification breakdown, examples, patterns]

## 2. Retrieval Architecture Analysis
[Findings from reading recall.py]

## 3. Adversarial Defense Recommendations
[Ranked list of techniques with expected impact]

## 4. Multi-Hop Improvement Recommendations
[Ranked list of techniques with expected impact]

## 5. Evidence Packing Analysis
[Findings and recommendations]

## 6. Competitive Analysis
[What we can learn from Memobase/Letta/Mem0]

## 7. Quick Wins (each +1-3pp)
[Numbered list with implementation sketch for each]

## 8. Architecture Changes (each +3-5pp)
[Numbered list with design sketch for each]

## 9. Recommended Implementation Order
[Prioritized roadmap: what to try first, expected cumulative gain]
```

## How to Run Error Analysis

To sample failures, you can run the benchmark on a single conversation:

```bash
cd /home/n/mem-os
source ~/.claude-ultimate/.env

# Quick dry run to see retrieval quality (no API calls)
python3 benchmarks/locomo_judge.py --dry-run --single-conv 4

# Run judge on one conversation (takes ~5 min with gpt-4o-mini)
python3 benchmarks/locomo_judge.py \
  --answerer-model gpt-4o-mini \
  --judge-model gpt-4o-mini \
  --top-k 10 \
  --single-conv 4 \
  -o benchmarks/research_conv4.json

# Analyze results
python3 -c "
import json
results = []
with open('benchmarks/research_conv4.json.conv4.jsonl') as f:
    for line in f:
        results.append(json.loads(line))

# Filter failures
failures = [r for r in results if r.get('judge_score', 0) < 50]
print(f'Total: {len(results)}, Failures: {len(failures)}')

# Group by category
from collections import Counter
cats = Counter(r.get('category', 'unknown') for r in failures)
print('Failure by category:', dict(cats))

# Print worst failures
for r in sorted(failures, key=lambda x: x.get('judge_score', 0))[:10]:
    print(f\"\\nScore: {r['judge_score']} | Cat: {r.get('category')} | Q: {r['question'][:100]}\")
    print(f\"  Gold: {r.get('gold_answer', '')[:100]}\")
    print(f\"  Got:  {r.get('answer', '')[:100]}\")
"
```

To inspect retrieval quality for specific questions:

```bash
cd /home/n/mem-os
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from recall import recall

# Example: check what recall returns for a specific query
results = recall('What did Alice say about her job?', workspace='.', top_k=10)
for i, r in enumerate(results):
    print(f'{i+1}. score={r[\"score\"]:.3f} | {r[\"text\"][:120]}')
"
```

## Important Notes

- **Do NOT modify any code.** This is a research task only. Output goes to RESEARCH_RESULTS.md.
- **Do NOT run the full 10-conversation benchmark.** That takes ~2 hours. Use single-conv runs or dry-runs for analysis.
- **Be specific.** Don't say "improve query expansion." Say "add irregular verb handling for 'went→go' pattern, which currently misses 12% of temporal queries."
- **Cite line numbers.** When referencing code, use `file.py:L123` format.
- **Stay within constraints.** Every recommendation must work without embeddings, without cloud calls, and with zero external dependencies.
- **Prioritize by expected impact per effort.** Quick wins first, architecture changes second.
