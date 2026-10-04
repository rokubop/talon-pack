"""Release notes for `tpack release`: a draft from the commits since the
last tag, edited in your git editor, then used as both the annotated tag
message and the GitHub release body.

GitHub's --generate-notes only lists merged PRs, so a repo pushed to
directly got releases with nothing in them.
"""
import os
import re
import subprocess

SCISSORS = "# ------------------------ >8 ------------------------"

# Commits that are the release itself, not something in it
SKIP = re.compile(r"^(bump|update|set) (the )?version\b", re.IGNORECASE)


def draft(tag: str, prev_tag: str | None, subjects: list[str]) -> str:
    """Bullets from commit subjects, then everything after the scissors
    line: instructions, dropped on save."""
    bullets = [f"- {s.strip()}" for s in subjects if s.strip() and not SKIP.match(s.strip())]
    since = f"since {prev_tag}" if prev_tag else "so far"
    return "\n".join([
        *bullets,
        "",
        SCISSORS,
        "# Everything from the line above down is dropped.",
        f"# Release notes for {tag}, from the commits {since}.",
        "# Write them for people using the package: trim, merge, reword.",
        "# Headings like ### Fixes or ### Added are fine.",
        "# Save and close to continue. Empty notes cancel the release.",
        "",
    ])


def clean(text: str) -> str:
    """The notes as written: everything above the scissors, trimmed."""
    lines = text.replace("\r\n", "\n").split("\n")
    if SCISSORS in lines:
        lines = lines[:lines.index(SCISSORS)]
    return "\n".join(lines).strip()


def subjects(directory, log_range: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", log_range, "--format=%s", "--no-merges"],
        capture_output=True, text=True, cwd=str(directory),
    )
    return result.stdout.splitlines() if result.returncode == 0 else []


def editor(directory) -> str:
    """The editor git would use for a commit message."""
    for name in ("GIT_EDITOR", "VISUAL", "EDITOR"):
        if os.environ.get(name):
            return os.environ[name]
    result = subprocess.run(["git", "var", "GIT_EDITOR"], capture_output=True, text=True,
                            cwd=str(directory))
    return result.stdout.strip() if result.returncode == 0 else ""


def edit(path, directory) -> bool:
    """Open `path` in the editor and wait for it to close."""
    command = editor(directory)
    if not command:
        return False
    return subprocess.run(f'{command} "{path}"', shell=True).returncode == 0
