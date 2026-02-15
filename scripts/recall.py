#!/usr/bin/env python3
"""mem-os Recall Engine (TF-IDF + Graph). Zero external deps.

Default recall backend: ranked keyword search using TF-IDF scoring
with field boosts, recency weighting, and optional graph-based
neighbor boosting via cross-reference traversal.

For semantic recall (embeddings), see RecallBackend interface below.
Optional vector backends (Qdrant/Pinecone) can be plugged in via config.

Usage:
    python3 scripts/recall.py --query "authentication" --workspace "."
    python3 scripts/recall.py --query "auth" --workspace "." --json --limit 5
    python3 scripts/recall.py --query "deadline" --active-only
    python3 scripts/recall.py --query "database" --graph --workspace .
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


_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "must", "and", "but", "or",
    "nor", "not", "so", "yet", "for", "of", "to", "in", "on", "at", "by",
    "with", "from", "as", "into", "about", "between", "through", "during",
    "before", "after", "above", "below", "up", "down", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "because", "if", "while", "that", "this",
    "it", "its", "we", "they", "them", "their", "he", "she", "his", "her",
})


def tokenize(text):
    """Split text into lowercase tokens, filtering stopwords."""
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower())
            if t not in _STOPWORDS and len(t) > 1]


def extract_text(block):
    """Extract searchable text from a block."""
    parts = []
    # Include block ID so users can search by ID
    bid = block.get("_id", "")
    if bid:
        parts.append(bid)
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
        now = datetime.now()
        days_old = (now - d).days
        if days_old <= 0:
            return 1.0
        return max(0.1, 1.0 - (days_old / 365))
    except (ValueError, TypeError):
        return 0.5


# ---------------------------------------------------------------------------
# Graph-based recall — cross-reference neighbor boosting
# ---------------------------------------------------------------------------

# Regex matching any block ID pattern (D-..., T-..., PRJ-..., etc.)
_BLOCK_ID_RE = re.compile(
    r"\b(D-\d{8}-\d{3}|T-\d{8}-\d{3}|PRJ-\d{3}|PER-\d{3}|TOOL-\d{3}"
    r"|INC-\d{3}|C-\d{8}-\d{3}|SIG-\d{8}-\d{3}|P-\d{8}-\d{3})\b"
)

# Graph neighbor boost factor: a neighbor gets this fraction of the referencing block's score
GRAPH_BOOST_FACTOR = 0.3


def build_xref_graph(all_blocks):
    """Build bidirectional adjacency graph from cross-references.

    Scans every block's text fields for mentions of other block IDs.
    Returns {block_id: set(neighbor_ids)} with edges in both directions.
    """
    block_ids = {b.get("_id") for b in all_blocks if b.get("_id")}
    graph = {bid: set() for bid in block_ids}

    # Fields to scan for cross-references
    xref_fields = SEARCH_FIELDS + [
        "Supersedes", "SupersededBy", "AlignsWith", "Dependencies",
        "Next", "Sources", "Evidence", "Rollback", "History",
    ]

    for block in all_blocks:
        bid = block.get("_id")
        if not bid:
            continue

        # Collect all text from the block
        texts = []
        for field in xref_fields:
            val = block.get(field, "")
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                texts.extend(str(v) for v in val)

        # Also scan ConstraintSignature scope.projects
        for sig in block.get("ConstraintSignatures", []):
            scope = sig.get("scope", {})
            if isinstance(scope, dict):
                for v in scope.values():
                    if isinstance(v, list):
                        texts.extend(str(x) for x in v)
                    elif isinstance(v, str):
                        texts.append(v)

        # Find all referenced block IDs
        full_text = " ".join(texts)
        for match in _BLOCK_ID_RE.finditer(full_text):
            ref_id = match.group(1)
            if ref_id != bid and ref_id in block_ids:
                graph[bid].add(ref_id)
                graph[ref_id].add(bid)  # bidirectional

    return graph


def recall(workspace, query, limit=10, active_only=False, graph_boost=False):
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
        try:
            blocks = parse_file(path)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
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

    # Graph-based neighbor boosting: propagate score to 1-hop neighbors
    if graph_boost and results:
        xref_graph = build_xref_graph(all_blocks)
        score_by_id = {r["_id"]: r["score"] for r in results}
        # Blocks not yet in results can be added via graph traversal
        block_by_id = {b.get("_id"): b for b in all_blocks if b.get("_id")}

        neighbor_scores = {}
        for r in results:
            for neighbor_id in xref_graph.get(r["_id"], set()):
                if neighbor_id not in score_by_id:
                    # New block discovered via graph — add with boosted score
                    boost = r["score"] * GRAPH_BOOST_FACTOR
                    neighbor_scores[neighbor_id] = (
                        neighbor_scores.get(neighbor_id, 0) + boost
                    )
                else:
                    # Existing result — additional graph boost
                    boost = r["score"] * GRAPH_BOOST_FACTOR * 0.5
                    neighbor_scores[neighbor_id] = (
                        neighbor_scores.get(neighbor_id, 0) + boost
                    )

        # Apply boosts to existing results
        for r in results:
            if r["_id"] in neighbor_scores:
                r["score"] = round(r["score"] + neighbor_scores[r["_id"]], 4)
                r["via_graph"] = True

        # Add new neighbors discovered via graph
        for nid, nscore in neighbor_scores.items():
            if nid not in score_by_id and nid in block_by_id:
                nb = block_by_id[nid]
                results.append({
                    "_id": nid,
                    "type": get_block_type(nid),
                    "score": round(nscore, 4),
                    "excerpt": get_excerpt(nb),
                    "file": nb.get("_source_file", "?"),
                    "line": nb.get("_line", 0),
                    "status": nb.get("Status", ""),
                    "via_graph": True,
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
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    return None  # use built-in TF-IDF


def main():
    parser = argparse.ArgumentParser(description="mem-os Lexical Recall Engine")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    parser.add_argument("--active-only", action="store_true", help="Only search active blocks")
    parser.add_argument("--graph", action="store_true", help="Enable graph-based neighbor boosting")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Try vector backend first, fall back to TF-IDF
    backend = _load_backend(args.workspace)
    if backend:
        try:
            results = backend.search(args.workspace, args.query, args.limit, args.active_only)
        except (OSError, ValueError, TypeError) as e:
            print(f"recall: backend error ({e}), falling back to TF-IDF", file=sys.stderr)
            results = recall(args.workspace, args.query, args.limit, args.active_only, args.graph)
    else:
        results = recall(args.workspace, args.query, args.limit, args.active_only, args.graph)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No results found.")
        else:
            for r in results:
                graph_tag = " [graph]" if r.get("via_graph") else ""
                print(f"[{r['score']:.3f}] {r['_id']} ({r['type']}{graph_tag}) — {r['excerpt'][:80]}")
                print(f"        {r['file']}:{r['line']}")


if __name__ == "__main__":
    main()
