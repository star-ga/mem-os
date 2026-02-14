#!/usr/bin/env python3
"""Tests for capture.py — zero external deps (stdlib unittest)."""

import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from capture import scan_log, append_signals, DECISION_PATTERNS, XREF_PATTERN


class TestScanLog(unittest.TestCase):
    def _write_log(self, tmpdir, content):
        path = os.path.join(tmpdir, "test.md")
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_detects_decision_language(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_log(td, "We decided to use PostgreSQL for the database.\n")
            signals = scan_log(path)
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0]["type"], "decision")

    def test_detects_task_language(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_log(td, "We need to update the deployment scripts.\n")
            signals = scan_log(path)
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0]["type"], "task")

    def test_skips_crossreferenced(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_log(td, "We decided to use JWT (D-20260213-001).\n")
            signals = scan_log(path)
            self.assertEqual(len(signals), 0)

    def test_skips_headers(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_log(td, "# We decided to restructure\n")
            signals = scan_log(path)
            self.assertEqual(len(signals), 0)

    def test_skips_empty_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_log(td, "\n\n\n")
            signals = scan_log(path)
            self.assertEqual(len(signals), 0)

    def test_line_numbers_correct(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write_log(td, "Normal line.\nWe decided to switch to Redis.\n")
            signals = scan_log(path)
            self.assertEqual(signals[0]["line"], 2)


class TestAppendSignals(unittest.TestCase):
    def _setup_workspace(self, tmpdir, existing_signals=""):
        intel_dir = os.path.join(tmpdir, "intelligence")
        os.makedirs(intel_dir, exist_ok=True)
        sig_path = os.path.join(intel_dir, "SIGNALS.md")
        with open(sig_path, "w") as f:
            f.write("# Captured Signals\n\n" + existing_signals)
        return tmpdir

    def test_appends_signal_without_hash_header(self):
        """Signals must use [SIG-...] format, NOT ## [SIG-...]."""
        with tempfile.TemporaryDirectory() as td:
            ws = self._setup_workspace(td)
            signals = [{"line": 1, "type": "decision", "text": "We chose React", "pattern": ".*"}]
            count = append_signals(ws, signals, "2026-02-13")
            self.assertEqual(count, 1)

            with open(os.path.join(ws, "intelligence", "SIGNALS.md")) as f:
                content = f.read()
            # Must have [SIG-...] without ## prefix for parser compatibility
            self.assertIn("[SIG-20260213-001]", content)
            self.assertNotIn("## [SIG-", content)

    def test_dedup_skips_existing(self):
        """If first 60 chars of signal text already exist in SIGNALS.md, skip it."""
        with tempfile.TemporaryDirectory() as td:
            # The dedup check is: sig["text"][:60] in existing
            existing_text = "We chose React for the frontend framework as our UI layer"
            ws = self._setup_workspace(td, f"[SIG-20260213-001]\nExcerpt: {existing_text}\n")
            signals = [{"line": 1, "type": "decision", "text": existing_text, "pattern": ".*"}]
            count = append_signals(ws, signals, "2026-02-13")
            self.assertEqual(count, 0)

    def test_counter_increments(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._setup_workspace(td, "[SIG-20260213-002]\nExcerpt: Previous signal\n")
            signals = [{"line": 1, "type": "task", "text": "Need to deploy by Friday", "pattern": ".*"}]
            count = append_signals(ws, signals, "2026-02-13")
            self.assertEqual(count, 1)

            with open(os.path.join(ws, "intelligence", "SIGNALS.md")) as f:
                content = f.read()
            self.assertIn("[SIG-20260213-003]", content)

    def test_no_signals_file(self):
        with tempfile.TemporaryDirectory() as td:
            signals = [{"line": 1, "type": "decision", "text": "test", "pattern": ".*"}]
            count = append_signals(td, signals, "2026-02-13")
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
