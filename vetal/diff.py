"""Diff parsing and smart trimming for Vetal.

Reads git diffs and trims them to a sensible context budget so the LLM
gets a focused, representative slice of the change.
"""

import re
import subprocess

# ── Boring-file patterns ──────────────────────────────────────────────────────

_LOCKFILES = frozenset({
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "pnpm-lock.yaml",
    "composer.lock",
    "Gemfile.lock",
})

_BORING_EXTENSIONS = frozenset({
    ".min.js",
    ".min.css",
    ".svg",
    ".map",
})

_BINARY_MARKER = re.compile(r"^Binary files .+ differ$", re.MULTILINE)

# Header that starts each file in a unified diff
_DIFF_FILE_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)


def is_boring_file(filename: str) -> bool:
    """Return True if *filename* is a lockfile, minified asset, map, SVG, or image."""
    basename = filename.rsplit("/", 1)[-1] if "/" in filename else filename
    if basename in _LOCKFILES:
        return True
    lower = filename.lower()
    for ext in _BORING_EXTENSIONS:
        if lower.endswith(ext):
            return True
    # Common image extensions
    if re.search(r"\.(png|jpe?g|gif|ico|bmp|webp|tiff?|avif)$", lower):
        return True
    return False


# ── Git helpers ───────────────────────────────────────────────────────────────

def _run_git(*args: str) -> str:
    """Run a git command and return its stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def get_push_diff(remote: str, refspecs: str) -> str:
    """Get the diff between the local branch and the remote for a push.

    Parameters
    ----------
    remote : str
        Name of the remote (e.g. ``"origin"``).
    refspecs : str
        Refspec string containing ``local_sha remote_sha``.

    Returns
    -------
    str
        The unified diff text.
    """
    parts = refspecs.strip().split()
    if len(parts) >= 4:
        _local_ref, local_sha, _remote_ref, remote_sha = parts[:4]
    elif len(parts) >= 2:
        local_sha, remote_sha = parts[0], parts[1]
    else:
        return get_working_diff()

    null_sha = "0" * 40

    if local_sha == null_sha:
        # Deleting a branch — nothing to review
        return ""

    if remote_sha == null_sha:
        # New branch — diff last 5 commits
        diff = _run_git("diff", "--no-color", f"{local_sha}~5..{local_sha}")
        if not diff:
            diff = _run_git("diff", "--no-color", local_sha)
        return diff

    return _run_git("diff", "--no-color", f"{remote_sha}..{local_sha}")


def get_working_diff() -> str:
    """Get ``git diff HEAD`` for the interactive ``ask`` command."""
    diff = _run_git("diff", "--no-color", "HEAD")
    if not diff:
        # Maybe nothing is committed yet; try staged diff
        diff = _run_git("diff", "--no-color", "--cached")
    if not diff:
        # Try unstaged diff
        diff = _run_git("diff", "--no-color")
    return diff


# ── Smart trim ────────────────────────────────────────────────────────────────

def _split_into_file_diffs(raw_diff: str) -> list:
    """Split a unified diff into per-file chunks.

    Returns a list of ``(filename, chunk_text)`` tuples.
    """
    positions = [m.start() for m in _DIFF_FILE_HEADER.finditer(raw_diff)]
    if not positions:
        return [("unknown", raw_diff)]

    chunks = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(raw_diff)
        chunk = raw_diff[pos:end]
        match = _DIFF_FILE_HEADER.match(chunk)
        fname = match.group(2) if match else "unknown"
        chunks.append((fname, chunk))
    return chunks


def trim_diff(raw_diff: str, max_bytes: int = 12000) -> str:
    """Trim *raw_diff* to at most *max_bytes*, keeping interesting files.

    Strategy
    --------
    1. Drop boring files (lockfiles, minified, SVGs, images, binary diffs).
    2. Give each remaining file a fair share of the byte budget proportional
       to its original size, with a minimum share of 400 bytes.
    3. If a file's chunk exceeds its share, keep the first *share* bytes,
       cutting at the last newline boundary.
    """
    if not raw_diff:
        return ""

    # Remove binary-diff markers entirely
    cleaned = _BINARY_MARKER.sub("", raw_diff)

    chunks = _split_into_file_diffs(cleaned)

    # Filter out boring files
    interesting = [(f, c) for f, c in chunks if not is_boring_file(f)]

    if not interesting:
        return ""

    total_size = sum(len(c) for _, c in interesting)

    if total_size <= max_bytes:
        return "".join(c for _, c in interesting)

    # Proportional allocation with a minimum share
    min_share = 400
    result_parts = []
    for fname, chunk in interesting:
        share = max(min_share, int(max_bytes * len(chunk) / total_size))
        if len(chunk) <= share:
            result_parts.append(chunk)
        else:
            # Cut at last newline within the share
            cut = chunk[:share]
            last_nl = cut.rfind("\n")
            if last_nl > 0:
                cut = cut[: last_nl + 1]
            cut += f"\n... (trimmed {fname})\n"
            result_parts.append(cut)

    result = "".join(result_parts)

    # Final safety cap
    if len(result) > max_bytes:
        result = result[:max_bytes]
        last_nl = result.rfind("\n")
        if last_nl > 0:
            result = result[: last_nl + 1]
        result += "\n... (trimmed to fit context)\n"

    return result
