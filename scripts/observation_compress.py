"""Observation Compression Layer for Mem-OS.

Compresses retrieved memory blocks into concise, query-relevant observations
using an LLM. This sits between retrieval and answer generation:

    Retrieve (BM25) → Compress (LLM) → Answer (LLM) → Judge (LLM)

The compression step distills top-K raw blocks into focused factual
observations, dramatically improving answer quality by:
  1. Eliminating noise and irrelevant context
  2. Synthesizing scattered facts into coherent summaries
  3. Surfacing implicit temporal and causal relationships

Zero external dependencies beyond stdlib (uses the same _llm_chat as the
benchmark harness).
"""

from __future__ import annotations

COMPRESS_SYSTEM_PROMPT = """\
You are a memory compression expert. Given a set of conversation memory excerpts \
and a question, extract ONLY the facts relevant to answering the question.

Rules:
1. Output a numbered list of factual observations derived from the context.
2. Each observation must be a single, self-contained factual statement.
3. Include temporal information (dates, times, order of events) when present.
4. Include names, relationships, preferences, opinions, and specific details.
5. If multiple excerpts discuss the same topic, synthesize them into one observation.
6. Discard excerpts that are completely irrelevant to the question.
7. Preserve exact quotes, numbers, and proper nouns from the source material.
8. Output 3-8 observations. Fewer is fine if the context is sparse."""

# Category-specific system prompts that override the default when a query
# type is detected.  These give the compression LLM sharper focus for each
# question category.

_CATEGORY_PROMPTS = {
    "adversarial": """\
You are a memory compression expert. The question tests whether something \
was explicitly rejected, never mentioned, or contradicts prior context.

Rules:
1. Output a numbered list of factual observations from the context.
2. For each topic in the question, note whether it was AFFIRMED, DENIED, \
or NEVER MENTIONED in the excerpts.
3. If something was explicitly rejected or not chosen, state that clearly \
(e.g., "They explicitly decided NOT to use X").
4. If the context contains NO information about a topic, state: \
"No evidence found regarding [topic]."
5. Pay close attention to negations, rejections, changes of mind, and \
contradictions between excerpts.
6. Preserve exact quotes that contain negations or rejections.
7. Output 3-8 observations.""",

    "temporal": """\
You are a memory compression expert. The question asks about timing, \
sequence, or chronological order of events.

Rules:
1. Output a numbered list of factual observations in CHRONOLOGICAL ORDER.
2. Include exact dates, times, and relative ordering (before/after/during).
3. If events have a causal chain, preserve that order explicitly.
4. Note any changes over time (e.g., "First X, then changed to Y on [date]").
5. If timing is ambiguous, state what is known and what is uncertain.
6. Preserve exact dates and timestamps from the source material.
7. Output 3-8 observations.""",

    "multi-hop": """\
You are a memory compression expert. The question requires connecting \
multiple facts from different parts of the conversation.

Rules:
1. Output a numbered list of factual observations.
2. For each relevant fact, note its SOURCE (which excerpt or conversation \
segment it came from).
3. Explicitly state connections between facts when they exist \
(e.g., "Person A mentioned X in excerpt 2, and Person B responded to X \
in excerpt 5").
4. If the question asks about a relationship between entities, list all \
facts about EACH entity separately, then note their connections.
5. Include indirect connections that require inference.
6. Preserve names, relationships, and cross-references.
7. Output 4-10 observations (multi-hop needs more detail).""",
}

COMPRESS_USER_TEMPLATE = """\
Question: {question}

Retrieved memory excerpts:
{context}

Extract the relevant factual observations for answering this question."""


def compress_context(
    context: str,
    question: str,
    llm_fn,
    model: str = "gpt-4o-mini",
    max_tokens: int = 400,
    query_type: str | None = None,
) -> str:
    """Compress retrieved context into focused observations.

    Args:
        context: Formatted context string from format_context().
        question: The user's question.
        llm_fn: Callable matching _llm_chat(messages, model, max_tokens) -> str.
        model: Model to use for compression (same as answerer for consistency).
        max_tokens: Max tokens for compression output.
        query_type: Optional query category (adversarial/temporal/multi-hop)
                    for category-specific compression prompts.

    Returns:
        Compressed observation string to replace raw context.
    """
    if not context.strip():
        return context

    system_prompt = _CATEGORY_PROMPTS.get(query_type or "", COMPRESS_SYSTEM_PROMPT)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": COMPRESS_USER_TEMPLATE.format(
            question=question, context=context
        )},
    ]
    return llm_fn(messages, model=model, max_tokens=max_tokens)
