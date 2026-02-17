"""Tests for the adversarial abstention classifier."""

from __future__ import annotations

import os
import sys

# Ensure scripts/ is on path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

from abstention_classifier import (  # noqa: E402
    ABSTENTION_ANSWER,
    AbstentionResult,
    DEFAULT_THRESHOLD,
    _extract_query_entities,
    _extract_speaker_from_query,
    _speaker_in_hit,
    _term_overlap,
    classify_abstention,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_hit(excerpt: str, score: float = 5.0, speaker: str = "Emma") -> dict:
    """Build a minimal recall hit for testing."""
    return {
        "excerpt": excerpt,
        "score": score,
        "speaker": speaker,
        "DiaID": "D1:1",
        "tags": f"speaker:{speaker}",
        "_id": "test-001",
    }


RELEVANT_HITS = [
    _make_hit("Emma mentioned she wanted to adopt a golden retriever puppy", score=8.5),
    _make_hit("Emma said she loves dogs and has been looking at shelters", score=7.2),
    _make_hit("During the conversation, Emma talked about her pet preferences", score=6.0),
    _make_hit("Emma also mentioned her neighbor has a dog she walks sometimes", score=5.5),
    _make_hit("Emma discussed her weekend plans involving the animal shelter", score=4.8),
]

IRRELEVANT_HITS = [
    _make_hit("John talked about his new car and the dealership experience", score=3.1, speaker="John"),
    _make_hit("The weather forecast showed rain for the entire week", score=2.5, speaker="John"),
    _make_hit("Sarah mentioned her vacation plans to Italy next summer", score=2.0, speaker="Sarah"),
    _make_hit("The meeting agenda covered quarterly budget reviews", score=1.8, speaker="Manager"),
    _make_hit("Technical discussion about API rate limiting strategies", score=1.2, speaker="Dev"),
]

MIXED_HITS = [
    _make_hit("Emma mentioned she wanted to adopt a golden retriever puppy", score=8.5),
    _make_hit("John talked about his new car and the dealership experience", score=3.1, speaker="John"),
    _make_hit("Sarah mentioned her vacation plans to Italy next summer", score=2.0, speaker="Sarah"),
    _make_hit("The meeting agenda covered quarterly budget reviews", score=1.8, speaker="Manager"),
    _make_hit("Technical discussion about API rate limiting strategies", score=1.2, speaker="Dev"),
]


# ── Unit tests: entity extraction ────────────────────────────────────

class TestExtractQueryEntities:
    def test_basic_extraction(self):
        entities = _extract_query_entities("Did Emma mention adopting a dog?")
        assert "emma" in entities
        assert "adopting" in entities
        assert "dog" in entities

    def test_stops_removed(self):
        entities = _extract_query_entities("Did she ever mention wanting to adopt?")
        assert "she" not in entities
        assert "ever" not in entities
        assert "adopt" in entities
        assert "wanting" in entities

    def test_empty_query(self):
        assert _extract_query_entities("") == set()


class TestExtractSpeaker:
    def test_finds_name(self):
        assert _extract_speaker_from_query("Did Emma ever mention dogs?") == "emma"

    def test_finds_full_name(self):
        result = _extract_speaker_from_query("Did Emma Watson talk about her career?")
        assert result in ("emma watson", "emma")

    def test_no_name(self):
        assert _extract_speaker_from_query("what was discussed about dogs?") is None

    def test_skips_question_words(self):
        # "Did" and "The" should not be extracted as names
        assert _extract_speaker_from_query("Did the group discuss plans?") is None


class TestTermOverlap:
    def test_full_overlap(self):
        overlap = _term_overlap("Emma loves dogs and wants to adopt one", {"emma", "dogs", "adopt"})
        assert overlap == 1.0

    def test_partial_overlap(self):
        overlap = _term_overlap("Emma loves cats", {"emma", "dogs", "adopt"})
        assert 0.0 < overlap < 1.0

    def test_no_overlap(self):
        overlap = _term_overlap("Technical budget review", {"emma", "dogs", "adopt"})
        assert overlap == 0.0

    def test_empty_entities(self):
        assert _term_overlap("some text", set()) == 0.0


class TestSpeakerInHit:
    def test_speaker_field_match(self):
        hit = _make_hit("some text", speaker="Emma")
        assert _speaker_in_hit(hit, "emma") is True

    def test_excerpt_match(self):
        hit = _make_hit("Emma said hello", speaker="Unknown")
        assert _speaker_in_hit(hit, "emma") is True

    def test_no_match(self):
        hit = _make_hit("John said hello", speaker="John")
        assert _speaker_in_hit(hit, "emma") is False

    def test_no_speaker_query(self):
        hit = _make_hit("some text")
        assert _speaker_in_hit(hit, "") is False


# ── Integration tests: classify_abstention ───────────────────────────

class TestClassifyAbstention:
    def test_no_hits_abstains(self):
        result = classify_abstention("Did Emma ever adopt a dog?", [])
        assert result.should_abstain is True
        assert result.confidence == 0.0
        assert result.forced_answer == ABSTENTION_ANSWER

    def test_relevant_hits_no_abstain(self):
        result = classify_abstention("Did Emma ever mention adopting a dog?", RELEVANT_HITS)
        assert result.should_abstain is False
        assert result.confidence > DEFAULT_THRESHOLD

    def test_irrelevant_hits_abstains(self):
        result = classify_abstention("Did Emma ever mention adopting a dog?", IRRELEVANT_HITS)
        assert result.should_abstain is True
        assert result.confidence < DEFAULT_THRESHOLD

    def test_mixed_hits_intermediate_confidence(self):
        result = classify_abstention("Did Emma ever mention adopting a dog?", MIXED_HITS)
        # With 1 relevant + 4 irrelevant, confidence should be moderate
        assert 0.0 < result.confidence < 0.8

    def test_forced_answer_on_abstention(self):
        result = classify_abstention("Did Emma ever mention quantum physics?", IRRELEVANT_HITS)
        assert result.should_abstain is True
        assert result.forced_answer == ABSTENTION_ANSWER

    def test_no_forced_answer_when_confident(self):
        result = classify_abstention("Did Emma ever mention adopting a dog?", RELEVANT_HITS)
        assert result.forced_answer == ""

    def test_features_populated(self):
        result = classify_abstention("Did Emma ever mention dogs?", RELEVANT_HITS)
        assert "entity_overlap" in result.features
        assert "top1_score_raw" in result.features
        assert "speaker_coverage" in result.features
        assert "evidence_density" in result.features
        assert "speaker_detected" in result.features

    def test_threshold_tuning(self):
        # Very high threshold should cause abstention even with good hits
        result = classify_abstention(
            "Did Emma ever mention adopting a dog?",
            RELEVANT_HITS,
            threshold=0.99,
        )
        assert result.should_abstain is True

        # Zero threshold should never abstain (unless no hits)
        result = classify_abstention(
            "Did Emma ever mention quantum physics?",
            IRRELEVANT_HITS,
            threshold=0.0,
        )
        assert result.should_abstain is False

    def test_ever_pattern_penalty(self):
        """'did X ever' pattern should penalize low-overlap results."""
        r1 = classify_abstention("Did Emma ever mention dogs?", IRRELEVANT_HITS)
        r2 = classify_abstention("What did Emma say about dogs?", IRRELEVANT_HITS)
        # "ever" variant should have lower confidence due to negation penalty
        assert r1.features["has_ever_pattern"] is True
        assert r2.features["has_ever_pattern"] is False
        assert r1.confidence <= r2.confidence

    def test_result_is_dataclass(self):
        result = classify_abstention("test?", [])
        assert isinstance(result, AbstentionResult)

    def test_confidence_clamped(self):
        result = classify_abstention("test?", RELEVANT_HITS)
        assert 0.0 <= result.confidence <= 1.0

    def test_non_adversarial_question(self):
        """Normal factual questions with good hits should not abstain."""
        good_hits = [
            _make_hit("The project deadline is March 15th", score=9.0, speaker="Manager"),
            _make_hit("We agreed on March 15th for the final delivery", score=8.0, speaker="Manager"),
        ]
        result = classify_abstention("What is the project deadline?", good_hits)
        assert result.should_abstain is False


# ── Edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_single_hit(self):
        result = classify_abstention(
            "Did Emma mention dogs?",
            [_make_hit("Emma loves dogs", score=8.0)],
        )
        assert isinstance(result, AbstentionResult)

    def test_hit_with_zero_score(self):
        hits = [_make_hit("some text about Emma dogs", score=0.0)]
        result = classify_abstention("Did Emma mention dogs?", hits)
        # Zero BM25 score lowers confidence vs same hit with high score
        high_score_hits = [_make_hit("some text about Emma dogs", score=8.0)]
        result_high = classify_abstention("Did Emma mention dogs?", high_score_hits)
        assert result.confidence < result_high.confidence

    def test_hit_missing_fields(self):
        """Hits with missing optional fields should not crash."""
        hits = [{"excerpt": "Emma mentioned dogs", "score": 5.0}]
        result = classify_abstention("Did Emma mention dogs?", hits)
        assert isinstance(result, AbstentionResult)

    def test_unicode_query(self):
        result = classify_abstention("Did Emma mention cafe?", RELEVANT_HITS)
        assert isinstance(result, AbstentionResult)
