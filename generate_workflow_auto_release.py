"""Generate a GitHub Actions workflow for automatic releases on version bump."""
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

_script_dir = str(Path(__file__).parent.resolve())
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

WORKFLOW_CONTENT = """\
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Check for version change
        id: version
        run: |
          CURRENT=$(python3 -c "import json; print(json.load(open('manifest.json'))['version'])")
          PREVIOUS=$(git show HEAD~1:manifest.json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])" 2>/dev/null || echo "")
          if [ "$CURRENT" != "$PREVIOUS" ] && [ -n "$PREVIOUS" ]; then
            echo "changed=true" >> "$GITHUB_OUTPUT"
            echo "version=$CURRENT" >> "$GITHUB_OUTPUT"
            echo "Version changed: $PREVIOUS -> $CURRENT"
          else
            echo "changed=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Create release
        if: steps.version.outputs.changed == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          VERSION="v${{ steps.version.outputs.version }}"
          git tag "$VERSION"
          git push origin "$VERSION"
          gh release create "$VERSION" \\
            --title "$VERSION" \\
            --generate-notes
"""


def _check_repo_public(github_url: str) -> bool | None:
    """Check if a GitHub repo is public via the API. Returns True/False, or None if unknown."""
    if not github_url:
        return None
    # Extract owner/repo from URL
    url = github_url.rstrip("/")
    parts = url.split("github.com/")
    if len(parts) != 2:
        return None
    repo_path = parts[1].rstrip("/")
    api_url = f"https://api.github.com/repos/{repo_path}"
    try:
        req = Request(api_url, headers={"User-Agent": "talon-pack"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return not data.get("private", True)
    except URLError:
        return None
    except Exception:
        return None


def generate_workflow(package_dir: str):
    """Generate .github/workflows/release.yml in the target directory."""
    from diff_utils import GREEN, YELLOW, CYAN, DIM, RESET

    full_dir = os.path.abspath(package_dir)
    if not os.path.isdir(full_dir):
        print(f"Error: Directory not found: {full_dir}")
        sys.exit(1)

    # Check repo visibility
    manifest_path = os.path.join(full_dir, "manifest.json")
    github_url = ""
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            github_url = json.load(f).get("github", "")

    is_public = _check_repo_public(github_url)
    if is_public is False:
        print(f"  {YELLOW}Warning: Repository appears to be private.{RESET}")
        print(f"  GitHub Actions minutes cost money on private repos.")
        print(f"  Use --force to generate anyway.")
        if "--force" not in sys.argv:
            sys.exit(1)
    elif is_public is None and not github_url:
        print(f"  {YELLOW}Warning: No github URL in manifest.json.{RESET}")
        print(f"  Cannot verify repo is public. GitHub Actions minutes cost money on private repos.")
        print(f"  Use --force to generate anyway.")
        if "--force" not in sys.argv:
            sys.exit(1)

    workflow_dir = os.path.join(full_dir, ".github", "workflows")
    workflow_path = os.path.join(workflow_dir, "release.yml")

    dry_run = "--dry-run" in sys.argv

    if os.path.exists(workflow_path):
        with open(workflow_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == WORKFLOW_CONTENT:
            print(f"  {DIM}release.yml already up to date{RESET}")
            return
        print(f"  {YELLOW}release.yml already exists and differs{RESET}")
        print(f"  Use --force to overwrite")
        if "--force" not in sys.argv:
            return

    if dry_run:
        print(f"  {CYAN}Would create:{RESET} .github/workflows/release.yml")
        return

    os.makedirs(workflow_dir, exist_ok=True)
    with open(workflow_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(WORKFLOW_CONTENT)
    print(f"  {GREEN}Created:{RESET} .github/workflows/release.yml")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_workflow_auto_release.py <directory>")
        sys.exit(1)

    generate_workflow(sys.argv[1])
