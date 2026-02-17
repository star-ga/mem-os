#!/usr/bin/env python3
"""mem-os Recall Engine (BM25 + TF-IDF + Graph + Stemming). Zero external deps.

Default recall backend: BM25 scoring with Porter stemming, stopword filtering,
query expansion, field boosts, recency weighting, and optional graph-based
neighbor boosting via cross-reference traversal.

For semantic recall (embeddings), see RecallBackend interface below.
Optional vector backends (Qdrant/Pinecone) can be plugged in via config.

Usage:
    python3 scripts/recall.py --query "authentication" --workspace "."
    python3 scripts/recall.py --query "auth" --workspace "." --json --limit 5
    python3 scripts/recall.py --query "deadline" --active-only
    python3 scripts/recall.py --query "database" --graph --workspace .
"""

from __future__ import annotations

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
from observability import get_logger, metrics, timed

_log = get_logger("recall")


# ---------------------------------------------------------------------------
# RecallBackend interface — plug in vector/semantic backends here
# ---------------------------------------------------------------------------

class RecallBackend(ABC):
    """Interface for recall backends. Default: BM25Backend (below).

    To add a vector backend:
    1. Implement this interface in recall_vector.py
    2. Set recall.backend = "vector" in mem-os.json
    3. recall.py will load it dynamically, falling back to BM25 on error.
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

# BM25 parameters
BM25_K1 = 1.2   # Term frequency saturation
BM25_B = 0.75   # Document length normalization


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


# ---------------------------------------------------------------------------
# Porter Stemmer (simplified, zero-dependency)
# ---------------------------------------------------------------------------

def _stem(word: str) -> str:
    """Simplified Porter stemmer — handles common English suffixes.

    Not a full Porter implementation, but covers the most impactful rules
    for recall quality: -ing, -ed, -tion, -ies, -ment, -ness, -ous, -ize.
    """
    if len(word) <= 3:
        return word

    # Step 1: Plurals and past participles
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("sses"):
        word = word[:-2]
    elif word.endswith("ness"):
        word = word[:-4]
    elif word.endswith("ment") and len(word) > 5:
        word = word[:-4]
    elif word.endswith("tion"):
        word = word[:-4] + "t"
    elif word.endswith("sion"):
        word = word[:-4] + "s"
    elif word.endswith("ized"):
        word = word[:-1]
    elif word.endswith("izing"):
        word = word[:-3] + "e"
    elif word.endswith("ize"):
        word = word  # keep as-is
    elif word.endswith("ating"):
        word = word[:-3] + "e"
    elif word.endswith("ation"):
        word = word[:-5] + "ate"
    elif word.endswith("ously"):
        word = word[:-5] + "ous"
    elif word.endswith("ous") and len(word) > 5:
        word = word  # keep as-is
    elif word.endswith("ful"):
        word = word[:-3]
    elif word.endswith("ally"):
        word = word[:-4] + "al"
    elif word.endswith("ably"):
        word = word[:-4] + "able"
    elif word.endswith("ibly"):
        word = word[:-4] + "ible"
    elif word.endswith("able") and len(word) > 5:
        word = word[:-4]
    elif word.endswith("ible") and len(word) > 5:
        word = word[:-4]
    elif word.endswith("ing") and len(word) > 4:
        word = word[:-3]
        # Restore trailing 'e': computing -> comput -> compute
        if word.endswith(("at", "iz", "bl")):
            word += "e"
    elif word.endswith("ated") and len(word) > 5:
        word = word[:-1]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]
        if word.endswith(("at", "iz", "bl")):
            word += "e"
    elif word.endswith("ly") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("er") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("est") and len(word) > 4:
        word = word[:-3]
    elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]

    return word


def tokenize(text: str) -> list[str]:
    """Split text into lowercase stemmed tokens, filtering stopwords."""
    return [_stem(t) for t in re.findall(r"[a-z0-9_]+", text.lower())
            if t not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# Query Expansion — domain-aware synonyms
# ---------------------------------------------------------------------------

_QUERY_EXPANSIONS = {
    "auth": ["authentication", "login", "oauth", "jwt", "session"],
    "authentication": ["auth", "login", "oauth", "jwt"],
    "db": ["database", "postgresql", "mysql", "sqlite", "sql"],
    "database": ["db", "postgresql", "mysql", "sqlite", "sql"],
    "api": ["endpoint", "rest", "graphql", "route", "handler"],
    "deploy": ["deployment", "ci", "cd", "pipeline", "release"],
    "deployment": ["deploy", "ci", "cd", "pipeline", "release"],
    "bug": ["error", "issue", "defect", "fix", "regression"],
    "error": ["bug", "exception", "failure", "crash"],
    "test": ["testing", "pytest", "unittest", "spec", "coverage"],
    "security": ["vulnerability", "auth", "encryption", "xss", "injection"],
    "perf": ["performance", "latency", "throughput", "optimization"],
    "performance": ["perf", "latency", "throughput", "optimization", "speed"],
    "config": ["configuration", "settings", "env", "environment"],
    "infra": ["infrastructure", "server", "cloud", "devops"],
}


def expand_query(tokens: list[str], max_expansions: int = 3) -> list[str]:
    """Expand query tokens with domain synonyms. Returns expanded token list."""
    expanded = list(tokens)
    added = set(tokens)
    for token in tokens:
        # Try unstemmed and stemmed lookups
        for lookup in (token, _stem(token)):
            if lookup in _QUERY_EXPANSIONS:
                for synonym in _QUERY_EXPANSIONS[lookup]:
                    stemmed = _stem(synonym)
                    if stemmed not in added and len(expanded) < len(tokens) + max_expansions:
                        expanded.append(stemmed)
                        added.add(stemmed)
    return expanded


def extract_text(block: dict) -> str:
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


# ---------------------------------------------------------------------------
# BM25F — Field-weighted term extraction
# ---------------------------------------------------------------------------

# Weight multipliers per field for BM25F scoring.
# Higher weight = terms in this field contribute more to the score.
FIELD_WEIGHTS = {
    "Statement": 3.0, "Title": 2.5, "Name": 2.0,
    "Summary": 1.5, "Description": 1.2, "Purpose": 1.2,
    "RootCause": 1.2, "Fix": 1.2, "Prevention": 1.0,
    "Tags": 0.8, "Keywords": 0.8,
    "Context": 0.5, "Rationale": 0.5, "ProposedFix": 0.5,
    "History": 0.3,
}


def extract_field_tokens(block: dict) -> dict[str, list[str]]:
    """Extract and tokenize per-field for BM25F scoring.

    Returns {field_name: [stemmed_tokens]} for each non-empty field.
    Also includes _id tokens under a synthetic '_id' key.
    """
    field_tokens = {}

    bid = block.get("_id", "")
    if bid:
        field_tokens["_id"] = tokenize(bid)

    for field in SEARCH_FIELDS:
        val = block.get(field, "")
        if isinstance(val, str) and val:
            tokens = tokenize(val)
            if tokens:
                field_tokens[field] = tokens
        elif isinstance(val, list):
            combined = " ".join(str(v) for v in val)
            tokens = tokenize(combined)
            if tokens:
                field_tokens[field] = tokens

    # ConstraintSignature fields
    sig_parts = []
    for sig in block.get("ConstraintSignatures", []):
        for sf in SIG_FIELDS:
            val = sig.get(sf, "")
            if isinstance(val, str):
                sig_parts.append(val)
    if sig_parts:
        tokens = tokenize(" ".join(sig_parts))
        if tokens:
            field_tokens["_sig"] = tokens

    return field_tokens


# ---------------------------------------------------------------------------
# Bigram phrase matching
# ---------------------------------------------------------------------------

def get_bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    """Generate set of adjacent token pairs (bigrams)."""
    return set(zip(tokens, tokens[1:]))


# ---------------------------------------------------------------------------
# Overlapping chunk indexing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Query Type Detection — category-specific retrieval tuning
# ---------------------------------------------------------------------------

# Temporal signal words/patterns
_TEMPORAL_PATTERNS = re.compile(
    r"\b(when|before|after|during|while|since|until|first|last|latest|earliest"
    r"|recent|previous|next|ago|year|month|week|day|date|time|period"
    r"|january|february|march|april|may|june|july|august|september"
    r"|october|november|december|spring|summer|fall|winter|autumn"
    r"|morning|evening|night|weekend|holiday|birthday|anniversary"
    r"|how long|how often|what time|what date|what year|what month"
    r"|started|ended|began|finished|happened|occurred|changed"
    r"|earlier|later|prior|subsequent|meanwhile|eventually)\b",
    re.IGNORECASE,
)

# Adversarial negation patterns
_ADVERSARIAL_PATTERNS = re.compile(
    r"\b(never|not|no one|nobody|nothing|nowhere|neither|nor"
    r"|didn.t|doesn.t|don.t|wasn.t|weren.t|isn.t|aren.t|hasn.t"
    r"|haven.t|hadn.t|won.t|wouldn.t|can.t|couldn.t|shouldn.t"
    r"|false|incorrect|wrong|untrue|lie|fake|fabricat"
    r"|no interest|no desire|no intention|no plan"
    r"|contrary|opposite|instead|rather than|unlike|different from)\b",
    re.IGNORECASE,
)

# Multi-hop indicators (questions requiring info from multiple sources)
_MULTIHOP_PATTERNS = re.compile(
    r"\b(both|and also|as well as|in addition|together|combined"
    r"|relationship|connection|between|compare|comparison|versus|vs|both"
    r"|how many|how much|total|count|sum|all|every|each"
    r"|who else|what else|where else|which other"
    r"|same|similar|different|shared|common|overlap"
    r"|because|caused|resulted|led to|due to|reason|why did)\b",
    re.IGNORECASE,
)


def detect_query_type(query: str) -> str:
    """Classify query into temporal/adversarial/multi-hop/single-hop.

    Returns one of: 'temporal', 'adversarial', 'multi-hop', 'single-hop'.
    Uses pattern-based heuristics with scoring to handle ambiguous queries.
    """
    query_lower = query.lower()

    temporal_hits = len(_TEMPORAL_PATTERNS.findall(query_lower))
    adversarial_hits = len(_ADVERSARIAL_PATTERNS.findall(query_lower))
    multihop_hits = len(_MULTIHOP_PATTERNS.findall(query_lower))

    # Question mark count can indicate complexity
    qmarks = query.count("?")

    # Score each category
    scores = {
        "temporal": temporal_hits * 2,
        "adversarial": adversarial_hits * 2.5,
        "multi-hop": multihop_hits * 1.5 + (1 if qmarks > 1 else 0),
        "single-hop": 1,  # default baseline
    }

    # Strong negation at start is a very strong adversarial signal
    if re.match(r"^(did|was|were|is|has|have|does|do)\b.+\b(not|never|n.t)\b", query_lower):
        scores["adversarial"] += 3
    # "Did X ever" is also adversarial (expects yes/no about something that may not have happened)
    if re.search(r"\bever\b", query_lower):
        scores["adversarial"] += 2

    # Long queries with conjunctions are more likely multi-hop
    word_count = len(query.split())
    if word_count > 15 and multihop_hits > 0:
        scores["multi-hop"] += 2

    # Pick the highest-scoring category
    best = max(scores, key=scores.get)

    # Only override single-hop if signal is strong enough
    if best == "single-hop" or scores[best] < 1.5:
        return "single-hop"

    return best


# Category-specific retrieval parameters
_QUERY_TYPE_PARAMS = {
    "temporal": {
        "recency_weight": 0.6,     # Higher recency matters more
        "date_boost": 2.0,         # Boost blocks with dates
        "expand_query": True,      # Keep expansions
        "extra_limit_factor": 1.5, # Retrieve more candidates
    },
    "adversarial": {
        "recency_weight": 0.3,     # Standard — adversarial needs same broad recall
        "date_boost": 1.0,         # No date boost
        "expand_query": True,      # Keep expansion — adversarial answers ARE in context
        "extra_limit_factor": 1.0, # Standard — handled at answerer level, not retrieval
    },
    "multi-hop": {
        "recency_weight": 0.3,     # Standard
        "date_boost": 1.0,
        "expand_query": True,
        "extra_limit_factor": 2.0, # Need more blocks to find all hops
        "graph_boost_override": True,  # Force graph traversal
    },
    "single-hop": {
        "recency_weight": 0.3,     # Standard
        "date_boost": 1.0,
        "expand_query": True,
        "extra_limit_factor": 1.0,
    },
}


def chunk_text(text: str, chunk_size: int = 3, overlap: int = 1) -> list[str]:
    """Split text into overlapping sentence chunks.

    Args:
        text: Full text to chunk.
        chunk_size: Sentences per chunk.
        overlap: Overlapping sentences between chunks.

    Returns list of chunk strings. Returns [text] if <=chunk_size sentences.
    """
    # Simple sentence splitting on .!? followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s for s in sentences if s.strip()]

    if len(sentences) <= chunk_size:
        return [text]

    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(sentences), step):
        chunk = " ".join(sentences[start:start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(sentences):
            break
    return chunks if chunks else [text]


def get_excerpt(block: dict, max_len: int = 120) -> str:
    """Get a short excerpt from a block."""
    for field in ("Statement", "Title", "Summary", "Description", "Name", "Context"):
        val = block.get(field, "")
        if isinstance(val, str) and val:
            return val[:max_len]
    return block.get("_id", "?")


def get_block_type(block_id: str) -> str:
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


def date_score(block: dict) -> float:
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


def build_xref_graph(all_blocks: list[dict]) -> dict[str, set[str]]:
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


def recall(workspace: str, query: str, limit: int = 10, active_only: bool = False, graph_boost: bool = False, agent_id: str | None = None) -> list[dict]:
    """Search across all memory files using BM25 scoring. Returns ranked results.

    Args:
        workspace: Workspace root path.
        query: Search query.
        limit: Max results to return.
        active_only: Only return blocks with active status.
        graph_boost: Enable cross-reference neighbor boosting.
        agent_id: Optional agent ID for namespace ACL filtering.
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Detect query type for category-specific tuning
    query_type = detect_query_type(query)
    qparams = _QUERY_TYPE_PARAMS.get(query_type, _QUERY_TYPE_PARAMS["single-hop"])

    # Query expansion: add domain synonyms (skip for adversarial — precision over recall)
    if qparams.get("expand_query", True):
        query_tokens = expand_query(query_tokens)

    # Force graph boost for multi-hop queries
    if qparams.get("graph_boost_override", False):
        graph_boost = True

    # Adjust effective limit for retrieval (retrieve more candidates, trim later)
    effective_limit = int(limit * qparams.get("extra_limit_factor", 1.0))

    # Namespace ACL: resolve accessible paths if agent_id is provided
    ns_manager = None
    if agent_id:
        try:
            from namespaces import NamespaceManager
            ns_manager = NamespaceManager(workspace, agent_id=agent_id)
        except ImportError:
            pass

    # Load all blocks with source file tracking
    all_blocks = []
    for label, rel_path in CORPUS_FILES.items():
        # ACL check: skip files the agent cannot read
        if ns_manager and not ns_manager.can_read(rel_path):
            continue

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

    # If agent has namespace, also search agent-private corpus files
    if ns_manager and agent_id:
        agent_ns = f"agents/{agent_id}"
        for label, rel_path in CORPUS_FILES.items():
            ns_path = os.path.join(agent_ns, rel_path)
            full_path = os.path.join(workspace, ns_path)
            if not os.path.isfile(full_path):
                continue
            if not ns_manager.can_read(ns_path):
                continue
            try:
                blocks = parse_file(full_path)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            if active_only:
                blocks = get_active(blocks)
            for b in blocks:
                b["_source_file"] = ns_path
                b["_source_label"] = f"{label}@{agent_id}"
                all_blocks.append(b)

    if not all_blocks:
        return []

    # --- BM25F: per-field tokenization + flat token list for IDF ---
    doc_field_tokens = []   # [{field: [tokens]}] per block
    doc_flat_tokens = []    # [[all_tokens]] per block (for IDF + bigrams)
    for block in all_blocks:
        ft = extract_field_tokens(block)
        doc_field_tokens.append(ft)
        flat = []
        for tokens in ft.values():
            flat.extend(tokens)
        doc_flat_tokens.append(flat)

    # Document frequency + average weighted doc length
    df = Counter()
    total_wdl = 0.0
    for i, ft in enumerate(doc_field_tokens):
        seen = set()
        wdl = 0.0
        for field, tokens in ft.items():
            w = FIELD_WEIGHTS.get(field, 1.0)
            wdl += len(tokens) * w
            for t in tokens:
                seen.add(t)
        for t in seen:
            df[t] += 1
        total_wdl += wdl

    N = len(all_blocks)
    avg_wdl = total_wdl / N if N > 0 else 1.0

    # Pre-compute query bigrams for phrase matching
    query_bigrams = get_bigrams(query_tokens)

    results = []

    for i, block in enumerate(all_blocks):
        ft = doc_field_tokens[i]
        flat = doc_flat_tokens[i]
        if not flat:
            continue

        # --- BM25F: field-weighted term frequency ---
        # Compute weighted TF across all fields
        weighted_tf = Counter()
        wdl = 0.0
        for field, tokens in ft.items():
            w = FIELD_WEIGHTS.get(field, 1.0)
            wdl += len(tokens) * w
            for t in tokens:
                weighted_tf[t] += w

        score = 0.0
        for qt in query_tokens:
            if qt in weighted_tf:
                wtf = weighted_tf[qt]
                idf = math.log((N - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5) + 1)
                numerator = wtf * (BM25_K1 + 1)
                denominator = wtf + BM25_K1 * (1 - BM25_B + BM25_B * wdl / avg_wdl)
                score += idf * numerator / denominator

        if score <= 0:
            continue

        # --- Bigram phrase matching boost ---
        if query_bigrams:
            doc_bigrams = get_bigrams(flat)
            phrase_matches = len(query_bigrams & doc_bigrams)
            if phrase_matches > 0:
                score *= (1.0 + 0.25 * phrase_matches)

        # --- Chunking boost: score best chunk separately, blend ---
        # For long blocks, check if a chunk scores much higher
        statement = block.get("Statement", "") or block.get("Title", "") or ""
        if len(statement) > 200:
            chunks = chunk_text(statement)
            if len(chunks) > 1:
                best_chunk_score = 0.0
                for chunk in chunks:
                    ctokens = tokenize(chunk)
                    ctf = Counter(ctokens)
                    cdl = len(ctokens)
                    cs = 0.0
                    for qt in query_tokens:
                        if qt in ctf:
                            freq = ctf[qt]
                            idf = math.log((N - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5) + 1)
                            cs += idf * freq * (BM25_K1 + 1) / (freq + BM25_K1 * (1 - BM25_B + BM25_B * cdl / max(avg_wdl, 1)))
                    best_chunk_score = max(best_chunk_score, cs)
                # Blend: take the better of full-block or best-chunk score
                if best_chunk_score > score:
                    score = 0.6 * best_chunk_score + 0.4 * score

        # --- Boost factors (query-type-aware) ---
        recency = date_score(block)
        rw = qparams.get("recency_weight", 0.3)
        score *= (1.0 - rw + rw * recency)

        # Temporal queries: boost blocks that contain dates
        date_boost = qparams.get("date_boost", 1.0)
        if date_boost > 1.0 and block.get("Date", ""):
            score *= date_boost

        status = block.get("Status", "")
        if status == "active":
            score *= 1.2
        elif status in ("todo", "doing"):
            score *= 1.1

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

    # Graph-based neighbor boosting: 2-hop traversal for multi-hop recall
    if graph_boost and results:
        xref_graph = build_xref_graph(all_blocks)
        score_by_id = {r["_id"]: r["score"] for r in results}
        block_by_id = {b.get("_id"): b for b in all_blocks if b.get("_id")}

        neighbor_scores = {}

        # 2-hop traversal: decay 0.3 for 1-hop, 0.1 for 2-hop
        for hop, decay in enumerate([GRAPH_BOOST_FACTOR, GRAPH_BOOST_FACTOR * 0.33]):
            # On first hop, seed from BM25 results; on second, seed from 1-hop discoveries
            seeds = results if hop == 0 else [
                {"_id": nid, "score": ns}
                for nid, ns in neighbor_scores.items()
                if nid not in score_by_id
            ]
            for r in seeds:
                rid = r["_id"]
                for neighbor_id in xref_graph.get(rid, set()):
                    boost = r["score"] * decay
                    if neighbor_id not in score_by_id:
                        neighbor_scores[neighbor_id] = (
                            neighbor_scores.get(neighbor_id, 0) + boost
                        )
                    else:
                        neighbor_scores[neighbor_id] = (
                            neighbor_scores.get(neighbor_id, 0) + boost * 0.5
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
    top = results[:limit]
    _log.info("query_complete", query=query, query_type=query_type,
              blocks_searched=N, results=len(top),
              top_score=top[0]["score"] if top else 0)
    metrics.inc("recall_queries")
    metrics.inc("recall_results", len(top))
    return top


def _load_backend(workspace: str) -> str:
    """Load recall backend from config. Falls back to BM25."""
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
                    pass  # fall through to BM25
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    return None  # use built-in BM25


def main():
    parser = argparse.ArgumentParser(description="mem-os Recall Engine (BM25 + Graph)")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    parser.add_argument("--active-only", action="store_true", help="Only search active blocks")
    parser.add_argument("--graph", action="store_true", help="Enable graph-based neighbor boosting")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Try vector backend first, fall back to BM25
    backend = _load_backend(args.workspace)
    if backend:
        try:
            results = backend.search(args.workspace, args.query, args.limit, args.active_only)
        except (OSError, ValueError, TypeError) as e:
            print(f"recall: backend error ({e}), falling back to BM25", file=sys.stderr)
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
