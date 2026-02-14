#!/usr/bin/env python3
"""Tests for apply_engine.py — focus on security, validation, and rollback."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from apply_engine import _safe_resolve, validate_proposal, create_snapshot, restore_snapshot


class TestSafeResolve(unittest.TestCase):
    def test_normal_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "decisions")
            os.makedirs(target)
            result = _safe_resolve(td, "decisions")
            self.assertEqual(result, os.path.realpath(target))

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                _safe_resolve(td, "../../../etc/passwd")

    def test_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                _safe_resolve(td, "/etc/passwd")

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td:
            # Create symlink that points outside workspace
            link_path = os.path.join(td, "escape_link")
            os.symlink("/tmp", link_path)
            with self.assertRaises(ValueError):
                _safe_resolve(td, "escape_link/should_fail")

    def test_allows_internal_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            real_dir = os.path.join(td, "real")
            os.makedirs(real_dir)
            link_path = os.path.join(td, "link")
            os.symlink(real_dir, link_path)
            # Internal symlink should work
            result = _safe_resolve(td, "link")
            self.assertEqual(result, os.path.realpath(real_dir))

    def test_rejects_dotdot_in_middle(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                _safe_resolve(td, "decisions/../../../etc/passwd")


class TestValidateProposal(unittest.TestCase):
    def _valid_proposal(self, **overrides):
        base = {
            "ProposalId": "P-20260213-001",
            "Type": "decision",
            "Risk": "low",
            "Status": "staged",
            "Evidence": "Test evidence",
            "Rollback": "Revert changes",
            "Ops": [{"op": "append_block", "file": "decisions/DECISIONS.md"}],
        }
        base.update(overrides)
        return base

    def test_valid_proposal(self):
        errors = validate_proposal(self._valid_proposal())
        self.assertEqual(errors, [])

    def test_missing_required_field(self):
        p = self._valid_proposal()
        del p["Evidence"]
        errors = validate_proposal(p)
        self.assertTrue(any("Evidence" in e for e in errors))

    def test_invalid_risk(self):
        errors = validate_proposal(self._valid_proposal(Risk="extreme"))
        self.assertTrue(any("Risk" in e for e in errors))

    def test_invalid_type(self):
        errors = validate_proposal(self._valid_proposal(Type="migration"))
        self.assertTrue(any("Type" in e for e in errors))

    def test_status_not_staged(self):
        errors = validate_proposal(self._valid_proposal(Status="applied"))
        self.assertTrue(any("staged" in e for e in errors))

    def test_rejects_path_traversal_in_ops(self):
        p = self._valid_proposal(
            Ops=[{"op": "append_block", "file": "../../../etc/shadow"}]
        )
        errors = validate_proposal(p)
        self.assertTrue(any("traversal" in e for e in errors))

    def test_rejects_absolute_path_in_ops(self):
        p = self._valid_proposal(
            Ops=[{"op": "append_block", "file": "/etc/passwd"}]
        )
        errors = validate_proposal(p)
        self.assertTrue(any("traversal" in e.lower() or "absolute" in e.lower() for e in errors))

    def test_invalid_op_type(self):
        p = self._valid_proposal(
            Ops=[{"op": "delete_everything", "file": "decisions/DECISIONS.md"}]
        )
        errors = validate_proposal(p)
        self.assertTrue(any("op" in e.lower() for e in errors))


class TestSnapshotRollback(unittest.TestCase):
    """Verify atomic rollback removes files created during failed ops."""

    def test_rollback_removes_new_files(self):
        """Files created after snapshot must be deleted on restore."""
        with tempfile.TemporaryDirectory() as ws:
            # Set up workspace structure
            os.makedirs(os.path.join(ws, "decisions"))
            original = os.path.join(ws, "decisions", "DECISIONS.md")
            with open(original, "w") as f:
                f.write("# Decisions\n")

            # Create snapshot
            snap_dir = create_snapshot(ws, "test-rollback")

            # Simulate a failed op creating a new file
            rogue_file = os.path.join(ws, "decisions", "ROGUE.md")
            with open(rogue_file, "w") as f:
                f.write("# This should not survive rollback\n")
            self.assertTrue(os.path.exists(rogue_file))

            # Restore snapshot
            restore_snapshot(ws, snap_dir)

            # Rogue file must be gone (true atomic rollback)
            self.assertFalse(os.path.exists(rogue_file))
            # Original file must still exist
            self.assertTrue(os.path.exists(original))

    def test_rollback_restores_content(self):
        """Modified files must revert to snapshot content."""
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, "decisions"))
            original = os.path.join(ws, "decisions", "DECISIONS.md")
            with open(original, "w") as f:
                f.write("original content")

            snap_dir = create_snapshot(ws, "test-content")

            # Modify file
            with open(original, "w") as f:
                f.write("corrupted content")

            restore_snapshot(ws, snap_dir)

            with open(original) as f:
                self.assertEqual(f.read(), "original content")


if __name__ == "__main__":
    unittest.main()
