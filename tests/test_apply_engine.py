#!/usr/bin/env python3
"""Tests for apply_engine.py — focus on security, validation, and rollback."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from apply_engine import (
    _safe_resolve, validate_proposal, create_snapshot, restore_snapshot,
    check_no_touch_window, check_fingerprint_dedup, compute_fingerprint,
)
import json
from datetime import datetime, timedelta


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


class TestSnapshotIntelligenceRestore(unittest.TestCase):
    """Verify snapshot restore includes intelligence files."""

    def test_rollback_restores_intelligence_files(self):
        """Intelligence files (e.g., SIGNALS.md) must be restored on rollback."""
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, "decisions"))
            os.makedirs(os.path.join(ws, "intelligence"))
            signals = os.path.join(ws, "intelligence", "SIGNALS.md")
            with open(signals, "w") as f:
                f.write("original signals")
            with open(os.path.join(ws, "decisions", "DECISIONS.md"), "w") as f:
                f.write("# D\n")

            snap_dir = create_snapshot(ws, "test-intel")

            # Mutate intelligence file
            with open(signals, "w") as f:
                f.write("mutated signals")

            restore_snapshot(ws, snap_dir)

            with open(signals) as f:
                self.assertEqual(f.read(), "original signals")


class TestNoTouchWindow(unittest.TestCase):
    """Verify no-touch window cooldown logic."""

    def test_no_previous_apply(self):
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, "memory"))
            with open(os.path.join(ws, "memory", "intel-state.json"), "w") as f:
                json.dump({}, f)
            ok, reason = check_no_touch_window(ws)
            self.assertTrue(ok)

    def test_recent_apply_blocks(self):
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, "memory"))
            recent = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(os.path.join(ws, "memory", "intel-state.json"), "w") as f:
                json.dump({"last_apply_ts": recent}, f)
            ok, reason = check_no_touch_window(ws)
            self.assertFalse(ok)
            self.assertIn("No-touch window", reason)

    def test_old_apply_clears(self):
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, "memory"))
            old = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(os.path.join(ws, "memory", "intel-state.json"), "w") as f:
                json.dump({"last_apply_ts": old}, f)
            ok, reason = check_no_touch_window(ws)
            self.assertTrue(ok)


class TestFingerprintDedup(unittest.TestCase):
    """Verify fingerprint dedup skips self-match."""

    def test_self_match_not_duplicate(self):
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, "intelligence", "proposed"), exist_ok=True)
            proposal = {
                "ProposalId": "P-20260214-001", "_id": "P-20260214-001",
                "Type": "decision", "TargetBlock": "D-20260214-001",
                "Ops": [{"op": "append_block", "file": "decisions/DECISIONS.md"}],
                "Status": "staged",
            }
            fp = compute_fingerprint(proposal)
            block_text = (
                "[P-20260214-001]\n"
                "ProposalId: P-20260214-001\n"
                "Type: decision\n"
                "TargetBlock: D-20260214-001\n"
                "Status: staged\n"
                f"Fingerprint: {fp}\n"
            )
            for fn in ["DECISIONS_PROPOSED.md", "TASKS_PROPOSED.md", "EDITS_PROPOSED.md"]:
                path = os.path.join(ws, "intelligence", "proposed", fn)
                with open(path, "w") as f:
                    f.write(block_text if fn == "DECISIONS_PROPOSED.md" else "")
            is_dup, dup_id = check_fingerprint_dedup(ws, proposal)
            self.assertFalse(is_dup)


class TestFreshInitValidate(unittest.TestCase):
    """Verify fresh workspace passes validate.sh with 0 issues."""

    def test_fresh_init_passes_validate(self):
        with tempfile.TemporaryDirectory() as ws:
            from init_workspace import init
            init(ws)
            import subprocess
            result = subprocess.run(
                ["bash", os.path.join(ws, "maintenance", "validate.sh"), ws],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, f"validate.sh failed:\n{result.stdout}")
            self.assertIn("0 issues", result.stdout)


if __name__ == "__main__":
    unittest.main()
