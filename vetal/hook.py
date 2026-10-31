"""Git hook management for Vetal.

Installs and uninstalls the ``pre-push`` hook that summons Vetal
whenever ``git push`` is run.
"""

import os
import shutil
import stat
import subprocess

# ── ANSI helpers ──────────────────────────────────────────────────────────────

SUCCESS = "\033[32m"
WARN = "\033[31m"
GHOST = "\033[35m"
RESET = "\033[0m"
BOLD = "\033[1m"

# ── Marker used to identify our hook ─────────────────────────────────────────

_VETAL_MARKER = "Vetal"

# ── Hook script ───────────────────────────────────────────────────────────────

_HOOK_SCRIPT = r"""#!/bin/sh
# 🌳 Vetal — the ghost on your git push
# Remove this file or run 'vetal uninstall' to silence him.

# If not a terminal (GUI client, CI), let it pass
if [ ! -t 0 ] && [ ! -t 1 ]; then
    exit 0
fi

# Read the push info from stdin
while read local_ref local_sha remote_ref remote_sha; do
    # Skip delete pushes
    if [ "$local_sha" = "0000000000000000000000000000000000000000" ]; then
        continue
    fi

    # Get the diff
    if [ "$remote_sha" = "0000000000000000000000000000000000000000" ]; then
        DIFF=$(git diff --no-color HEAD~5..HEAD 2>/dev/null || git diff --no-color HEAD)
    else
        DIFF=$(git diff --no-color "$remote_sha".."$local_sha")
    fi

    # Skip if no diff
    if [ -z "$DIFF" ]; then
        continue
    fi

    # Ask Vetal
    echo "$DIFF" | python -m vetal judge "$local_sha"
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        exit 1
    fi
done

exit 0
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_git_dir() -> str:
    """Return the path to the ``.git`` directory for the current repo.

    Raises
    ------
    RuntimeError
        If not inside a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Not a git repository (git rev-parse failed): {result.stderr.strip()}"
            )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("git is not installed or not on PATH")


# ── Install / Uninstall ──────────────────────────────────────────────────────

def install_hook():
    """Install the Vetal pre-push hook into the current repo.

    If a pre-push hook already exists, it is backed up to
    ``pre-push.vetal-backup`` before being overwritten.
    """
    git_dir = get_git_dir()
    hooks_dir = os.path.join(git_dir, "hooks")
    hook_path = os.path.join(hooks_dir, "pre-push")
    backup_path = hook_path + ".vetal-backup"

    os.makedirs(hooks_dir, exist_ok=True)

    # Back up existing hook (if it isn't already ours)
    if os.path.exists(hook_path):
        try:
            with open(hook_path, "r", encoding="utf-8") as fh:
                existing = fh.read()
        except (OSError, UnicodeDecodeError):
            existing = ""

        if _VETAL_MARKER in existing:
            print(f"{GHOST}Vetal's hook is already installed.  Re-writing it.{RESET}")
        else:
            shutil.copy2(hook_path, backup_path)
            print(
                f"{WARN}Existing pre-push hook backed up to "
                f"{os.path.basename(backup_path)}{RESET}"
            )

    # Write the hook
    with open(hook_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_HOOK_SCRIPT)

    # Make executable on Unix-like systems
    if os.name != "nt":
        st = os.stat(hook_path)
        os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"{SUCCESS}{BOLD}🌳 Vetal is now watching your pushes.{RESET}")
    print(f"   Hook installed at {hook_path}")
    print(f"   Run {GHOST}vetal uninstall{RESET} to remove him.")


def uninstall_hook():
    """Remove the Vetal pre-push hook.

    Only removes the hook if it contains the Vetal marker comment.
    Restores a backup if one exists.
    """
    git_dir = get_git_dir()
    hook_path = os.path.join(git_dir, "hooks", "pre-push")
    backup_path = hook_path + ".vetal-backup"

    if not os.path.exists(hook_path):
        print(f"{WARN}No pre-push hook found.  Vetal was not installed.{RESET}")
        return

    # Safety check — only remove hooks we created
    try:
        with open(hook_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except (OSError, UnicodeDecodeError):
        content = ""

    if _VETAL_MARKER not in content:
        print(
            f"{WARN}The current pre-push hook was not installed by Vetal.  "
            f"Leaving it alone.{RESET}"
        )
        return

    os.remove(hook_path)

    # Restore backup if available
    if os.path.exists(backup_path):
        shutil.move(backup_path, hook_path)
        print(f"{SUCCESS}Restored your previous pre-push hook from backup.{RESET}")
    else:
        print(f"{SUCCESS}🌳 Vetal releases his grip.  Pre-push hook removed.{RESET}")
