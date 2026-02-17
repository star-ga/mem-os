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
) -> str:
    """Compress retrieved context into focused observations.

    Args:
        context: Formatted context string from format_context().
        question: The user's question.
        llm_fn: Callable matching _llm_chat(messages, model, max_tokens) -> str.
        model: Model to use for compression (same as answerer for consistency).
        max_tokens: Max tokens for compression output.

    Returns:
        Compressed observation string to replace raw context.
    """
    if not context.strip():
        return context

    messages = [
        {"role": "system", "content": COMPRESS_SYSTEM_PROMPT},
        {"role": "user", "content": COMPRESS_USER_TEMPLATE.format(
            question=question, context=context
        )},
    ]
    return llm_fn(messages, model=model, max_tokens=max_tokens)
