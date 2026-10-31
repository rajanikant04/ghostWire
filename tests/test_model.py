"""Tests for the model module — Ollama interaction with mocked HTTP calls."""

import json
import unittest
from unittest import mock

from vetal.model import generate_riddle, judge_answer


def _make_ollama_response(content_dict: dict) -> bytes:
    """Build a fake Ollama chat API response body."""
    body = {
        "model": "gemma3:4b",
        "message": {
            "role": "assistant",
            "content": json.dumps(content_dict),
        },
    }
    return json.dumps(body).encode("utf-8")


class _FakeHTTPResponse:
    """Minimal context-manager stand-in for ``urllib.request.urlopen``."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestGenerateRiddle(unittest.TestCase):
    """Tests for ``generate_riddle``."""

    _VALID_RIDDLE = {
        "tale": "In the kingdom of Avanti, a wise potter refused to glaze his finest pot.",
        "riddle": "Tell me, Vikram: what happens when validate_user skips the email check?",
        "answer_key": [
            "Empty strings reach the database",
            "The unique constraint raises a 500 error",
        ],
    }

    @mock.patch("vetal.model.is_ollama_running", return_value=True)
    @mock.patch("vetal.model.urllib.request.urlopen")
    def test_generate_riddle_parses_response(self, mock_urlopen, _mock_running):
        """A well-formed Ollama response should parse into the expected dict."""
        mock_urlopen.return_value = _FakeHTTPResponse(
            _make_ollama_response(self._VALID_RIDDLE)
        )

        result = generate_riddle("diff --git a/app.py ...")
        self.assertIsNotNone(result)
        self.assertEqual(result["tale"], self._VALID_RIDDLE["tale"])
        self.assertEqual(result["riddle"], self._VALID_RIDDLE["riddle"])
        self.assertEqual(result["answer_key"], self._VALID_RIDDLE["answer_key"])

    @mock.patch("vetal.model.is_ollama_running", return_value=False)
    def test_ollama_not_running(self, _mock_running):
        """When Ollama is not reachable, ``generate_riddle`` should return None."""
        result = generate_riddle("diff --git a/app.py ...")
        self.assertIsNone(result)


class TestJudgeAnswer(unittest.TestCase):
    """Tests for ``judge_answer``."""

    _DIFF = "diff --git a/app.py b/app.py\n-old\n+new"
    _RIDDLE = "What breaks when the check is removed?"
    _ANSWER_KEY = ["empty strings pass through", "500 error instead of 400"]
    _ANSWER = "Empty strings hit the DB and you get a 500"

    @mock.patch("vetal.model.is_ollama_running", return_value=True)
    @mock.patch("vetal.model.urllib.request.urlopen")
    def test_judge_answer_release(self, mock_urlopen, _mock_running):
        """A 'release' verdict should be parsed correctly."""
        verdict_body = {
            "verdict": "release",
            "response": "You speak true, Vikram. Vetal releases his grip.",
        }
        mock_urlopen.return_value = _FakeHTTPResponse(
            _make_ollama_response(verdict_body)
        )

        result = judge_answer(
            self._DIFF, self._RIDDLE, self._ANSWER_KEY, self._ANSWER
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "release")
        self.assertIn("Vikram", result["response"])

    @mock.patch("vetal.model.is_ollama_running", return_value=True)
    @mock.patch("vetal.model.urllib.request.urlopen")
    def test_judge_answer_cling(self, mock_urlopen, _mock_running):
        """A 'cling' verdict should be parsed correctly."""
        verdict_body = {
            "verdict": "cling",
            "response": "You do not understand your own change, Vikram!",
        }
        mock_urlopen.return_value = _FakeHTTPResponse(
            _make_ollama_response(verdict_body)
        )

        result = judge_answer(
            self._DIFF, self._RIDDLE, self._ANSWER_KEY, "I dunno"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "cling")

    @mock.patch("vetal.model.is_ollama_running", return_value=False)
    def test_ollama_not_running_judge(self, _mock_running):
        """When Ollama is unreachable, ``judge_answer`` should return None."""
        result = judge_answer(
            self._DIFF, self._RIDDLE, self._ANSWER_KEY, self._ANSWER
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
