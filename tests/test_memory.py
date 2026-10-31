"""Tests for the memory module — recording and checking answered commits."""

import json
import os
import tempfile
import unittest
from unittest import mock

from vetal import memory


def _make_fake_git_dir(tmp: str) -> str:
    """Create a fake .git directory inside *tmp* and return its path."""
    git_dir = os.path.join(tmp, ".git")
    os.makedirs(git_dir, exist_ok=True)
    return git_dir


class TestMemory(unittest.TestCase):
    """Tests for ``has_answered`` and ``record_answer``."""

    def setUp(self):
        """Create a temp directory with a fake .git and patch ``get_git_dir``."""
        self._tmp = tempfile.mkdtemp()
        self._git_dir = _make_fake_git_dir(self._tmp)
        # Patch get_git_dir so memory reads/writes inside our temp dir
        self._patcher = mock.patch(
            "vetal.memory.get_git_dir", return_value=self._git_dir
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        # Clean up temp directory
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── Tests ─────────────────────────────────────────────────────────────

    def test_record_and_check(self):
        """After recording a SHA, ``has_answered`` should return True."""
        sha = "abc123def456"
        self.assertFalse(memory.has_answered(sha))
        memory.record_answer(sha)
        self.assertTrue(memory.has_answered(sha))

    def test_unknown_sha(self):
        """``has_answered`` should return False for an unknown SHA."""
        self.assertFalse(memory.has_answered("never_seen_before"))

    def test_persistence(self):
        """Data written by ``record_answer`` should survive a fresh read from disk."""
        sha = "persist_me_1234"
        memory.record_answer(sha)

        # Verify the file was actually written to disk
        answered_path = os.path.join(self._git_dir, "vetal", "answered.json")
        self.assertTrue(os.path.exists(answered_path))

        # Read the raw JSON to confirm the SHA is there
        with open(answered_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn(sha, data)

        # Calling has_answered again (which re-reads from disk) should still
        # find it — simulating a new "instance" of the memory module.
        self.assertTrue(memory.has_answered(sha))

    def test_record_empty_sha_is_noop(self):
        """Recording an empty SHA should be silently ignored."""
        memory.record_answer("")
        self.assertFalse(memory.has_answered(""))

    def test_record_skip(self):
        """``record_skip`` should also mark the SHA as present."""
        sha = "skipped_abc"
        memory.record_skip(sha)
        self.assertTrue(memory.has_answered(sha))


if __name__ == "__main__":
    unittest.main()
