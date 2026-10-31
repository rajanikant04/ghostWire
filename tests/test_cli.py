"""Tests for the CLI interface of Vetal."""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from vetal import cli


class TestCLI(unittest.TestCase):
    """Test CLI commands and argument routing."""

    def test_version_flag(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("sys.argv", ["vetal", "--version"]):
                with self.assertRaises(SystemExit) as cm:
                    cli.main()
                self.assertEqual(cm.exception.code, 0)
                self.assertIn("vetal", mock_stdout.getvalue())

    def test_status_command(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("vetal.cli.is_ollama_running", return_value=True):
                with patch("vetal.hook.get_git_dir", return_value=tempfile.gettempdir()):
                    with patch("sys.argv", ["vetal", "status"]):
                        cli.main()
                    output = mock_stdout.getvalue()
                    self.assertIn("Ollama: reachable", output)

    def test_demo_command_simulation(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("vetal.cli.is_ollama_running", return_value=False):
                with patch("builtins.input", return_value="It hits the database constraint and 500s"):
                    with patch("sys.argv", ["vetal", "demo"]):
                        with self.assertRaises(SystemExit) as cm:
                            cli.main()
                        self.assertEqual(cm.exception.code, 0)
                        output = mock_stdout.getvalue()
                        self.assertIn("Vetal leaps off your shoulders", output)

    def test_riddle_command_json_empty_diff(self):
        with patch("sys.stdin", io.StringIO("")):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with patch("sys.argv", ["vetal", "riddle", "--json"]):
                    with self.assertRaises(SystemExit) as cm:
                        cli.main()
                    self.assertEqual(cm.exception.code, 0)
                    data = json.loads(mock_stdout.getvalue())
                    self.assertEqual(data.get("tale"), "")
                    self.assertEqual(data.get("riddle"), "")

    def test_riddle_command_json_with_diff(self):
        sample_diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
-def foo(): return 1
+def foo(): return None
"""
        mock_riddle = {
            "tale": "A merchant stopped weighing gold.",
            "riddle": "What happens when foo returns None?",
            "answer_key": ["returns None", "type error"],
        }
        with patch("sys.stdin", io.StringIO(sample_diff)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with patch("vetal.cli.generate_riddle", return_value=mock_riddle):
                    with patch("sys.argv", ["vetal", "riddle", "--json"]):
                        cli.main()
                        data = json.loads(mock_stdout.getvalue())
                        self.assertEqual(data["riddle"], mock_riddle["riddle"])
                        self.assertEqual(data["tale"], mock_riddle["tale"])

    def test_judge_pr_command(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as diff_f:
            diff_f.write("diff --git a/foo.py b/foo.py\n+def bar(): pass\n")
            diff_path = diff_f.name

        with tempfile.NamedTemporaryFile("w", delete=False) as ans_f:
            ans_f.write("It adds a dummy function that does nothing.")
            ans_path = ans_f.name

        try:
            mock_riddle = {
                "tale": "A builder laid a stone.",
                "riddle": "Why pass?",
                "answer_key": ["empty function"],
            }
            mock_judgment = {
                "verdict": "release",
                "response": "You know your code.",
            }

            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with patch("vetal.cli.generate_riddle", return_value=mock_riddle):
                    with patch("vetal.cli.judge_answer", return_value=mock_judgment):
                        with patch(
                            "sys.argv",
                            [
                                "vetal",
                                "judge-pr",
                                "--diff-file",
                                diff_path,
                                "--answer-file",
                                ans_path,
                                "--json",
                            ],
                        ):
                            cli.main()
                            data = json.loads(mock_stdout.getvalue())
                            self.assertEqual(data["verdict"], "release")
                            self.assertEqual(data["response"], "You know your code.")
        finally:
            if os.path.exists(diff_path):
                os.remove(diff_path)
            if os.path.exists(ans_path):
                os.remove(ans_path)


if __name__ == "__main__":
    unittest.main()
