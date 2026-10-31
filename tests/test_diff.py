"""Tests for the diff parsing and trimming module."""

import unittest

from vetal.diff import is_boring_file, trim_diff


class TestIsBoringFile(unittest.TestCase):
    """Tests for ``is_boring_file``."""

    def test_lockfiles_are_boring(self):
        """Lock-files should be marked as boring."""
        lockfiles = [
            "package-lock.json",
            "yarn.lock",
            "poetry.lock",
            "Pipfile.lock",
            "Cargo.lock",
            "go.sum",
            "pnpm-lock.yaml",
            "composer.lock",
            "Gemfile.lock",
        ]
        for name in lockfiles:
            with self.subTest(name=name):
                self.assertTrue(is_boring_file(name))

    def test_minified_and_svg_are_boring(self):
        """.min.js, .min.css, .svg, and .map files are boring."""
        boring = ["app.min.js", "style.min.css", "logo.svg", "bundle.js.map"]
        for name in boring:
            with self.subTest(name=name):
                self.assertTrue(is_boring_file(name))

    def test_source_files_are_not_boring(self):
        """.py, .js, .ts, .go, .rs files should NOT be boring."""
        interesting = ["main.py", "index.js", "app.ts", "server.go", "lib.rs"]
        for name in interesting:
            with self.subTest(name=name):
                self.assertFalse(is_boring_file(name))

    def test_nested_lockfile_path(self):
        """Lockfile inside a subdirectory path should still be detected."""
        self.assertTrue(is_boring_file("some/deep/path/package-lock.json"))

    def test_image_extensions_are_boring(self):
        """Image files (.png, .jpg, etc.) should be boring."""
        self.assertTrue(is_boring_file("screenshot.png"))
        self.assertTrue(is_boring_file("photo.jpeg"))


class TestTrimDiff(unittest.TestCase):
    """Tests for ``trim_diff``."""

    # ── Helpers ───────────────────────────────────────────────────────────

    _PY_DIFF = (
        "diff --git a/app.py b/app.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,3 +1,4 @@\n"
        " import os\n"
        "+import sys\n"
        " \n"
        " def main():\n"
    )

    _LOCK_DIFF = (
        "diff --git a/package-lock.json b/package-lock.json\n"
        "index aaa..bbb 100644\n"
        "--- a/package-lock.json\n"
        "+++ b/package-lock.json\n"
        "@@ -1,1000 +1,1001 @@\n"
        ' "lockfileVersion": 3,\n'
    )

    def test_trim_diff_drops_lockfiles(self):
        """A diff containing only lockfile content should trim to empty."""
        result = trim_diff(self._LOCK_DIFF)
        self.assertEqual(result, "")

    def test_trim_diff_preserves_code(self):
        """A small .py diff within budget should be preserved verbatim."""
        result = trim_diff(self._PY_DIFF)
        self.assertEqual(result, self._PY_DIFF)

    def test_trim_diff_fair_share(self):
        """When 2 files exceed the byte budget, each gets roughly half."""
        # Create two large file diffs, each 1000 bytes of content
        big_line = "+" + "x" * 78 + "\n"  # 80 bytes per line
        lines_per_file = 15  # 15 * 80 = 1200 bytes of content per file

        file_a_header = (
            "diff --git a/alpha.py b/alpha.py\n"
            "--- a/alpha.py\n"
            "+++ b/alpha.py\n"
            "@@ -1,1 +1,20 @@\n"
        )
        file_b_header = (
            "diff --git a/beta.py b/beta.py\n"
            "--- a/beta.py\n"
            "+++ b/beta.py\n"
            "@@ -1,1 +1,20 @@\n"
        )

        file_a = file_a_header + big_line * lines_per_file
        file_b = file_b_header + big_line * lines_per_file

        combined = file_a + file_b
        # Budget much smaller than total — forces trimming
        budget = len(combined) // 2
        result = trim_diff(combined, max_bytes=budget)

        # Both files should be represented (both headers should appear)
        self.assertIn("alpha.py", result)
        self.assertIn("beta.py", result)

        # Result should be within the budget (or very close, plus trim markers)
        # The important thing is both files got a share
        self.assertLessEqual(len(result), budget + 200)  # small margin for trim markers

    def test_empty_diff(self):
        """An empty diff string should return an empty string."""
        self.assertEqual(trim_diff(""), "")

    def test_mixed_boring_and_interesting(self):
        """A combined diff with lockfile + .py should drop the lockfile part."""
        combined = self._LOCK_DIFF + self._PY_DIFF
        result = trim_diff(combined)
        self.assertNotIn("package-lock.json", result)
        self.assertIn("app.py", result)


if __name__ == "__main__":
    unittest.main()
