#!/usr/bin/env python3
"""Tests for intel_scan.py — contradiction detection, drift analysis, impact graph."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from intel_scan import (
    IntelReport, detect_contradictions, detect_drift, scopes_overlap,
    check_signature_conflict, get_axis_key, load_all, build_impact_graph,
)


class TestIntelReport(unittest.TestCase):
    def test_accumulates_counts(self):
        r = IntelReport()
        r.critical_msg("crit1")
        r.warn("warn1")
        r.warn("warn2")
        r.info_msg("info1")
        self.assertEqual(r.critical, 1)
        self.assertEqual(r.warnings, 2)
        self.assertEqual(r.info, 1)

    def test_text_output(self):
        r = IntelReport()
        r.section("TEST")
        r.ok("All good")
        text = r.text()
        self.assertIn("=== TEST ===", text)
        self.assertIn("OK: All good", text)


class TestScopesOverlap(unittest.TestCase):
    def test_empty_scopes_overlap(self):
        self.assertTrue(scopes_overlap({}, {}))

    def test_disjoint_projects(self):
        s1 = {"projects": ["proj-a"]}
        s2 = {"projects": ["proj-b"]}
        self.assertFalse(scopes_overlap(s1, s2))

    def test_overlapping_projects(self):
        s1 = {"projects": ["proj-a", "proj-b"]}
        s2 = {"projects": ["proj-b", "proj-c"]}
        self.assertTrue(scopes_overlap(s1, s2))

    def test_disjoint_time(self):
        s1 = {"time": {"start": "2026-01-01", "end": "2026-01-31"}}
        s2 = {"time": {"start": "2026-03-01", "end": "2026-03-31"}}
        self.assertFalse(scopes_overlap(s1, s2))

    def test_overlapping_time(self):
        s1 = {"time": {"start": "2026-01-01", "end": "2026-03-01"}}
        s2 = {"time": {"start": "2026-02-01", "end": "2026-04-01"}}
        self.assertTrue(scopes_overlap(s1, s2))


class TestGetAxisKey(unittest.TestCase):
    def test_with_axis(self):
        sig = {"axis": {"key": "auth.jwt"}}
        self.assertEqual(get_axis_key(sig), "auth.jwt")

    def test_fallback_to_domain_subject(self):
        sig = {"domain": "security", "subject": "tokens"}
        self.assertEqual(get_axis_key(sig), "security.tokens")

    def test_empty_sig(self):
        self.assertEqual(get_axis_key({}), "other.unknown")


class TestCheckSignatureConflict(unittest.TestCase):
    def test_no_conflict_different_axis(self):
        s1 = {"id": "CS-001", "axis": {"key": "auth.jwt"}, "modality": "must", "scope": {}}
        s2 = {"id": "CS-002", "axis": {"key": "db.postgres"}, "modality": "must_not", "scope": {}}
        self.assertIsNone(check_signature_conflict(s1, s2))

    def test_modality_conflict(self):
        s1 = {"id": "CS-001", "axis": {"key": "auth.jwt"}, "modality": "must",
               "scope": {}, "predicate": "use", "object": "JWT"}
        s2 = {"id": "CS-002", "axis": {"key": "auth.jwt"}, "modality": "must_not",
               "scope": {}, "predicate": "use", "object": "JWT"}
        result = check_signature_conflict(s1, s2)
        self.assertIsNotNone(result)
        self.assertEqual(result["severity"], "critical")

    def test_composes_with_suppresses(self):
        s1 = {"id": "CS-001", "axis": {"key": "auth.jwt"}, "modality": "must",
               "scope": {}, "composes_with": ["CS-002"]}
        s2 = {"id": "CS-002", "axis": {"key": "auth.jwt"}, "modality": "must_not",
               "scope": {}}
        self.assertIsNone(check_signature_conflict(s1, s2))

    def test_disjoint_scope_no_conflict(self):
        s1 = {"id": "CS-001", "axis": {"key": "auth"}, "modality": "must",
               "scope": {"projects": ["proj-a"]}}
        s2 = {"id": "CS-002", "axis": {"key": "auth"}, "modality": "must_not",
               "scope": {"projects": ["proj-b"]}}
        self.assertIsNone(check_signature_conflict(s1, s2))


class TestDetectContradictions(unittest.TestCase):
    def test_no_active_decisions(self):
        report = IntelReport()
        result = detect_contradictions([], report)
        self.assertEqual(result, [])

    def test_detects_contradiction(self):
        decisions = [
            {
                "_id": "D-20260213-001", "Status": "active",
                "ConstraintSignatures": [
                    {"id": "CS-001", "axis": {"key": "auth"}, "modality": "must",
                     "scope": {}, "predicate": "use", "object": "JWT"}
                ]
            },
            {
                "_id": "D-20260213-002", "Status": "active",
                "ConstraintSignatures": [
                    {"id": "CS-002", "axis": {"key": "auth"}, "modality": "must_not",
                     "scope": {}, "predicate": "use", "object": "JWT"}
                ]
            },
        ]
        report = IntelReport()
        result = detect_contradictions(decisions, report)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["severity"], "critical")


class TestDetectDrift(unittest.TestCase):
    def test_no_drift_on_empty(self):
        data = {"decisions": [], "tasks": [], "incidents": []}
        report = IntelReport()
        result = detect_drift(data, report)
        self.assertEqual(result, [])

    def test_detects_blocked_tasks(self):
        data = {
            "decisions": [],
            "tasks": [{"_id": "T-001", "Status": "blocked", "Title": "Stuck task"}],
            "incidents": [],
        }
        report = IntelReport()
        result = detect_drift(data, report)
        stalled = [s for s in result if s["signal"] == "stalled_tasks"]
        self.assertEqual(len(stalled), 1)


class TestLoadAll(unittest.TestCase):
    def test_missing_files_return_empty(self):
        with tempfile.TemporaryDirectory() as td:
            data = load_all(td)
            for key in data:
                self.assertEqual(data[key], [])


if __name__ == "__main__":
    unittest.main()
