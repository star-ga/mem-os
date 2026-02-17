"""Deterministic evidence packer for Mem-OS.

Builds structured, speaker-attributed evidence context from recall hits.
No LLM dependency — prevents starvation and hallucination in adversarial
and verification queries.

This module is the "answer view" builder for mem-os recall results:
  recall(query) -> hits -> pack_evidence(hits, query_type) -> packed_context
"""

from __future__ import annotations

import re

_DENIAL_RE = re.compile(
    r"\b(didn't|did not|never|not|no|denied|refused|won't|can't|cannot|"
    r"doesn't|does not|hasn't|has not|wasn't|wasn't|isn't)\b",
    re.IGNORECASE,
)

_SEMANTIC_PREFIX_RE = re.compile(r"^\([^)]{1,80}\)\s*")

# Patterns that indicate a question is truly adversarial/verification
# vs a normal factual question misclassified as adversarial
_ADVERSARIAL_SIGNAL_RE = re.compile(
    r"\b(ever|never|deny|denied|not\s+mention|was\s+.*\s+said|"
    r"at\s+any\s+point|reject|refuse|contradict|false|untrue)\b",
    re.IGNORECASE,
)


def strip_semantic_prefix(text: str) -> str:
    """Remove leading semantic label prefix e.g. '(identity description) '."""
    return _SEMANTIC_PREFIX_RE.sub("", text)


def is_true_adversarial(question: str) -> bool:
    """Check if a question is truly adversarial/verification vs misclassified.

    Many LoCoMo 'adversarial' questions are normal factual questions.
    Only apply strict adversarial policy when the question actually
    contains verification/negation language.
    """
    return bool(_ADVERSARIAL_SIGNAL_RE.search(question))


def pack_evidence(
    hits: list[dict],
    question: str = "",
    query_type: str = "",
    max_chars: int = 6000,
) -> str:
    """Build structured evidence context from recall hits.

    For adversarial/verification queries: speaker-attributed structured format.
    For normal queries: clean text format (backwards compatible).

    Args:
        hits: Recall results with excerpt, speaker, tags, score.
        question: The query (used for adversarial classification).
        query_type: Category hint (adversarial, temporal, etc.).
        max_chars: Maximum context length.

    Returns:
        Formatted context string ready for LLM consumption.
    """
    # Route: true adversarial gets structured packing,
    # misclassified adversarial gets normal packing
    if query_type == "adversarial" and is_true_adversarial(question):
        return _pack_adversarial(hits, max_chars)
    else:
        return _pack_standard(hits, max_chars)


def _pack_standard(hits: list[dict], max_chars: int = 6000) -> str:
    """Standard context packing — clean text, speaker prefix if available."""
    parts = []
    total = 0
    for r in hits:
        text = r.get("excerpt", "")
        if not text:
            continue
        clean = strip_semantic_prefix(text.strip())
        if total + len(clean) > max_chars:
            break
        parts.append(clean)
        total += len(clean)
    return "\n".join(parts)


def _pack_adversarial(hits: list[dict], max_chars: int = 6000) -> str:
    """Structured evidence packing for adversarial/verification questions.

    Deterministic — no LLM, no starvation risk.
    Groups by speaker, separates denial evidence.
    """
    evidence_lines = []
    denial_lines = []
    total = 0

    for r in hits:
        text = r.get("excerpt", "")
        if not text:
            continue
        clean = strip_semantic_prefix(text.strip())
        speaker = r.get("speaker", "") or "UNKNOWN"

        line = f"[SPEAKER={speaker}] {clean}"
        if total + len(line) > max_chars:
            break

        if _DENIAL_RE.search(clean):
            denial_lines.append(line)
        else:
            evidence_lines.append(line)
        total += len(line)

    has_evidence = bool(evidence_lines or denial_lines)

    parts = []
    parts.append(f"EVIDENCE_FOUND: {'YES' if has_evidence else 'NO'}")
    parts.append("EVIDENCE:")
    if evidence_lines:
        parts.extend(f"- {ln}" for ln in evidence_lines)
    else:
        parts.append("- (none)")
    parts.append("DENIAL_EVIDENCE:")
    if denial_lines:
        parts.extend(f"- {ln}" for ln in denial_lines)
    else:
        parts.append("- (none)")

    return "\n".join(parts)
