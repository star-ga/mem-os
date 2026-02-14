#!/usr/bin/env python3
"""mem-os Lexical Recall Engine (TF-IDF). Zero external deps.

Default recall backend: ranked keyword search using TF-IDF scoring
with field boosts and recency weighting. Fast, predictable, no deps.

For semantic recall (embeddings), see RecallBackend interface below.
Optional vector backends (Qdrant/Pinecone) can be plugged in via config.

Usage:
    python3 scripts/recall.py --query "authentication" --workspace "."
    python3 scripts/recall.py --query "auth" --workspace "." --json --limit 5
    python3 scripts/recall.py --query "deadline" --active-only
"""

import argparse
import json
import math
import os
import re
import sys
from abc import ABC, abstractmethod
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_parser import parse_file, get_active


# ---------------------------------------------------------------------------
# RecallBackend interface — plug in vector/semantic backends here
# ---------------------------------------------------------------------------

class RecallBackend(ABC):
    """Interface for recall backends. Default: TFIDFBackend (below).

    To add a vector backend:
    1. Implement this interface in recall_vector.py
    2. Set recall.backend = "vector" in mem-os.json
    3. recall.py will load it dynamically, falling back to TF-IDF on error.
    """

    @abstractmethod
    def search(self, workspace, query, limit=10, active_only=False):
        """Return list of {_id, type, score, excerpt, file, line, status}."""
        ...

    @abstractmethod
    def index(self, workspace):
        """(Re)build index from workspace files."""
        ...


# Fields to index for search (in priority order)
SEARCH_FIELDS = [
    "Statement", "Title", "Summary", "Description", "Context",
    "Rationale", "Tags", "Keywords", "Name", "Purpose",
    "RootCause", "Fix", "Prevention", "ProposedFix",
]

# Fields from ConstraintSignatures
SIG_FIELDS = ["subject", "predicate", "object", "domain"]

# Files to scan
CORPUS_FILES = {
    "decisions": "decisions/DECISIONS.md",
    "tasks": "tasks/TASKS.md",
    "projects": "entities/projects.md",
    "people": "entities/people.md",
    "tools": "entities/tools.md",
    "incidents": "entities/incidents.md",
    "contradictions": "intelligence/CONTRADICTIONS.md",
    "drift": "intelligence/DRIFT.md",
    "signals": "intelligence/SIGNALS.md",
}


def tokenize(text):
    """Split text into lowercase tokens."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def extract_text(block):
    """Extract searchable text from a block."""
    parts = []
    for field in SEARCH_FIELDS:
        val = block.get(field, "")
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(v) for v in val)

    # Extract from ConstraintSignatures
    for sig in block.get("ConstraintSignatures", []):
        for sf in SIG_FIELDS:
            val = sig.get(sf, "")
            if isinstance(val, str):
                parts.append(val)

    return " ".join(parts)


def get_excerpt(block, max_len=120):
    """Get a short excerpt from a block."""
    for field in ("Statement", "Title", "Summary", "Description", "Name", "Context"):
        val = block.get(field, "")
        if isinstance(val, str) and val:
            return val[:max_len]
    return block.get("_id", "?")


def get_block_type(block_id):
    """Infer block type from ID prefix."""
    prefixes = {
        "D-": "decision", "T-": "task", "PRJ-": "project",
        "PER-": "person", "TOOL-": "tool", "INC-": "incident",
        "C-": "contradiction", "DREF-": "drift", "SIG-": "signal",
        "P-": "proposal", "I-": "impact",
    }
    for prefix, btype in prefixes.items():
        if block_id.startswith(prefix):
            return btype
    return "unknown"


def date_score(block):
    """Boost recent blocks. Returns 0.0-1.0."""
    date_str = block.get("Date", "")
    if not date_str:
        return 0.5
    try:
        from datetime import datetime
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        now = datetime.utcnow()
        days_old = (now - d).days
        if days_old <= 0:
            return 1.0
        return max(0.1, 1.0 - (days_old / 365))
    except (ValueError, TypeError):
        return 0.5


def recall(workspace, query, limit=10, active_only=False):
    """Search across all memory files. Returns ranked results."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Load all blocks with source file tracking
    all_blocks = []
    for label, rel_path in CORPUS_FILES.items():
        path = os.path.join(workspace, rel_path)
        if not os.path.isfile(path):
            continue
        blocks = parse_file(path)
        if active_only:
            blocks = get_active(blocks)
        for b in blocks:
            b["_source_file"] = rel_path
            b["_source_label"] = label
            all_blocks.append(b)

    if not all_blocks:
        return []

    # Build inverted index (term -> list of block indices)
    doc_tokens = []
    for block in all_blocks:
        text = extract_text(block)
        tokens = tokenize(text)
        doc_tokens.append(tokens)

    # Document frequency
    df = Counter()
    for tokens in doc_tokens:
        unique = set(tokens)
        for t in unique:
            df[t] += 1

    N = len(all_blocks)
    results = []

    for i, block in enumerate(all_blocks):
        tokens = doc_tokens[i]
        if not tokens:
            continue

        tf = Counter(tokens)
        score = 0.0

        for qt in query_tokens:
            if qt in tf:
                # TF-IDF score
                term_freq = tf[qt] / len(tokens)
                idf = math.log((N + 1) / (df.get(qt, 0) + 1))
                score += term_freq * idf

        if score <= 0:
            continue

        # Boost factors
        recency = date_score(block)
        score *= (0.7 + 0.3 * recency)

        # Boost active status
        status = block.get("Status", "")
        if status == "active":
            score *= 1.2
        elif status in ("todo", "doing"):
            score *= 1.1

        # Priority boost
        priority = block.get("Priority", "")
        if priority in ("P0", "P1"):
            score *= 1.1

        results.append({
            "_id": block.get("_id", "?"),
            "type": get_block_type(block.get("_id", "")),
            "score": round(score, 4),
            "excerpt": get_excerpt(block),
            "file": block.get("_source_file", "?"),
            "line": block.get("_line", 0),
            "status": status,
        })

    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def _load_backend(workspace):
    """Load recall backend from config. Falls back to TF-IDF."""
    config_path = os.path.join(workspace, "mem-os.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            backend = cfg.get("recall", {}).get("backend", "tfidf")
            if backend == "vector":
                try:
                    from recall_vector import VectorBackend
                    return VectorBackend(cfg.get("recall", {}))
                except ImportError:
                    pass  # fall through to TF-IDF
        except Exception:
            pass
    return None  # use built-in TF-IDF


def main():
    parser = argparse.ArgumentParser(description="mem-os Lexical Recall Engine")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    parser.add_argument("--active-only", action="store_true", help="Only search active blocks")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Try vector backend first, fall back to TF-IDF
    backend = _load_backend(args.workspace)
    if backend:
        try:
            results = backend.search(args.workspace, args.query, args.limit, args.active_only)
        except Exception:
            results = recall(args.workspace, args.query, args.limit, args.active_only)
    else:
        results = recall(args.workspace, args.query, args.limit, args.active_only)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No results found.")
        else:
            for r in results:
                print(f"[{r['score']:.3f}] {r['_id']} ({r['type']}) — {r['excerpt'][:80]}")
                print(f"        {r['file']}:{r['line']}")


if __name__ == "__main__":
    main()
