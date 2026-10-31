"""Persistent memory for Vetal — remembers which commits have been answered.

Data is stored in ``.git/vetal/answered.json``, a JSON dict mapping
commit SHAs to timestamps.  File writes are thread-safe via a simple
lockfile strategy.
"""

import json
import os
import time

from vetal.hook import get_git_dir

# ── Helpers ───────────────────────────────────────────────────────────────────


def _memory_path() -> str:
    """Return the absolute path to the answered.json file."""
    git_dir = get_git_dir()
    vetal_dir = os.path.join(git_dir, "vetal")
    os.makedirs(vetal_dir, exist_ok=True)
    return os.path.join(vetal_dir, "answered.json")


def _load() -> dict:
    """Load the memory dict from disk, or return an empty dict."""
    path = _memory_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict):
    """Write *data* to the memory file atomically (write-then-rename).

    This provides basic thread safety — the file is never in a
    half-written state.
    """
    path = _memory_path()
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        # Atomic-ish rename (Windows replaces if dest exists in Python 3.3+)
        if os.name == "nt" and os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.replace(tmp_path, path)
    except OSError:
        # Best-effort — don't crash the push over a memory write failure
        pass


# ── Public API ────────────────────────────────────────────────────────────────


def has_answered(sha: str) -> bool:
    """Return ``True`` if commit *sha* has already been answered."""
    if not sha:
        return False
    data = _load()
    return sha in data


def record_answer(sha: str):
    """Record that the developer correctly answered Vetal's riddle for *sha*."""
    if not sha:
        return
    data = _load()
    data[sha] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "answered",
    }
    _save(data)


def record_skip(sha: str):
    """Record that the developer used ``--no-verify`` to skip Vetal.

    Vetal remembers.
    """
    if not sha:
        return
    data = _load()
    data[sha] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "skipped",
    }
    _save(data)
