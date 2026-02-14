#!/usr/bin/env python3
"""Tests for recall.py — zero external deps (stdlib unittest)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from recall import tokenize, extract_text, get_block_type, get_excerpt, recall


class TestTokenize(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(tokenize("Hello World"), ["hello", "world"])

    def test_special_chars(self):
        self.assertEqual(tokenize("auth/JWT-token"), ["auth", "jwt", "token"])

    def test_empty(self):
        self.assertEqual(tokenize(""), [])

    def test_numbers(self):
        self.assertIn("42", tokenize("answer is 42"))


class TestExtractText(unittest.TestCase):
    def test_extracts_search_fields(self):
        block = {"Statement": "Use JWT", "Tags": "auth, security"}
        text = extract_text(block)
        self.assertIn("Use JWT", text)
        self.assertIn("auth, security", text)

    def test_extracts_constraint_sigs(self):
        block = {
            "ConstraintSignatures": [
                {"subject": "we", "predicate": "must_use", "object": "JWT", "domain": "auth"}
            ]
        }
        text = extract_text(block)
        self.assertIn("we", text)
        self.assertIn("must_use", text)

    def test_empty_block(self):
        self.assertEqual(extract_text({}).strip(), "")


class TestGetBlockType(unittest.TestCase):
    def test_known_prefixes(self):
        self.assertEqual(get_block_type("D-20260213-001"), "decision")
        self.assertEqual(get_block_type("T-20260213-001"), "task")
        self.assertEqual(get_block_type("PRJ-001"), "project")
        self.assertEqual(get_block_type("SIG-20260213-001"), "signal")

    def test_unknown(self):
        self.assertEqual(get_block_type("X-001"), "unknown")


class TestGetExcerpt(unittest.TestCase):
    def test_returns_statement(self):
        block = {"Statement": "Use JWT for authentication"}
        self.assertEqual(get_excerpt(block), "Use JWT for authentication")

    def test_fallback_to_id(self):
        block = {"_id": "D-001"}
        self.assertEqual(get_excerpt(block), "D-001")

    def test_truncation(self):
        block = {"Statement": "x" * 200}
        self.assertEqual(len(get_excerpt(block)), 120)


class TestRecall(unittest.TestCase):
    def _setup_workspace(self, tmpdir, decisions_content=""):
        """Create minimal workspace with decisions file and a dummy task for IDF diversity."""
        for d in ["decisions", "tasks", "entities", "intelligence"]:
            os.makedirs(os.path.join(tmpdir, d), exist_ok=True)
        with open(os.path.join(tmpdir, "decisions", "DECISIONS.md"), "w") as f:
            f.write(decisions_content)
        # Create a dummy task block so TF-IDF has >1 document (IDF needs document diversity)
        with open(os.path.join(tmpdir, "tasks", "TASKS.md"), "w") as f:
            f.write("[T-20260213-099]\nTitle: Unrelated placeholder task\nStatus: active\n")
        for fname in ["entities/projects.md", "entities/people.md",
                       "entities/tools.md", "entities/incidents.md",
                       "intelligence/CONTRADICTIONS.md", "intelligence/DRIFT.md",
                       "intelligence/SIGNALS.md"]:
            path = os.path.join(tmpdir, fname)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(f"# {os.path.basename(fname)}\n")
        return tmpdir

    def test_empty_query(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._setup_workspace(td)
            results = recall(ws, "")
            self.assertEqual(results, [])

    def test_no_results(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._setup_workspace(td, "# Decisions\n")
            results = recall(ws, "xyznonexistent")
            self.assertEqual(results, [])

    def test_finds_matching_block(self):
        with tempfile.TemporaryDirectory() as td:
            content = (
                "[D-20260213-001]\nStatement: Use JWT for authentication\n"
                "Status: active\nDate: 2026-02-13\n"
            )
            ws = self._setup_workspace(td, content)
            results = recall(ws, "JWT authentication")
            self.assertGreater(len(results), 0)
            self.assertEqual(results[0]["_id"], "D-20260213-001")

    def test_limit(self):
        with tempfile.TemporaryDirectory() as td:
            content = ""
            for i in range(1, 6):
                content += f"[D-20260213-{i:03d}]\nStatement: Auth decision {i}\nStatus: active\n\n---\n\n"
            ws = self._setup_workspace(td, content)
            results = recall(ws, "auth", limit=2)
            self.assertLessEqual(len(results), 2)

    def test_active_only_filter(self):
        with tempfile.TemporaryDirectory() as td:
            content = (
                "[D-20260213-001]\nStatement: JWT auth\nStatus: active\n\n---\n\n"
                "[D-20260213-002]\nStatement: JWT superseded\nStatus: superseded\n"
            )
            ws = self._setup_workspace(td, content)
            results = recall(ws, "JWT", active_only=True)
            ids = [r["_id"] for r in results]
            self.assertIn("D-20260213-001", ids)
            self.assertNotIn("D-20260213-002", ids)

    def test_boosts_active_status(self):
        """Active blocks should score higher than non-active ones."""
        with tempfile.TemporaryDirectory() as td:
            content = (
                "[D-20260213-001]\nStatement: JWT token auth\nStatus: superseded\nDate: 2026-02-13\n\n---\n\n"
                "[D-20260213-002]\nStatement: JWT token auth\nStatus: active\nDate: 2026-02-13\n"
            )
            ws = self._setup_workspace(td, content)
            results = recall(ws, "JWT token")
            self.assertEqual(len(results), 2)
            # Active block should rank higher
            self.assertEqual(results[0]["_id"], "D-20260213-002")


if __name__ == "__main__":
    unittest.main()
