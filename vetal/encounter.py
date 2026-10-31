"""The encounter — Vetal's main riddle→answer→judge flow.

This module ties together diff trimming, model interaction, memory, and
the dramatic terminal UI.
"""

import os
import sys

from vetal.diff import trim_diff
from vetal.model import is_ollama_running, generate_riddle, judge_answer
from vetal.memory import has_answered, record_answer

# ── ANSI styling ──────────────────────────────────────────────────────────────

TREE = "\033[32m"       # green
GHOST = "\033[35m"      # magenta
TALE = "\033[2;3m"      # dim italic
RIDDLE = "\033[1;33m"   # bold yellow
WARN = "\033[31m"       # red
SUCCESS = "\033[32m"    # green
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Minimum diff size (in chars) worth asking about
_MIN_DIFF_SIZE = 20


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_tale(tale: str):
    """Print the folk tale in dim italic styling."""
    print()
    for line in tale.splitlines():
        print(f"  {TALE}{line}{RESET}")
    print()


def _print_riddle(riddle: str):
    """Print the riddle in bold yellow."""
    print(f"  {RIDDLE}Tell me, Vikram:{RESET}")
    print()
    for line in riddle.splitlines():
        print(f"  {RIDDLE}{line}{RESET}")
    print()
    print(f"  {DIM}If you know the answer and keep silent,{RESET}")
    print(f"  {DIM}your head will burst into a thousand pieces.{RESET}")
    print()


def _prompt_answer() -> str:
    """Prompt the user for their answer.  Returns the stripped string."""
    try:
        answer = input(f"  {GHOST}Your answer, Vikram › {RESET}")
        return answer.strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


# ── Main encounter ────────────────────────────────────────────────────────────

def run_encounter(diff_text: str, commit_sha: str = None) -> bool:
    """Run the full Vetal encounter.

    Parameters
    ----------
    diff_text : str
        The raw unified diff to review.
    commit_sha : str, optional
        The commit SHA being pushed (used for memory).

    Returns
    -------
    bool
        ``True`` if the push should proceed, ``False`` if blocked.
    """
    # ── 1. Memory check ──────────────────────────────────────────────────
    if commit_sha and has_answered(commit_sha):
        print(
            f"\n  {GHOST}Vetal remembers you, Vikram.  "
            f"You may pass.{RESET}\n"
        )
        return True

    # ── 2. Ollama availability ────────────────────────────────────────────
    if not is_ollama_running():
        strict = os.environ.get("VETAL_STRICT", "0") == "1"
        if strict:
            print(
                f"\n  {WARN}{BOLD}⚠ Vetal cannot reach Ollama, "
                f"and VETAL_STRICT=1.{RESET}"
            )
            print(
                f"  {WARN}Start Ollama or unset VETAL_STRICT to push.{RESET}\n"
            )
            return False
        else:
            print(
                f"\n  {DIM}🌙 Vetal sleeps — Ollama is not running.  "
                f"You may pass.{RESET}\n"
            )
            return True

    # ── 3. Trim the diff ─────────────────────────────────────────────────
    trimmed = trim_diff(diff_text)
    if not trimmed or len(trimmed.strip()) < _MIN_DIFF_SIZE:
        print(
            f"\n  {DIM}The change is too small to wake Vetal.  "
            f"You may pass.{RESET}\n"
        )
        return True

    # ── 4. Generate riddle ───────────────────────────────────────────────
    print(f"\n  {TREE}🌳 Something heavy drops onto your shoulders "
          f"from the tamarind tree...{RESET}\n")

    riddle_data = generate_riddle(trimmed)
    if riddle_data is None:
        print(
            f"  {DIM}Vetal opens his mouth but no words come out.  "
            f"(Model error — you may pass.){RESET}\n"
        )
        return True

    tale = riddle_data.get("tale", "")
    riddle = riddle_data.get("riddle", "")
    answer_key = riddle_data.get("answer_key", [])

    if not riddle:
        print(f"  {DIM}Vetal has nothing to ask.  You may pass.{RESET}\n")
        return True

    # ── 5. Present the encounter ─────────────────────────────────────────
    if tale:
        _print_tale(tale)

    _print_riddle(riddle)

    # ── 6. Get the developer's answer ────────────────────────────────────
    answer = _prompt_answer()

    if not answer:
        print(
            f"\n  {WARN}Silence.  Vetal clings tighter.{RESET}"
        )
        print(
            f"  {DIM}Push blocked.  Answer the riddle or use "
            f"git push --no-verify.{RESET}\n"
        )
        return False

    # ── 7. Judge the answer ──────────────────────────────────────────────
    print(f"\n  {DIM}Vetal considers your words...{RESET}\n")

    verdict = judge_answer(trimmed, riddle, answer_key, answer)

    if verdict is None:
        # Model error during judging — let them pass
        print(
            f"  {DIM}Vetal cannot decide.  "
            f"(Model error — you may pass.){RESET}\n"
        )
        if commit_sha:
            record_answer(commit_sha)
        return True

    response_text = verdict.get("response", "")

    if verdict["verdict"] == "release":
        # ── Success ──────────────────────────────────────────────────
        print(f"  {SUCCESS}{BOLD}✓ {response_text}{RESET}")
        print(
            f"\n  {GHOST}Vetal leaps off your shoulders and flies "
            f"back to the tamarind tree.{RESET}\n"
        )
        if commit_sha:
            record_answer(commit_sha)
        return True
    else:
        # ── Failure ──────────────────────────────────────────────────
        print(f"  {WARN}{BOLD}✗ {response_text}{RESET}")
        print(
            f"\n  {GHOST}Vetal clings to your back, cackling.{RESET}"
        )
        print(
            f"  {DIM}Push blocked.  Try again or use "
            f"git push --no-verify.{RESET}\n"
        )
        return False
