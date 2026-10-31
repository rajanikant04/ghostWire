"""Command-line interface for Vetal — the ghost on your git push."""

import argparse
import json
import sys

# Windows console encoding safeguard
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from vetal import __version__
from vetal.hook import install_hook, uninstall_hook
from vetal.diff import get_working_diff, get_push_diff, trim_diff
from vetal.encounter import run_encounter
from vetal.model import is_ollama_running, generate_riddle, judge_answer

# ── ANSI helpers ──────────────────────────────────────────────────────────────

TREE = "\033[32m"
GHOST = "\033[35m"
WARN = "\033[31m"
SUCCESS = "\033[32m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def _banner():
    """Print a short Vetal banner."""
    print(f"{GHOST}{BOLD}")
    print(r"  .---------------------------.")
    print(r"  |   *   V E T A L   P R     |")
    print(r"  |  the ghost on your push   |")
    print(r"  '---------------------------'")
    print(f"{RESET}")


# ── Subcommand handlers ──────────────────────────────────────────────────────

def _cmd_install(args):
    """Install the pre-push git hook."""
    _banner()
    install_hook()


def _cmd_uninstall(args):
    """Remove the pre-push git hook."""
    _banner()
    uninstall_hook()


def _cmd_ask(args):
    """Manually trigger Vetal against the working-tree diff (for testing)."""
    _banner()
    diff_text = get_working_diff()
    if not diff_text or not diff_text.strip():
        print(f"{WARN}No diff found. Stage or commit something first.{RESET}")
        print(f"{DIM}Tip: Try 'vetal demo' to see an encounter with a sample diff.{RESET}")
        sys.exit(0)

    ok = run_encounter(diff_text, commit_sha=None)
    sys.exit(0 if ok else 1)


def _cmd_demo(args):
    """Run an interactive demo encounter using a sample diff."""
    _banner()
    sample_diff = r"""diff --git a/auth/validator.py b/auth/validator.py
index 4a12b3c..7d89e1f 100644
--- a/auth/validator.py
+++ b/auth/validator.py
@@ -14,6 +14,3 @@ def validate_user_payload(data: dict) -> bool:
     if not data.get("username"):
         raise ValidationError("username is required")
-    if "email" not in data or not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
-        raise ValidationError("valid email is required")
     return True
"""
    print(f"  {DIM}[Demo mode: testing with sample diff (removed email check in auth/validator.py)]{RESET}\n")

    if is_ollama_running():
        ok = run_encounter(sample_diff, commit_sha=None)
        sys.exit(0 if ok else 1)

    # If Ollama is not active, run an interactive simulation so the user can experience the UX immediately
    print(f"  {DIM}🌙 Ollama is not running locally. Demonstrating Vetal encounter simulation:{RESET}\n")
    print(f"  {TREE}🌳 Something heavy drops onto your shoulders from the tamarind tree...{RESET}\n")
    print(f"  {DIM}In the kingdom of Avanti, the old gatekeeper was told he need no longer ask travellers their names.{RESET}")
    print(f"  {DIM}That night, a stranger with no name walked in, and by morning the treasury was hollow.{RESET}\n")
    print(f"  {BOLD}Tell me, Vikram:{RESET} validate_user_payload() no longer checks email format.")
    print(f"  What happens when someone submits an invalid or empty email?")
    print()
    print(f"  {DIM}If you know the answer and keep silent,{RESET}")
    print(f"  {DIM}your head will burst into a thousand pieces.{RESET}\n")

    try:
        ans = input(f"  {GHOST}Your answer, Vikram › {RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)

    if not ans:
        print(f"\n  {WARN}Silence.  Vetal clings tighter.{RESET}\n")
        sys.exit(1)

    print(f"\n  {DIM}Vetal considers your words...{RESET}\n")
    keywords = ["db", "database", "constraint", "500", "pass", "crash", "downstream", "fail", "empty", "null", "none"]
    if any(k in ans.lower() for k in keywords):
        print(f"  {SUCCESS}{BOLD}✓ You speak true. Unvalidated input will pass directly into the persistence layer and trigger a 500.{RESET}")
        print(f"\n  {GHOST}Vetal leaps off your shoulders and flies back to the tamarind tree.{RESET}\n")
        sys.exit(0)
    else:
        print(f"  {WARN}{BOLD}✗ You evade the danger, Vikram. You do not see what shatters downstream.{RESET}")
        print(f"\n  {GHOST}Vetal clings to your back, cackling.{RESET}\n")
        sys.exit(1)


def _cmd_judge(args):
    """Called by the pre-push hook.  Reads diff from stdin."""
    # The hook pipes the diff into stdin
    if sys.stdin.isatty():
        # No piped input — try to read diff ourselves
        diff_text = get_working_diff()
    else:
        diff_text = sys.stdin.read()

    if not diff_text or not diff_text.strip():
        # Nothing to review
        sys.exit(0)

    # Re-open /dev/tty (or CON on Windows) so we can prompt the user
    # even though stdin was consumed by the pipe.
    try:
        import os
        tty_path = "CON" if os.name == "nt" else "/dev/tty"
        tty = open(tty_path, "r")
        sys.stdin = tty
    except OSError:
        # Can't open terminal — non-interactive, let it pass
        sys.exit(0)

    commit_sha = args.commit_sha if hasattr(args, "commit_sha") and args.commit_sha else None
    ok = run_encounter(diff_text, commit_sha=commit_sha)
    sys.exit(0 if ok else 1)


def _cmd_riddle(args):
    """Generate a riddle from a diff (CI/headless mode).

    Reads diff from stdin, generates a riddle, and prints JSON to stdout.
    Used by the GitHub Actions workflow.
    """
    if sys.stdin.isatty():
        diff_text = get_working_diff()
    else:
        diff_text = sys.stdin.read()

    if not diff_text or not diff_text.strip():
        json.dump({"tale": "", "riddle": "", "answer_key": []}, sys.stdout)
        sys.exit(0)

    trimmed = trim_diff(diff_text)
    if not trimmed or len(trimmed.strip()) < 20:
        json.dump({"tale": "", "riddle": "", "answer_key": []}, sys.stdout)
        sys.exit(0)

    result = generate_riddle(trimmed)
    if result is None:
        print("Error: Could not generate riddle (is Ollama running?)", file=sys.stderr)
        json.dump({"tale": "", "riddle": "", "answer_key": []}, sys.stdout)
        sys.exit(1)

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False)
    else:
        print(f"\n  {TREE}🌳 Tale:{RESET}")
        print(f"  {DIM}{result.get('tale', '')}{RESET}\n")
        print(f"  {BOLD}Riddle:{RESET} {result.get('riddle', '')}\n")
        print(f"  {DIM}Answer key: {result.get('answer_key', [])}{RESET}")


def _cmd_judge_pr(args):
    """Judge an answer against a diff (CI/headless mode).

    Reads diff and answer from files, generates a riddle internally,
    judges the answer, and prints JSON to stdout.
    Used by the GitHub Actions workflow.
    """
    # Read diff
    try:
        with open(args.diff_file, "r", encoding="utf-8") as fh:
            diff_text = fh.read()
    except OSError as e:
        print(f"Error reading diff file: {e}", file=sys.stderr)
        sys.exit(1)

    # Read answer
    try:
        with open(args.answer_file, "r", encoding="utf-8") as fh:
            answer = fh.read().strip()
    except OSError as e:
        print(f"Error reading answer file: {e}", file=sys.stderr)
        sys.exit(1)

    if not diff_text or not diff_text.strip():
        json.dump({"verdict": "release", "response": "No diff to review."}, sys.stdout)
        sys.exit(0)

    trimmed = trim_diff(diff_text)

    # First generate the riddle (to get the answer key)
    riddle_data = generate_riddle(trimmed)
    if riddle_data is None:
        print("Error: Could not generate riddle (is Ollama running?)", file=sys.stderr)
        json.dump({"verdict": "release", "response": "Vetal could not speak."}, sys.stdout)
        sys.exit(1)

    riddle = riddle_data.get("riddle", "")
    answer_key = riddle_data.get("answer_key", [])

    # Now judge the answer
    result = judge_answer(trimmed, riddle, answer_key, answer)
    if result is None:
        json.dump({"verdict": "release", "response": "Vetal could not decide."}, sys.stdout)
        sys.exit(1)

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False)
    else:
        verdict_icon = "✓" if result["verdict"] == "release" else "✗"
        print(f"\n  {verdict_icon} {result.get('response', '')}")


def _cmd_status(args):
    """Check if Vetal is installed and Ollama is reachable."""
    _banner()

    # Check git hook
    try:
        from vetal.hook import get_git_dir
        import os
        git_dir = get_git_dir()
        hook_path = os.path.join(git_dir, "hooks", "pre-push")
        if os.path.exists(hook_path):
            with open(hook_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            if "Vetal" in content:
                print(f"  {SUCCESS}✓ Pre-push hook: installed{RESET}")
            else:
                print(f"  {WARN}✗ Pre-push hook: present but not Vetal's{RESET}")
        else:
            print(f"  {WARN}✗ Pre-push hook: not installed{RESET}")
    except RuntimeError as e:
        print(f"  {WARN}✗ Git: {e}{RESET}")

    # Check Ollama
    if is_ollama_running():
        from vetal.model import DEFAULT_MODEL
        print(f"  {SUCCESS}✓ Ollama: reachable{RESET}")
        print(f"  {DIM}  Model: {DEFAULT_MODEL}{RESET}")
    else:
        print(f"  {WARN}✗ Ollama: not reachable{RESET}")
        print(f"  {DIM}  Start Ollama or set VETAL_OLLAMA_URL{RESET}")

    print()


# ── Main entry point ─────────────────────────────────────────────────────────

def main():
    """Parse arguments and dispatch to the right subcommand."""
    parser = argparse.ArgumentParser(
        prog="vetal",
        description="Vetal — the ghost that won't let you push until you explain your own diff.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # install
    sp_install = subparsers.add_parser(
        "install",
        help="Install the Vetal pre-push hook into the current repo",
    )
    sp_install.set_defaults(func=_cmd_install)

    # uninstall
    sp_uninstall = subparsers.add_parser(
        "uninstall",
        help="Remove the Vetal pre-push hook",
    )
    sp_uninstall.set_defaults(func=_cmd_uninstall)

    # ask
    sp_ask = subparsers.add_parser(
        "ask",
        help="Manually trigger Vetal against the current diff (for testing)",
    )
    sp_ask.set_defaults(func=_cmd_ask)

    # demo
    sp_demo = subparsers.add_parser(
        "demo",
        help="Run an interactive demo encounter with a realistic sample diff",
    )
    sp_demo.set_defaults(func=_cmd_demo)

    # judge (used by the hook)
    sp_judge = subparsers.add_parser(
        "judge",
        help="(internal) Read diff from stdin and run the riddle→answer→judge flow",
    )
    sp_judge.add_argument(
        "commit_sha",
        nargs="?",
        default=None,
        help="Commit SHA being pushed",
    )
    sp_judge.set_defaults(func=_cmd_judge)

    # riddle (used by CI — generates riddle from stdin diff, outputs JSON)
    sp_riddle = subparsers.add_parser(
        "riddle",
        help="(CI) Generate a riddle from a diff piped to stdin",
    )
    sp_riddle.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )
    sp_riddle.set_defaults(func=_cmd_riddle)

    # judge-pr (used by CI — judges an answer from files, outputs JSON)
    sp_judge_pr = subparsers.add_parser(
        "judge-pr",
        help="(CI) Judge an answer against a diff, both read from files",
    )
    sp_judge_pr.add_argument(
        "--diff-file",
        required=True,
        help="Path to file containing the diff",
    )
    sp_judge_pr.add_argument(
        "--answer-file",
        required=True,
        help="Path to file containing the answer",
    )
    sp_judge_pr.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )
    sp_judge_pr.set_defaults(func=_cmd_judge_pr)

    # status
    sp_status = subparsers.add_parser(
        "status",
        help="Check if Vetal is installed and Ollama is reachable",
    )
    sp_status.set_defaults(func=_cmd_status)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)
