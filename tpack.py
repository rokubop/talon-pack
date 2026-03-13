"""
Run all generators in sequence: manifest, version, and readme.
Will update instead of overwriting existing code where relevant.

Usage:
  tpack [directory]              Update manifest, _version, and readme
  tpack info [dir]               List contributions, dependencies, and info
  tpack deps [dir]               Show all dependencies with install status
  tpack patch [dir]               Bump patch version (1.0.0 -> 1.0.1)
  tpack minor [dir]               Bump minor version (1.0.0 -> 1.1.0)
  tpack major [dir]               Bump major version (1.0.0 -> 2.0.0)
  tpack version patch [dir]       Same as above (long form)
  tpack install [dir]              Install dependencies from manifest
  tpack install <github_url>       Install a repo (+ its dependencies)
  tpack update [dir]               Pull latest for all dependencies
  tpack outdated [dir]             Check for newer versions (local vs remote)
  tpack sync [dep] [dir]           Update dependency min_version to installed version
  tpack sync [dir]                 Update all dependencies to installed versions
  tpack release [dir]              Create a GitHub release for the current version
  tpack status [dir]               Show current status
  tpack status <value> [dir]       Set status (experimental, preview, stable, etc.)
  tpack duplicate-check [dir]      Show current duplicate check setting
  tpack duplicate-check on [dir]   Enable duplicate check in _version.py
  tpack duplicate-check off [dir]  Disable duplicate check in _version.py
  tpack platform [dir]             Show current platforms
  tpack platform add <p> [dir]     Add platform (windows, mac, linux)
  tpack platform remove <p> [dir]  Remove platform
  tpack pip add <pkg> [dir]        Add pip dependency (e.g. vgamepad, vgamepad>=1.0.0)
  tpack pip remove <pkg> [dir]     Remove pip dependency
  tpack pip list [dir]             List pip dependencies
  tpack deps add <pkg|url> [dir]   Add dependency [--optional] [--dev] [--description "..."]
  tpack deps remove <pkg> [dir]    Remove dependency
  tpack deps set <pkg> [dir]      Set properties [--optional] [--dev] [--description "..."]
                                   Use --no-optional, --no-dev, --no-description to remove
  tpack generate <type> [dir]      Generate a specific file
    manifest                       Generate manifest.json
    version                        Generate _version.py
    readme                         Generate README.md
    shields                        Generate shield badges
    install-block                  Generate install block (outputs to console)
    install-block-tpack            Generate install block with tpack option (outputs to console)
    workflow-auto-release          Generate .github/workflows/release.yml
  tpack --dry-run                  Preview changes without writing files
  tpack --yes, -y                  Skip confirmation prompts
  tpack -v, --verbose              Show detailed output (default: show only changes)
  tpack --version, -V              Show tpack version
  tpack --search <path>            Search <path> for dependencies (relative or absolute)
  tpack --force                    Force operation (e.g. generate workflow without github URL)
  tpack --skip-version-check       Skip version check on startup
  tpack --help                     Show this help message

Config:
  Edit tpack.config.json to change default behavior (which generators run by default).
"""

import sys

if sys.version_info < (3, 12):
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    sys.exit(
        f"Python 3.12 or higher is required (you have {current_version}).\n"
        f"Update your tpack alias to use Talon's bundled Python.\n"
        f"See: https://github.com/rokubop/talon-pack#troubleshooting"
    )

import subprocess
import tempfile
import os
import json
from pathlib import Path

# Ensure UTF-8 output on Windows (avoid charmap encoding errors with emojis etc.)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "tpack.config.json"

# Ensure sibling modules (e.g. diff_utils) are importable when using Talon's bundled Python
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

def check_local_changes(directory: Path, include_commits_ahead: bool = False) -> str | None:
    """Check if the git repo has uncommitted changes (and optionally commits ahead of remote).
    Returns a warning message string, or None if clean."""
    import subprocess
    git_dir = directory / ".git"
    if not git_dir.exists():
        return None

    warnings = []
    try:
        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=directory
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            warnings.append(f"{len(lines)} uncommitted change{'s' if len(lines) != 1 else ''}")

        # Check for commits ahead of remote
        if include_commits_ahead:
            result = subprocess.run(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                capture_output=True, text=True, cwd=directory
            )
            if result.returncode == 0:
                count = int(result.stdout.strip())
                if count > 0:
                    warnings.append(f"{count} commit{'s' if count != 1 else ''} ahead of remote")
    except Exception:
        pass

    if warnings:
        return ", ".join(warnings)
    return None


def bump_version(version: str, bump_type: str) -> str:
    """Bump a semver version string."""
    major, minor, patch = map(int, version.split('.'))
    if bump_type == 'major':
        return f"{major + 1}.0.0"
    elif bump_type == 'minor':
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def version_command(bump_type: str, directory: Path, dry_run: bool = False) -> bool:
    """Handle version bump subcommand."""
    from diff_utils import GREEN, RED, CYAN, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
            manifest = json.loads(old_content)

        old_version = manifest.get('version', '0.0.0')
        new_version = bump_version(old_version, bump_type)
        manifest['version'] = new_version

        new_content = json.dumps(manifest, indent=2)

        # Show diff
        print(f"\n{CYAN}{directory.name}/{RESET}")
        has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
        if has_changes:
            print(format_diff_output(diff_output))

        if not dry_run:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Update shields if not explicitly disabled (version badge needs updating)
            if manifest.get('_generatorShields', True):
                readme_path = directory / "README.md"
                if readme_path.exists():
                    run_generator("generate_shields.py", str(directory))

        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


VALID_STATUSES = [
    "reference", "prototype", "experimental", "preview",
    "stable", "deprecated", "archived",
]


def status_command(new_status: str | None, directory: Path, dry_run: bool = False) -> bool:
    """Show or update the package status in manifest.json."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
            manifest = json.loads(old_content)

        current_status = manifest.get('status', '')

        # Show current status
        if new_status is None:
            name = manifest.get('name', directory.name)
            if current_status:
                print(f"{name}: {GREEN}{current_status}{RESET}")
            else:
                print(f"{name}: {DIM}(no status set){RESET}")
            print(f"\nValid statuses: {', '.join(VALID_STATUSES)}")
            return True

        # Warn if non-standard status
        if new_status not in VALID_STATUSES:
            print(f"{YELLOW}Warning: '{new_status}' is not a standard status.{RESET}")
            print(f"Standard statuses: {', '.join(VALID_STATUSES)}")

        if current_status == new_status:
            print(f"Status already set to '{new_status}'")
            return True

        manifest['status'] = new_status
        new_content = json.dumps(manifest, indent=2)

        print(f"\n{CYAN}{directory.name}/{RESET}")
        has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
        if has_changes:
            print(format_diff_output(diff_output))

        if not dry_run:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Update shields if not explicitly disabled (status badge needs updating)
            if manifest.get('_generatorShields', True):
                readme_path = directory / "README.md"
                if readme_path.exists():
                    run_generator("generate_shields.py", str(directory))

        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


VALID_PLATFORMS = ["windows", "mac", "linux"]


def platform_command(action: str | None, platform_names: list[str] | None, directory: Path, dry_run: bool = False) -> bool:
    """Show, add, or remove platform entries in manifest.json."""
    from diff_utils import GREEN, RED, CYAN, DIM, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
            manifest = json.loads(old_content)

        current = manifest.get('platforms', [])
        name = manifest.get('name', directory.name)

        # Show current setting + usage
        if action is None:
            if current:
                print(f"{name}: platforms {GREEN}{', '.join(current)}{RESET}")
            else:
                print(f"{name}: platforms {DIM}(not set){RESET}")
            print(f"\nUsage:")
            print(f"  tpack platform add <platform> [...]      Add platform(s)")
            print(f"  tpack platform remove <platform> [...]   Remove platform(s)")
            print(f"\nValid platforms: {', '.join(VALID_PLATFORMS)}")
            print(f"Examples:")
            print(f"  tpack platform add windows mac")
            print(f"  tpack platform add windows,mac,linux")
            return True

        if action == "add":
            if not platform_names:
                print(f"{RED}Error: platform name required{RESET}")
                print(f"Valid platforms: {', '.join(VALID_PLATFORMS)}")
                return False

            for p in platform_names:
                if p not in VALID_PLATFORMS:
                    print(f"{RED}Error: unknown platform '{p}'{RESET}")
                    print(f"Valid platforms: {', '.join(VALID_PLATFORMS)}")
                    return False

            added = [p for p in platform_names if p not in current]
            if not added:
                print(f"{DIM}{', '.join(platform_names)} already in platforms{RESET}")
                return True

            current.extend(added)
            # Sort in canonical order
            current = [p for p in VALID_PLATFORMS if p in current]
            manifest['platforms'] = current
            manifest = reorder_manifest_key(manifest, 'platforms', 'requires')

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Added {', '.join(added)} to platforms{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True

        elif action == "remove":
            if not platform_names:
                print(f"{RED}Error: platform name required{RESET}")
                print(f"Usage: tpack platform remove <platform> [...]")
                return False

            for p in platform_names:
                if p not in current:
                    print(f"{RED}Error: '{p}' is not in platforms{RESET}")
                    if current:
                        print(f"{DIM}Current platforms: {', '.join(current)}{RESET}")
                    return False

            for p in platform_names:
                current.remove(p)

            if current:
                manifest['platforms'] = current
            elif 'platforms' in manifest:
                del manifest['platforms']

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Removed {', '.join(platform_names)} from platforms{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True

        else:
            print(f"{RED}Unknown platform action: {action}{RESET}")
            print(f"Usage:")
            print(f"  tpack platform add <platform> [...]      Add platform(s)")
            print(f"  tpack platform remove <platform> [...]   Remove platform(s)")
            return False

    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def duplicate_check_command(value: bool | None, directory: Path, dry_run: bool = False) -> bool:
    """Show or update the duplicate check setting in manifest.json."""
    from diff_utils import GREEN, RED, CYAN, DIM, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
            manifest = json.loads(old_content)

        current = manifest.get('_generatorDuplicateCheck', False)

        # Show current setting
        if value is None:
            name = manifest.get('name', directory.name)
            state = f"{GREEN}on{RESET}" if current else f"{DIM}off{RESET}"
            print(f"{name}: duplicate-check {state}")
            print(f"\nUsage: tpack duplicate-check on|off")
            return True

        if current == value:
            state = "on" if value else "off"
            print(f"Duplicate check already {state}")
            return True

        manifest['_generatorDuplicateCheck'] = value
        new_content = json.dumps(manifest, indent=2)

        print(f"\n{CYAN}{directory.name}/{RESET}")
        has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
        if has_changes:
            print(format_diff_output(diff_output))

        if not dry_run:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Regenerate _version.py to include/remove duplicate check
            run_generator("generate_version.py", str(directory), ["--force"])

        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def get_readme_intro(directory: Path, max_lines: int = 5) -> str | None:
    """Extract intro text from README.md (skips title and badges)."""
    readme_path = directory / "README.md"
    if not readme_path.exists():
        return None

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        intro_lines = []
        in_content = False

        for line in lines:
            stripped = line.strip()
            # Skip empty lines at start
            if not in_content and not stripped:
                continue
            # Skip title
            if stripped.startswith('# '):
                continue
            # Skip badges
            if stripped.startswith('![') or stripped.startswith('[!['):
                continue
            # Skip blockquotes (often notes/warnings)
            if stripped.startswith('>'):
                continue
            # Found real content
            if stripped:
                in_content = True
                intro_lines.append(stripped)
                if len(intro_lines) >= max_lines:
                    break
            elif in_content:
                # Empty line after content - stop
                break

        return ' '.join(intro_lines) if intro_lines else None
    except:
        return None


def info_command(directory: Path) -> bool:
    """Display package info from manifest.json."""
    from diff_utils import GREEN, RED, CYAN, DIM, RESET

    manifest_path = directory / "manifest.json"
    temp_manifest_path = None
    generated = False

    try:
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        else:
            # Generate a temp manifest for analysis
            temp_manifest = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            temp_manifest_path = temp_manifest.name
            temp_manifest.close()

            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "generate_manifest.py"), str(directory),
                 "--dry-run", "--output-manifest-path", temp_manifest_path],
                capture_output=True,
                text=True
            )

            if not os.path.exists(temp_manifest_path) or os.path.getsize(temp_manifest_path) == 0:
                print(f"{RED}Error: Could not analyze directory {directory}{RESET}")
                if result.stderr:
                    print(result.stderr.strip())
                if result.stdout:
                    print(result.stdout.strip())
                return False

            with open(temp_manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            generated = True

        name = manifest.get('name', directory.name)
        version = manifest.get('version', '0.0.0')
        status = manifest.get('status', '')
        description = manifest.get('description', '')
        namespace = manifest.get('namespace', '')
        github = manifest.get('github', '')

        # Header
        status_str = f" ({status})" if status else ""
        if generated:
            print(f"\n{CYAN}{name}{RESET} {DIM}(analyzed){RESET}")
        else:
            print(f"\n{CYAN}{name}{RESET} {GREEN}v{version}{RESET}{DIM}{status_str}{RESET}")
            if description:
                print(f"{description}")

        # Show README intro
        readme_intro = get_readme_intro(directory)
        if readme_intro:
            print(f"\n{DIM}{readme_intro}{RESET}")
        if github or namespace:
            print()  # blank line before metadata
        if github:
            print(f"{github}")
        if namespace:
            print(f"namespace: {namespace}")

        # Requires
        requires = manifest.get('requires', [])
        if requires:
            requires_display = {
                "talonBeta": "Talon Beta",
                "eyeTracker": "Eye Tracker",
                "parrot": "Parrot",
                "gamepad": "Gamepad",
                "streamDeck": "Stream Deck",
                "webcam": "Webcam",
            }
            print(f"\n{CYAN}Requires:{RESET}")
            for req in requires:
                display = requires_display.get(req, req)
                print(f"  {display}")

        # Contributes
        contributes = manifest.get('contributes', {})
        if contributes:
            print(f"\n{CYAN}Contributes:{RESET}")
            for category, items in sorted(contributes.items()):
                if items:
                    print(f"  {category}:")
                    for item in sorted(items):
                        print(f"    {item}")

        # Depends
        depends = manifest.get('depends', {})
        if depends:
            print(f"\n{CYAN}Depends:{RESET}")
            for category, items in sorted(depends.items()):
                if items:
                    print(f"  {category}:")
                    for item in sorted(items):
                        print(f"    {item}")

        # Dependencies
        dependencies = manifest.get('dependencies', {})
        if dependencies:
            print(f"\n{CYAN}Dependencies:{RESET}")
            for dep_name, dep_info in sorted(dependencies.items()):
                min_ver = dep_info.get('min_version') or dep_info.get('version', '')
                dep_github = dep_info.get('github', '')
                ver_display = f" >={min_ver}" if min_ver else ""
                suffix_parts = []
                if dep_info.get('optional'):
                    suffix_parts.append("optional")
                if dep_info.get('dev_only'):
                    suffix_parts.append("dev only")
                if dep_info.get('description'):
                    suffix_parts.append(dep_info['description'])
                suffix = f"  {DIM}({', '.join(suffix_parts)}){RESET}" if suffix_parts else ""
                print(f"  {dep_name}{ver_display}{suffix}")
                if dep_github:
                    print(f"    {DIM}{dep_github}{RESET}")

        # Bundled Dependencies
        bundled_dependencies = manifest.get('bundledDependencies', {})
        if bundled_dependencies:
            print(f"\n{CYAN}Bundled Dependencies:{RESET}")
            for dep_name, dep_info in sorted(bundled_dependencies.items()):
                ver = dep_info.get('version', '?')
                dep_github = dep_info.get('github', '')
                print(f"  {dep_name} v{ver} (bundled)")
                if dep_github:
                    print(f"    {DIM}{dep_github}{RESET}")

        # Show message if nothing meaningful found
        has_content = requires or contributes or depends or dependencies or bundled_dependencies
        if not has_content:
            print(f"\n{DIM}No Talon contributions or dependencies detected.{RESET}")

        print()
        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False
    finally:
        # Clean up temp manifest file
        if temp_manifest_path and os.path.exists(temp_manifest_path):
            os.unlink(temp_manifest_path)


def find_talon_user_dir() -> str:
    """Find the Talon user directory by walking up from the package directory."""
    search_path = str(SCRIPT_DIR)
    while search_path:
        user_path = os.path.join(search_path, 'user')
        dir_name = os.path.basename(search_path)
        if dir_name in ('talon', '.talon') and os.path.isdir(user_path):
            has_talon_log = any(
                os.path.exists(os.path.join(search_path, f'talon.log{suffix}'))
                for suffix in ['', '.1', '.2', '.3', '.4', '.5']
            )
            if has_talon_log:
                return user_path
        parent = os.path.dirname(search_path)
        if parent == search_path:
            break
        search_path = parent
    return None


def scan_installed_versions(talon_user_dir: str) -> dict:
    """Scan all manifest.json files and return {package_name: {"version": version, "path": path}}."""
    from generate_manifest import is_community_repo, COMMUNITY_REPO_PACKAGE
    SKIP_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        '.pytest_cache', '.mypy_cache', 'dist', 'build', '.vscode',
        '.idea', 'recordings', 'backup', '.subtrees'
    }
    versions = {}
    for root, dirs, files in os.walk(talon_user_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if is_community_repo(root):
            versions[COMMUNITY_REPO_PACKAGE] = {"version": "", "path": root}
            dirs.clear()
            continue
        if 'manifest.json' in files:
            try:
                with open(os.path.join(root, 'manifest.json'), 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                if manifest.get('_generator') not in ('talon-pack', 'talon-manifest-generator'):
                    continue
                name = manifest.get('name')
                version = manifest.get('version')
                if name and version:
                    versions[name] = {"version": version, "path": root}
            except Exception:
                pass
    return versions


def outdated_command(directory: Path, search_dir: str = None, search_dir_display: str = None) -> bool:
    """Show packages with newer versions available (local vs remote)."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        if directory != Path(".").resolve():
            print(f"{YELLOW}Did you mean: tpack outdated --search {directory.name}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        local_version = manifest.get('version', '0.0.0')
        github_url = manifest.get('github', '')
        dependencies = manifest.get('dependencies', {})

        pkg_name = manifest.get('name', directory.name)

        # Scan installed versions for dependencies
        installed = {}
        if dependencies:
            talon_user_dir = search_dir or find_talon_user_dir()
            if not talon_user_dir:
                print(f"{RED}Error: Could not find Talon user directory{RESET}")
                return False
            installed = scan_installed_versions(talon_user_dir)

        # Build dependency list
        deps_to_check = {}
        for dep_name, dep_info in dependencies.items():
            installed_info = installed.get(dep_name)
            deps_to_check[dep_name] = {
                "manifest_version": dep_info.get('min_version'),
                "installed_version": installed_info["version"] if installed_info else None,
                "github": dep_info.get('github', ''),
            }

        # Fetch remote versions (self + deps)
        print(f"\n{CYAN}{directory.name}/{RESET}")
        print(f"{DIM}  Checking remote versions...{RESET}")

        remote_versions = {}
        if github_url:
            remote_manifest = fetch_remote_manifest(github_url)
            if remote_manifest:
                remote_versions[pkg_name] = remote_manifest.get('version')
        for name, info in deps_to_check.items():
            pkg_github = info["github"]
            if pkg_github:
                remote_manifest = fetch_remote_manifest(pkg_github)
                if remote_manifest:
                    remote_versions[name] = remote_manifest.get('version')

        # Show self package status
        self_remote = remote_versions.get(pkg_name)
        if self_remote and self_remote != local_version:
            remote_parts = [int(x) for x in self_remote.split('.')]
            local_parts = [int(x) for x in local_version.split('.')]
            if remote_parts > local_parts:
                self_status = f"{YELLOW}update available{RESET}"
            else:
                self_status = f"{CYAN}unpublished{RESET}"
        else:
            self_status = f"{GREEN}up to date{RESET}"
        print(f"  {pkg_name}  {local_version} (local)  {self_remote or '-'} (remote)  {self_status}")

        has_updates = self_remote and self_remote != local_version and [int(x) for x in self_remote.split('.')] > [int(x) for x in local_version.split('.')]

        # Show dependencies table
        if deps_to_check:
            name_width = max(len(name) for name in deps_to_check)
            name_width = max(name_width, len("Dependency"))

            print(f"\n  {'Dependency':<{name_width}}   {'Manifest':<12} {'Local':<12} {'Remote':<12} {'Status'}")
            print(f"  {'-' * name_width}   {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 16}")

            has_sync_needed = False
            for name, info in sorted(deps_to_check.items()):
                manifest_ver = info["manifest_version"]
                installed_ver = info.get("installed_version")
                remote_ver = remote_versions.get(name)

                if installed_ver is None:
                    status = f"{RED}not installed{RESET}"
                    has_updates = True
                elif not installed_ver or not manifest_ver:
                    status = f"{GREEN}installed{RESET}" if installed_ver is not None else f"{RED}not installed{RESET}"
                else:
                    installed_parts = [int(x) for x in installed_ver.split('.')]
                    needs_update = remote_ver and [int(x) for x in remote_ver.split('.')] > installed_parts
                    needs_sync = manifest_ver and installed_parts > [int(x) for x in manifest_ver.split('.')]

                    if needs_update and needs_sync:
                        status = f"{YELLOW}update available, sync available{RESET}"
                        has_updates = True
                        has_sync_needed = True
                    elif needs_update:
                        status = f"{YELLOW}update available{RESET}"
                        has_updates = True
                    elif needs_sync:
                        status = f"{YELLOW}sync available{RESET}"
                        has_sync_needed = True
                        has_updates = True
                    else:
                        status = f"{GREEN}up to date{RESET}"

                manifest_display = manifest_ver or "-"
                installed_display = installed_ver or "-"
                remote_display = remote_ver or "-"
                print(f"  {name:<{name_width}}   {manifest_display:<12} {installed_display:<12} {remote_display:<12} {status}")

        if has_updates:
            dir_hint = f" --search {search_dir_display or search_dir}" if search_dir else ""
            if any(
                info.get("installed_version") and remote_versions.get(name) and
                [int(x) for x in remote_versions[name].split('.')] > [int(x) for x in info["installed_version"].split('.')]
                for name, info in deps_to_check.items()
                if info.get("installed_version")
            ):
                print(f"\n  Run {GREEN}tpack update{dir_hint}{RESET} to pull latest versions.")
            if has_sync_needed:
                print(f"  Run {GREEN}tpack sync{dir_hint}{RESET} to update min_version in manifest.")
        else:
            print(f"\n{DIM}All packages are up to date.{RESET}")

        # Check for local changes that may need a version bump
        # Skip if: no remote (not published yet), or version already bumped past remote
        version_already_bumped = self_remote and [int(x) for x in local_version.split('.')] > [int(x) for x in self_remote.split('.')]
        if self_remote and not version_already_bumped:
            local_changes = check_local_changes(directory, include_commits_ahead=True)
            if local_changes:
                print(f"  {YELLOW}Local changes detected: {local_changes}.{RESET}")
                print(f"  {YELLOW}Consider running {GREEN}tpack patch{YELLOW}, {GREEN}tpack minor{YELLOW}, or {GREEN}tpack major{YELLOW} before releasing.{RESET}")

        print()
        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def deps_command(directory: Path, search_dir: str = None) -> bool:
    """Show all dependencies with local install status (no network calls)."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        dependencies = manifest.get('dependencies', {})
        bundled_deps = manifest.get('bundledDependencies', {})
        pip_deps = manifest.get('pipDependencies', {})

        has_any = dependencies or bundled_deps or pip_deps

        if not has_any:
            pkg_name = manifest.get('name', directory.name)
            print(f"\n{CYAN}{pkg_name}/{RESET}")
            print(f"{DIM}No dependencies.{RESET}\n")
            return True

        # Split dependencies by properties
        required_deps = {k: v for k, v in dependencies.items() if not v.get('optional') and not v.get('dev_only')}
        optional_deps = {k: v for k, v in dependencies.items() if v.get('optional')}
        dev_deps = {k: v for k, v in dependencies.items() if v.get('dev_only')}

        # Scan installed versions
        talon_user_dir = search_dir or find_talon_user_dir()
        installed = scan_installed_versions(talon_user_dir) if talon_user_dir else {}

        # Scan installed pip packages
        installed_pip = set()
        if pip_deps:
            pip_path = find_talon_pip()
            if pip_path:
                installed_pip = get_installed_pip_packages(pip_path)

        pkg_name = manifest.get('name', directory.name)
        print(f"\n{CYAN}{pkg_name}/{RESET}")

        def print_dep_section(title, deps, is_bundled=False):
            if not deps:
                return
            print(f"\n  {CYAN}{title}:{RESET}")
            for dep_name, dep_info in sorted(deps.items()):
                version = dep_info.get('min_version') or dep_info.get('version', '')
                required_by = dep_info.get('required_by', [])
                platforms = dep_info.get('platforms', [])
                description = dep_info.get('description', '')

                if is_bundled:
                    status = f"{DIM}bundled{RESET}"
                elif dep_name in installed:
                    inst_ver = installed[dep_name]["version"]
                    if version and inst_ver:
                        inst_parts = [int(x) for x in inst_ver.split('.')]
                        min_parts = [int(x) for x in version.split('.')]
                        if inst_parts >= min_parts:
                            status = f"{GREEN}{inst_ver} installed{RESET}"
                        else:
                            status = f"{YELLOW}{inst_ver} installed (needs >={version}){RESET}"
                    elif inst_ver:
                        status = f"{GREEN}{inst_ver} installed{RESET}"
                    else:
                        status = f"{GREEN}installed{RESET}"
                else:
                    status = f"{RED}not installed{RESET}"

                suffix_parts = []
                if description:
                    suffix_parts.append(description)
                if platforms and set(platforms) < {"windows", "mac", "linux"}:
                    names = [p.capitalize() if p != "mac" else "Mac" for p in sorted(platforms)]
                    suffix_parts.append(f"{'/'.join(names)} only")
                if required_by:
                    suffix_parts.append(f"required by {', '.join(required_by)}")
                suffix = f"  {DIM}({', '.join(suffix_parts)}){RESET}" if suffix_parts else ""

                ver_display = f">={version}" if version else ""
                print(f"    {dep_name}  {ver_display}  {status}{suffix}")

        def print_pip_section(pip_deps):
            if not pip_deps:
                return
            print(f"\n  {CYAN}Pip Dependencies:{RESET}")
            for pip_name, pip_info in sorted(pip_deps.items()):
                version = pip_info.get('version', '')
                optional = pip_info.get('optional', False)
                description = pip_info.get('description', '')
                required_by = pip_info.get('required_by', [])

                if pip_name.lower() in installed_pip:
                    status = f"{GREEN}installed{RESET}"
                else:
                    status = f"{RED}not installed{RESET}"

                suffix_parts = []
                if optional:
                    suffix_parts.append("optional")
                if description:
                    suffix_parts.append(description)
                if required_by:
                    suffix_parts.append(f"required by {', '.join(required_by)}")
                suffix = f"  {DIM}({', '.join(suffix_parts)}){RESET}" if suffix_parts else ""

                ver_display = f"  {version}" if version and version != '*' else ""
                print(f"    {pip_name}{ver_display}  {status}{suffix}")

        print_dep_section("Dependencies", required_deps)
        print_dep_section("Optional Dependencies", optional_deps)
        print_dep_section("Bundled Dependencies", bundled_deps, is_bundled=True)
        print_pip_section(pip_deps)
        print_dep_section("Dev Dependencies", dev_deps)

        print()
        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def find_talon_pip() -> str | None:
    """Find Talon's bundled pip executable (highest version on Windows)."""
    import platform
    system = platform.system()
    if system == "Windows":
        talon_dir = Path(os.environ.get("APPDATA", "")) / "talon"
        venv_dir = talon_dir / "venv"
        if venv_dir.exists():
            candidates = []
            for version_dir in venv_dir.iterdir():
                pip_path = version_dir / "Scripts" / "pip.bat"
                if pip_path.exists():
                    try:
                        ver = tuple(int(x) for x in version_dir.name.split('.'))
                        candidates.append((ver, pip_path))
                    except ValueError:
                        candidates.append(((0,), pip_path))
            if candidates:
                candidates.sort(reverse=True)
                return str(candidates[0][1])
    else:
        pip_path = Path.home() / ".talon" / "bin" / "pip"
        if pip_path.exists():
            return str(pip_path)
    return None


def get_installed_pip_packages(pip_path: str) -> set[str]:
    """Get set of installed pip package names (lowercased)."""
    try:
        result = subprocess.run(
            [pip_path, "list", "--format=json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {pkg["name"].lower() for pkg in packages}
    except Exception:
        pass
    return set()


def confirm_action(message: str, auto_yes: bool = False) -> bool:
    """Prompt user for y/N confirmation. Returns True if confirmed."""
    if auto_yes:
        print(f"{message} (auto-confirmed)")
        return True
    try:
        response = input(f"{message} [y/N] ").strip().lower()
        return response in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def repo_name_from_url(url: str) -> str:
    """Extract repo name from a GitHub URL."""
    name = url.rstrip('/').split('/')[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name


def parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL. Returns None if not a valid GitHub URL."""
    import re
    match = re.match(r'https://github\.com/([^/]+)/([^/.]+)', url.rstrip('/'))
    if match:
        return match.group(1), match.group(2)
    return None


def fetch_remote_manifest(url: str) -> dict | None:
    """Fetch manifest.json from a GitHub repo without cloning. Tries main then master branch."""
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError

    parsed = parse_github_url(url)
    if not parsed:
        return None
    owner, repo = parsed

    last_error = None
    for branch in ("main", "master"):
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/manifest.json"
        try:
            req = Request(raw_url, headers={"User-Agent": "talon-pack"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('_generator') in ('talon-pack', 'talon-manifest-generator'):
                    return data
        except (HTTPError, URLError, json.JSONDecodeError, Exception) as e:
            last_error = e
            continue
    if last_error:
        print(f"  Warning: Could not fetch remote manifest for {owner}/{repo}: {last_error}", file=sys.stderr)
    return None


def install_command(target: str | None, directory: Path, dry_run: bool = False, auto_yes: bool = False, search_dir: str = None) -> bool:
    """Install dependencies from manifest or install a package from a GitHub URL."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    # If target looks like a GitHub URL, install that single package
    if target and target.startswith("https://github.com/"):
        return install_from_url(target, dry_run, auto_yes)

    if target:
        # target might be a directory
        candidate = Path(target)
        if candidate.is_dir():
            directory = candidate.resolve()
        else:
            print(f"{RED}Error: '{target}' is not a valid directory or GitHub URL{RESET}")
            print(f"Usage: tpack install [dir]            Install dependencies from manifest")
            print(f"       tpack install <github_url>     Install a package")
            return False

    return install_from_manifest(directory, dry_run, auto_yes)


def install_from_manifest(directory: Path, dry_run: bool = False, auto_yes: bool = False) -> bool:
    """Install dependencies listed in a manifest.json."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        all_dependencies = manifest.get('dependencies', {})
        pip_deps = manifest.get('pipDependencies', {})

        # Split by properties
        required_deps = {k: v for k, v in all_dependencies.items() if not v.get('optional') and not v.get('dev_only')}
        optional_deps = {k: v for k, v in all_dependencies.items() if v.get('optional')}

        if not all_dependencies and not pip_deps:
            print(f"\n{DIM}No dependencies found in {directory.name}/manifest.json{RESET}")
            return True

        talon_user_dir = search_dir or find_talon_user_dir()
        if not talon_user_dir:
            print(f"{RED}Error: Could not find Talon user directory{RESET}")
            return False

        installed = scan_installed_versions(talon_user_dir)

        # Determine what needs to be installed (required deps only)
        to_clone = []
        already_installed = []
        for dep_name, dep_info in sorted(required_deps.items()):
            github_url = dep_info.get('github', '')
            if dep_name in installed:
                already_installed.append(dep_name)
            elif github_url:
                to_clone.append((dep_name, github_url))
            else:
                print(f"{YELLOW}Warning: {dep_name} has no github URL, cannot install{RESET}")

        pip_to_install = []
        pip_already_installed = []
        if pip_deps:
            pip_path = find_talon_pip()
            installed_pip = get_installed_pip_packages(pip_path) if pip_path else set()
            for pip_name, pip_info in sorted(pip_deps.items()):
                if pip_name.lower() in installed_pip:
                    pip_already_installed.append(pip_name)
                    continue
                version = pip_info.get('version', '')
                if version and version != '*':
                    pip_to_install.append(f"{pip_name}{version}")
                else:
                    pip_to_install.append(pip_name)

        # Show plan
        print(f"\n{CYAN}{directory.name}/{RESET}")

        if already_installed:
            for name in already_installed:
                print(f"  {DIM}{name} - already installed{RESET}")
        if pip_already_installed:
            for name in pip_already_installed:
                print(f"  {DIM}{name} (pip) - already installed{RESET}")

        if not to_clone and not pip_to_install:
            print(f"\n{DIM}All dependencies are already installed.{RESET}")
            return True

        if to_clone:
            print(f"\n  {CYAN}Commands:{RESET}")
            for dep_name, url in to_clone:
                clone_target = os.path.join(talon_user_dir, repo_name_from_url(url))
                print(f"    git clone {url} \"{clone_target}\"")

        if pip_to_install:
            pip_path = find_talon_pip()
            pip_display = pip_path or "pip"
            print(f"    {pip_display} install {' '.join(pip_to_install)}")

        if dry_run:
            print(f"\n{DIM}(dry run - no actions taken){RESET}")
            return True

        if not confirm_action("\nProceed with installation?", auto_yes):
            print(f"{DIM}Cancelled.{RESET}")
            return True

        # Clone repos
        success = True
        for dep_name, url in to_clone:
            clone_target = os.path.join(talon_user_dir, repo_name_from_url(url))
            print(f"\n  Cloning {dep_name}...")
            try:
                result = subprocess.run(
                    ["git", "clone", url, clone_target],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"  {GREEN}Cloned {dep_name}{RESET}")
                else:
                    print(f"  {RED}Failed to clone {dep_name}: {result.stderr.strip()}{RESET}")
                    success = False
            except Exception as e:
                print(f"  {RED}Error cloning {dep_name}: {e}{RESET}")
                success = False

        # Pip install
        if pip_to_install:
            pip_path = find_talon_pip()
            if not pip_path:
                print(f"\n{YELLOW}Warning: Could not find Talon's bundled pip.{RESET}")
                print(f"{DIM}Install manually with Talon's pip: pip install {' '.join(pip_to_install)}{RESET}")
            else:
                print(f"\n  Installing pip packages...")
                try:
                    result = subprocess.run(
                        [pip_path, "install"] + pip_to_install,
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        print(f"  {GREEN}Installed pip packages{RESET}")
                    else:
                        print(f"  {RED}pip install failed: {result.stderr.strip()}{RESET}")
                        success = False
                except Exception as e:
                    print(f"  {RED}Error running pip: {e}{RESET}")
                    success = False

        # Prompt for optional dependencies
        if optional_deps and not dry_run:
            optional_candidates = []
            for dep_name, dep_info in sorted(optional_deps.items()):
                if dep_name in installed:
                    continue
                github_url = dep_info.get('github', '')
                if github_url:
                    clone_target_opt = os.path.join(talon_user_dir, repo_name_from_url(github_url))
                    if not os.path.exists(clone_target_opt):
                        optional_candidates.append((dep_name, dep_info))

            if optional_candidates:
                print(f"\n  {CYAN}Optional dependencies:{RESET}")
                for dep_name, dep_info in optional_candidates:
                    github_url = dep_info.get('github', '')
                    description = dep_info.get('description', '')
                    desc_display = f" ({description})" if description else ""
                    if confirm_action(f"  Install {dep_name}?{desc_display}", auto_yes=False):
                        clone_target_opt = os.path.join(talon_user_dir, repo_name_from_url(github_url))
                        print(f"\n  Cloning {dep_name}...")
                        try:
                            result = subprocess.run(
                                ["git", "clone", github_url, clone_target_opt],
                                capture_output=True, text=True
                            )
                            if result.returncode == 0:
                                print(f"  {GREEN}Cloned {dep_name}{RESET}")
                            else:
                                print(f"  {RED}Failed to clone {dep_name}: {result.stderr.strip()}{RESET}")
                                success = False
                        except Exception as e:
                            print(f"  {RED}Error cloning {dep_name}: {e}{RESET}")
                            success = False

        print()
        return success
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def install_from_url(url: str, dry_run: bool = False, auto_yes: bool = False) -> bool:
    """Clone a package from a GitHub URL and install its dependencies."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    talon_user_dir = find_talon_user_dir()
    if not talon_user_dir:
        print(f"{RED}Error: Could not find Talon user directory{RESET}")
        return False

    repo_name = repo_name_from_url(url)
    clone_target = os.path.join(talon_user_dir, repo_name)

    if os.path.exists(clone_target):
        print(f"{DIM}{repo_name} already exists at {clone_target}{RESET}")
        manifest_path = Path(clone_target) / "manifest.json"
        if manifest_path.exists():
            return install_from_manifest(Path(clone_target), dry_run, auto_yes)
        return True

    installed = scan_installed_versions(talon_user_dir)

    # Fetch manifest from GitHub to show full plan before cloning
    remote_manifest = fetch_remote_manifest(url)

    to_clone = [(repo_name, url)]
    pip_to_install = []

    if remote_manifest:
        deps = remote_manifest.get('dependencies', {})
        # Only auto-install required deps (not optional or dev_only)
        for dep_name, dep_info in sorted(deps.items()):
            if dep_info.get('optional') or dep_info.get('dev_only'):
                continue
            if dep_name in installed:
                continue
            github_url = dep_info.get('github', '')
            if github_url:
                dep_repo = repo_name_from_url(github_url)
                dep_target = os.path.join(talon_user_dir, dep_repo)
                if not os.path.exists(dep_target):
                    to_clone.append((dep_name, github_url))

        pip_deps = remote_manifest.get('pipDependencies', {})
        if pip_deps:
            pip_path = find_talon_pip()
            installed_pip = get_installed_pip_packages(pip_path) if pip_path else set()
            for pip_name, pip_info in sorted(pip_deps.items()):
                if pip_name.lower() in installed_pip:
                    continue
                version = pip_info.get('version', '')
                if version and version != '*':
                    pip_to_install.append(f"{pip_name}{version}")
                else:
                    pip_to_install.append(pip_name)

    # Show plan
    print(f"\n{CYAN}Commands:{RESET}")
    for dep_name, dep_url in to_clone:
        target = os.path.join(talon_user_dir, repo_name_from_url(dep_url))
        print(f"  git clone {dep_url} \"{target}\"")

    if pip_to_install:
        pip_path = find_talon_pip()
        pip_display = pip_path or "pip"
        print(f"  {pip_display} install {' '.join(pip_to_install)}")

    if dry_run:
        print(f"\n{DIM}(dry run - no actions taken){RESET}")
        return True

    if not confirm_action("\nProceed with installation?", auto_yes):
        print(f"{DIM}Cancelled.{RESET}")
        return True

    # Clone all repos
    success = True
    for dep_name, dep_url in to_clone:
        target = os.path.join(talon_user_dir, repo_name_from_url(dep_url))
        print(f"\n  Cloning {dep_name}...")
        try:
            result = subprocess.run(
                ["git", "clone", dep_url, target],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  {GREEN}Cloned {dep_name}{RESET}")
            else:
                print(f"  {RED}Failed to clone {dep_name}: {result.stderr.strip()}{RESET}")
                success = False
        except Exception as e:
            print(f"  {RED}Error cloning {dep_name}: {e}{RESET}")
            success = False

    # Pip install
    if pip_to_install:
        pip_path = find_talon_pip()
        if not pip_path:
            print(f"\n{YELLOW}Warning: Could not find Talon's bundled pip.{RESET}")
            print(f"{DIM}Install manually with Talon's pip: pip install {' '.join(pip_to_install)}{RESET}")
        else:
            print(f"\n  Installing pip packages...")
            try:
                result = subprocess.run(
                    [pip_path, "install"] + pip_to_install,
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"  {GREEN}Installed pip packages{RESET}")
                else:
                    print(f"  {RED}pip install failed: {result.stderr.strip()}{RESET}")
                    success = False
            except Exception as e:
                print(f"  {RED}Error running pip: {e}{RESET}")
                success = False

    # Prompt for optional dependencies
    if remote_manifest and not dry_run:
        optional_deps = {k: v for k, v in deps.items() if v.get('optional')}
        optional_candidates = []
        for dep_name, dep_info in sorted(optional_deps.items()):
            if dep_name in installed:
                continue
            github_url = dep_info.get('github', '')
            if github_url:
                dep_repo = repo_name_from_url(github_url)
                dep_target = os.path.join(talon_user_dir, dep_repo)
                if not os.path.exists(dep_target):
                    optional_candidates.append((dep_name, dep_info))

        if optional_candidates:
            print(f"\n  {CYAN}Optional dependencies:{RESET}")
            for dep_name, dep_info in optional_candidates:
                github_url = dep_info.get('github', '')
                description = dep_info.get('description', '')
                desc_display = f" ({description})" if description else ""
                if confirm_action(f"  Install {dep_name}?{desc_display}", auto_yes=False):
                    dep_target = os.path.join(talon_user_dir, repo_name_from_url(github_url))
                    print(f"\n  Cloning {dep_name}...")
                    try:
                        result = subprocess.run(
                            ["git", "clone", github_url, dep_target],
                            capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            print(f"  {GREEN}Cloned {dep_name}{RESET}")
                        else:
                            print(f"  {RED}Failed to clone {dep_name}: {result.stderr.strip()}{RESET}")
                            success = False
                    except Exception as e:
                        print(f"  {RED}Error cloning {dep_name}: {e}{RESET}")
                        success = False

    print()
    return success


def consumer_update_command(directory: Path, dry_run: bool = False, auto_yes: bool = False, search_dir: str = None) -> bool:
    """Pull latest for the current package and its installed dependencies."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        pkg_name = manifest.get('name', directory.name)
        dependencies = manifest.get('dependencies', {})

        # Build list of repos to pull: self + dependencies
        to_update = []
        not_found = []

        # Include self if it's a git repo
        git_dir = directory / ".git"
        if git_dir.exists():
            to_update.append((pkg_name, str(directory)))

        if dependencies:
            talon_user_dir = search_dir or find_talon_user_dir()
            if not talon_user_dir:
                print(f"{RED}Error: Could not find Talon user directory{RESET}")
                return False

            installed = scan_installed_versions(talon_user_dir)

            for dep_name in sorted(dependencies.keys()):
                installed_info = installed.get(dep_name)
                if installed_info:
                    to_update.append((dep_name, installed_info["path"]))
                else:
                    not_found.append(dep_name)

        print(f"\n{CYAN}{directory.name}/{RESET}")

        if not_found:
            for name in not_found:
                print(f"  {YELLOW}{name} - not installed, skipping{RESET}")

        if not to_update:
            print(f"\n{DIM}Nothing to update.{RESET}")
            return True

        print(f"\n  {CYAN}Commands:{RESET}")
        for dep_name, path in to_update:
            print(f"    git -C \"{path}\" pull")

        if dry_run:
            print(f"\n{DIM}(dry run - no actions taken){RESET}")
            return True

        if not confirm_action("\nProceed with update?", auto_yes):
            print(f"{DIM}Cancelled.{RESET}")
            return True

        # Git pull each
        for dep_name, path in to_update:
            print(f"\n  Updating {dep_name}...")
            try:
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=path,
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if "Already up to date" in output or "Already up-to-date" in output:
                        print(f"  {DIM}{dep_name} - already up to date{RESET}")
                    else:
                        print(f"  {GREEN}{dep_name} - updated{RESET}")
                else:
                    print(f"  {RED}{dep_name} - failed: {result.stderr.strip()}{RESET}")
            except Exception as e:
                print(f"  {RED}{dep_name} - error: {e}{RESET}")

        print()
        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def sync_command(dep_name: str | None, directory: Path, dry_run: bool = False, search_dir: str = None) -> bool:
    """Update dependency min_version(s) to match installed versions."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
            manifest = json.loads(old_content)

        dependencies = manifest.get('dependencies', {})
        if not dependencies:
            print(f"\n{DIM}No dependencies found in {directory.name}/manifest.json{RESET}")
            return True

        if dep_name and dep_name not in dependencies:
            print(f"{RED}Error: '{dep_name}' is not a dependency of {directory.name}{RESET}")
            print(f"{DIM}Dependencies: {', '.join(sorted(dependencies.keys()))}{RESET}")
            return False

        talon_user_dir = search_dir or find_talon_user_dir()
        if not talon_user_dir:
            print(f"{RED}Error: Could not find Talon user directory{RESET}")
            return False

        installed = scan_installed_versions(talon_user_dir)

        deps_to_update = [dep_name] if dep_name else sorted(dependencies.keys())
        updated = []

        for name in deps_to_update:
            dep_info = dependencies[name]
            min_ver = dep_info.get('min_version') or dep_info.get('version', '')
            installed_info = installed.get(name)
            installed_ver = installed_info["version"] if installed_info else None

            if installed_ver is None:
                print(f"{YELLOW}{name}: not found locally, skipping{RESET}")
                continue

            if not installed_ver or not min_ver:
                continue

            if min_ver == installed_ver:
                continue

            installed_parts = [int(x) for x in installed_ver.split('.')]
            required_parts = [int(x) for x in min_ver.split('.')]
            if installed_parts > required_parts:
                dep_info['min_version'] = installed_ver
                updated.append((name, min_ver, installed_ver))

        if not updated:
            print(f"\n{DIM}All dependencies are already up to date.{RESET}")
            return True

        new_content = json.dumps(manifest, indent=2)

        print(f"\n{CYAN}{directory.name}/{RESET}")
        has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
        if has_changes:
            print(format_diff_output(diff_output))

        if not dry_run:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Regenerate readme and shields if needed
            readme_path = directory / "README.md"
            if readme_path.exists():
                run_generator("generate_readme.py", str(directory))
                if manifest.get('_generatorShields', True):
                    run_generator("generate_shields.py", str(directory), ["--quiet"])

        return True
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False


def parse_pip_spec(spec: str) -> tuple[str, dict, str | None]:
    """Parse a pip-style package spec into (name, info_dict, error).
    Examples:
        'vgamepad'         -> ('vgamepad', {'version': '*'}, None)
        'vgamepad>=1.0.0'  -> ('vgamepad', {'version': '>=1.0.0'}, None)
        'vgamepad==1.0.2'  -> ('vgamepad', {'version': '==1.0.2'}, None)
        'vgamepad>bad'     -> ('vgamepad', {}, 'invalid version ...')
    """
    import re
    match = re.match(r'^([A-Za-z0-9_.-]+)(.*)', spec)
    if not match:
        return spec, {}, f"invalid package name: {spec}"
    name = match.group(1)
    version_part = match.group(2).strip()
    if version_part:
        # Validate version specifier format
        version_pattern = re.compile(r'^(==|>=|<=|!=|~=|>|<)\d+(\.\d+)*$')
        if not version_pattern.match(version_part):
            return name, {}, (
                f"invalid version specifier: {version_part}\n"
                f"  Expected formats: ==1.0.0, >=1.0.0, <=1.0.0, !=1.0.0, ~=1.0.0"
            )
        return name, {'version': version_part}, None
    return name, {'version': '*'}, None


def reorder_manifest_key(manifest: dict, key: str, after: str) -> dict:
    """Reorder manifest so `key` appears right after `after`."""
    if key not in manifest or after not in manifest:
        return manifest
    value = manifest.pop(key)
    result = {}
    for k, v in manifest.items():
        result[k] = v
        if k == after:
            result[key] = value
    if key not in result:
        result[key] = value
    return result


def release_command(directory: Path, dry_run: bool = False, auto_yes: bool = False) -> bool:
    """Create a GitHub release for the current version."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    version = manifest.get("version")
    if not version:
        print(f"{RED}Error: No version found in manifest.json{RESET}")
        return False

    github_url = manifest.get("github", "")
    tag = f"v{version}"

    # Check gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print(f"{RED}Error: 'gh' CLI not found. Install from https://cli.github.com{RESET}")
        return False
    except subprocess.CalledProcessError:
        print(f"{RED}Error: 'gh' CLI failed{RESET}")
        return False

    # Check we're in a git repo
    git_check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, cwd=str(directory)
    )
    if git_check.returncode != 0:
        print(f"{RED}Error: Not a git repository: {directory}{RESET}")
        return False

    # Check for uncommitted changes
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=str(directory)
    )
    if status_result.stdout.strip():
        print(f"{YELLOW}Warning: You have uncommitted changes.{RESET}")
        print(f"{DIM}Commit and push before releasing.{RESET}")
        return False

    # Check if tag already exists
    tag_check = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True, text=True, cwd=str(directory)
    )
    if tag_check.stdout.strip():
        print(f"{DIM}{tag} already released.{RESET}")
        return True

    # Check if local is ahead of remote
    subprocess.run(
        ["git", "fetch", "--quiet"],
        capture_output=True, cwd=str(directory)
    )
    ahead_check = subprocess.run(
        ["git", "rev-list", "--count", "@{u}..HEAD"],
        capture_output=True, text=True, cwd=str(directory)
    )
    if ahead_check.returncode == 0 and ahead_check.stdout.strip() not in ("0", ""):
        ahead = ahead_check.stdout.strip()
        print(f"{YELLOW}Warning: {ahead} unpushed commit(s). Push before releasing.{RESET}")
        return False

    name = manifest.get("name", directory.name)
    print(f"\n{CYAN}{name}{RESET}")
    print(f"  Create tag {GREEN}{tag}{RESET} and GitHub release")
    if github_url:
        print(f"  {DIM}{github_url}/releases{RESET}")

    # Show commits since last tag
    last_tag = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "HEAD"],
        capture_output=True, text=True, cwd=str(directory)
    )
    if last_tag.returncode == 0 and last_tag.stdout.strip():
        prev_tag = last_tag.stdout.strip()
        log_range = f"{prev_tag}..HEAD"
    else:
        prev_tag = None
        log_range = "HEAD"

    commits = subprocess.run(
        ["git", "log", log_range, "--oneline", "--no-decorate"],
        capture_output=True, text=True, cwd=str(directory)
    )
    if commits.returncode == 0 and commits.stdout.strip():
        lines = commits.stdout.strip().split("\n")
        label = f"Commits since {prev_tag}" if prev_tag else "Commits"
        print(f"\n  {label}:")
        for line in lines[:20]:
            print(f"    {DIM}{line}{RESET}")
        if len(lines) > 20:
            print(f"    {DIM}... and {len(lines) - 20} more{RESET}")

    if dry_run:
        print(f"\n  {DIM}(dry run){RESET}")
        return True

    if not confirm_action("\nProceed?", auto_yes):
        print(f"{DIM}Release cancelled.{RESET}")
        return False

    # Create tag and release
    tag_result = subprocess.run(
        ["git", "tag", tag],
        capture_output=True, text=True, cwd=str(directory)
    )
    if tag_result.returncode != 0:
        print(f"{RED}Error creating tag: {tag_result.stderr.strip()}{RESET}")
        return False

    push_result = subprocess.run(
        ["git", "push", "origin", tag],
        capture_output=True, text=True, cwd=str(directory)
    )
    if push_result.returncode != 0:
        print(f"{RED}Error pushing tag: {push_result.stderr.strip()}{RESET}")
        return False

    release_result = subprocess.run(
        ["gh", "release", "create", tag, "--title", tag, "--generate-notes"],
        capture_output=True, text=True, cwd=str(directory)
    )
    if release_result.returncode != 0:
        print(f"{RED}Error creating release: {release_result.stderr.strip()}{RESET}")
        return False

    release_url = release_result.stdout.strip()
    print(f"  {GREEN}Released {tag}{RESET}")
    if release_url:
        print(f"  {release_url}")
    print()
    return True


def pip_command(action: str, package_spec: str | None, directory: Path, dry_run: bool = False) -> bool:
    """Add or remove a pip dependency."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    if action == "add":
        if not package_spec:
            print(f"{RED}Error: package name required{RESET}")
            print(f"Usage: tpack pip <package> [directory]")
            return False

        name, info, error = parse_pip_spec(package_spec)
        if error:
            print(f"{RED}Error: {error}{RESET}")
            return False

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                manifest = json.loads(old_content)

            pip_deps = manifest.get('pipDependencies', {})

            if name in pip_deps:
                existing = pip_deps[name]
                new_version = info.get('version')
                old_version = existing.get('version')
                if new_version == old_version or (not new_version and not old_version):
                    print(f"{DIM}{name} is already in pipDependencies{RESET}")
                    return True
                # Update version
                if new_version:
                    pip_deps[name]['version'] = new_version
                elif 'version' in pip_deps[name]:
                    del pip_deps[name]['version']
            else:
                pip_deps[name] = info

            manifest['pipDependencies'] = dict(sorted(pip_deps.items()))
            manifest = reorder_manifest_key(manifest, 'pipDependencies', 'dependencies')

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Added {name} to pipDependencies{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            return False

    elif action == "remove":
        if not package_spec:
            print(f"{RED}Error: package name required{RESET}")
            print(f"Usage: tpack pip remove <package> [directory]")
            return False

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                manifest = json.loads(old_content)

            pip_deps = manifest.get('pipDependencies', {})

            if package_spec not in pip_deps:
                print(f"{RED}Error: '{package_spec}' is not in pipDependencies{RESET}")
                if pip_deps:
                    print(f"{DIM}Current pip dependencies: {', '.join(sorted(pip_deps.keys()))}{RESET}")
                return False

            del pip_deps[package_spec]
            if pip_deps:
                manifest['pipDependencies'] = pip_deps
            elif 'pipDependencies' in manifest:
                del manifest['pipDependencies']

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Removed {package_spec} from pipDependencies{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            return False

    elif action == "list":
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            pip_deps = manifest.get('pipDependencies', {})
            if not pip_deps:
                print(f"{DIM}No pip dependencies in {directory.name}{RESET}")
                return True

            print(f"\n{CYAN}{directory.name}{RESET} pip dependencies:")
            for name, info in sorted(pip_deps.items()):
                version = info.get('version', '')
                required_by = info.get('required_by')
                parts = [f"  {name}"]
                if version and version != '*':
                    parts.append(f" ({version})")
                if required_by:
                    parts.append(f" {DIM}- required by {', '.join(required_by)}{RESET}")
                print("".join(parts))

            return True
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            return False

    else:
        print(f"{RED}Unknown pip action: {action}{RESET}")
        print(f"Usage: tpack pip add <package>       Add pip dependency")
        print(f"       tpack pip remove <package>   Remove pip dependency")
        print(f"       tpack pip list               List pip dependencies")
        return False


def deps_modify_command(action: str, package_spec: str | None, directory: Path, dry_run: bool = False,
                        optional: bool = False, dev: bool = False, description: str = "") -> bool:
    """Add or remove dependencies with optional/dev flags."""
    from diff_utils import GREEN, RED, CYAN, DIM, YELLOW, RESET, diff_json, format_diff_output

    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        print(f"{RED}Error: manifest.json not found in {directory}{RESET}")
        return False

    if action == "add":
        if not package_spec:
            print(f"{RED}Error: package name or GitHub URL required{RESET}")
            print(f"Usage: tpack deps add <package|github_url> [--optional] [--dev] [--description \"...\"]")
            return False

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                manifest = json.loads(old_content)

            deps = manifest.get('dependencies', {})

            # Resolve package info from URL or installed packages
            if package_spec.startswith('http'):
                url = package_spec.rstrip('/')
                name = repo_name_from_url(url)
                talon_user_dir = find_talon_user_dir()
                installed = scan_installed_versions(talon_user_dir) if talon_user_dir else {}
                if name in installed:
                    pkg_path = installed[name]["path"]
                    pkg_manifest_path = os.path.join(pkg_path, "manifest.json")
                    with open(pkg_manifest_path, 'r', encoding='utf-8') as f:
                        pkg_manifest = json.load(f)
                    info = {
                        "min_version": pkg_manifest.get("version", "0.0.0"),
                        "namespace": pkg_manifest.get("namespace", ""),
                        "github": url,
                    }
                    if pkg_manifest.get("platforms"):
                        info["platforms"] = pkg_manifest["platforms"]
                else:
                    remote_manifest = fetch_remote_manifest(url)
                    if remote_manifest:
                        info = {
                            "min_version": remote_manifest.get("version", "0.0.0"),
                            "namespace": remote_manifest.get("namespace", ""),
                            "github": url,
                        }
                        if remote_manifest.get("platforms"):
                            info["platforms"] = remote_manifest["platforms"]
                    else:
                        print(f"{RED}Error: Could not resolve package info for {url}{RESET}")
                        return False
            else:
                name = package_spec
                talon_user_dir = find_talon_user_dir()
                if not talon_user_dir:
                    print(f"{RED}Error: Could not find Talon user directory{RESET}")
                    return False
                installed = scan_installed_versions(talon_user_dir)
                if name not in installed:
                    print(f"{RED}Error: '{name}' is not installed. Provide a GitHub URL instead.{RESET}")
                    if installed:
                        similar = [n for n in installed if name in n or n in name]
                        if similar:
                            print(f"{DIM}Similar installed packages: {', '.join(sorted(similar))}{RESET}")
                    return False
                pkg_path = installed[name]["path"]
                pkg_manifest_path = os.path.join(pkg_path, "manifest.json")
                with open(pkg_manifest_path, 'r', encoding='utf-8') as f:
                    pkg_manifest = json.load(f)
                info = {
                    "min_version": pkg_manifest.get("version", "0.0.0"),
                    "namespace": pkg_manifest.get("namespace", ""),
                    "github": pkg_manifest.get("github", ""),
                }
                if pkg_manifest.get("platforms"):
                    info["platforms"] = pkg_manifest["platforms"]

            if name in deps:
                print(f"{DIM}{name} is already in dependencies{RESET}")
                return True

            # Set properties based on flags
            if optional:
                info["optional"] = True
            if dev:
                info["dev_only"] = True
            if description:
                info["description"] = description

            deps[name] = info
            manifest['dependencies'] = dict(sorted(deps.items()))

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            flag_label = " (optional)" if optional else " (dev)" if dev else ""
            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Added {name} to dependencies{flag_label}{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            return False

    elif action == "remove":
        if not package_spec:
            print(f"{RED}Error: package name required{RESET}")
            print(f"Usage: tpack deps remove <package>")
            return False

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                manifest = json.loads(old_content)

            deps = manifest.get('dependencies', {})

            if package_spec not in deps:
                print(f"{RED}Error: '{package_spec}' is not in dependencies{RESET}")
                if deps:
                    print(f"{DIM}Current dependencies: {', '.join(sorted(deps.keys()))}{RESET}")
                return False

            del deps[package_spec]
            manifest['dependencies'] = deps

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Removed {package_spec} from dependencies{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            return False

    elif action == "set":
        if not package_spec:
            print(f"{RED}Error: package name required{RESET}")
            print(f"Usage: tpack deps set <package> [--optional] [--dev] [--description \"...\"]")
            print(f"       Use --no-optional, --no-dev, --no-description to remove properties")
            return False

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                manifest = json.loads(old_content)

            deps = manifest.get('dependencies', {})

            if package_spec not in deps:
                print(f"{RED}Error: '{package_spec}' is not in dependencies{RESET}")
                if deps:
                    print(f"{DIM}Current dependencies: {', '.join(sorted(deps.keys()))}{RESET}")
                return False

            info = deps[package_spec]
            no_optional = "--no-optional" in sys.argv
            no_dev = "--no-dev" in sys.argv
            no_description = "--no-description" in sys.argv

            changes = []

            if optional and not info.get("optional"):
                info["optional"] = True
                changes.append("set optional")
            elif no_optional and info.get("optional"):
                del info["optional"]
                changes.append("removed optional")

            if dev and not info.get("dev_only"):
                info["dev_only"] = True
                changes.append("set dev_only")
            elif no_dev and info.get("dev_only"):
                del info["dev_only"]
                changes.append("removed dev_only")

            if description:
                info["description"] = description
                changes.append(f"set description")
            elif no_description and "description" in info:
                del info["description"]
                changes.append("removed description")

            if not changes:
                print(f"{DIM}No property changes for {package_spec}{RESET}")
                return True

            deps[package_spec] = info
            manifest['dependencies'] = deps

            new_content = json.dumps(manifest, indent=2, ensure_ascii=False)

            print(f"\n{CYAN}{directory.name}/{RESET}")
            has_changes, diff_output = diff_json(old_content, new_content, "manifest.json")
            if has_changes:
                print(format_diff_output(diff_output))

            if not dry_run:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"{GREEN}Updated {package_spec}: {', '.join(changes)}{RESET}")
            else:
                print(f"{DIM}(dry run - no files modified){RESET}")

            return True
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            return False

    else:
        print(f"{RED}Unknown deps action: {action}{RESET}")
        print(f"Usage: tpack deps add <package> [--optional] [--dev] [--description \"...\"]")
        print(f"       tpack deps remove <package>")
        print(f"       tpack deps set <package> [--optional] [--dev] [--description \"...\"]")
        return False


def load_config() -> dict:
    """Load config from tpack.config.json, returning defaults if not found."""
    defaults = {
        "defaults": {
            "manifest": True,
            "version": True,
            "readme": True,
            "shields": False
        }
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Merge with defaults
                for key in defaults["defaults"]:
                    if key not in config.get("defaults", {}):
                        config.setdefault("defaults", {})[key] = defaults["defaults"][key]
                return config
        except Exception:
            pass
    return defaults


def run_generator(script_name: str, directory: str, extra_args: list = None) -> bool:
    """Run a generator script and return success status."""
    try:
        # Build full path to the generator script
        script_path = SCRIPT_DIR / script_name
        cmd = [sys.executable, str(script_path), directory]
        if extra_args:
            cmd.extend(extra_args)
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=True,
            env=env
        )
        print(result.stdout, end='')
        return True
    except subprocess.CalledProcessError as e:
        from diff_utils import RED, RESET
        print(f"{RED}Error running {script_name}:{RESET}")
        print(e.stdout, end='')
        print(e.stderr, end='')
        return False


def process_directory(package_dir: Path, dry_run: bool = False, verbose: bool = False,
                      run_manifest: bool = True, run_version: bool = True,
                      run_readme: bool = True, run_shields: bool = False,
                      search_dir: str = None) -> bool:
    """Process a single directory with selected generators."""
    if not package_dir.exists():
        from diff_utils import RED, RESET
        print(f"{RED}Error: Directory not found: {package_dir}{RESET}")
        return False

    # Show package name header
    package_name = package_dir.name
    if verbose:
        print(f"\nGenerating files for: {package_dir}")
        print("=" * 60)
    else:
        from diff_utils import CYAN, RESET
        print(f"\n{CYAN}{package_name}/{RESET}")

    # In dry-run mode, use a temp file so other generators can read the mock manifest
    temp_manifest_path = None
    if dry_run and run_manifest:
        temp_manifest = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        temp_manifest_path = temp_manifest.name
        temp_manifest.close()

    try:
        # Run generators in sequence
        base_args = ["--skip-version-check"]
        if dry_run:
            base_args.append("--dry-run")
        if verbose:
            base_args.append("--verbose")

        # Add temp manifest output path for manifest generator in dry-run mode
        manifest_args = list(base_args)
        if temp_manifest_path:
            manifest_args.extend(["--output-manifest-path", temp_manifest_path])
        if search_dir:
            manifest_args.extend(["--search", search_dir])

        # Build args for other generators
        other_args = []
        if dry_run:
            other_args.append("--dry-run")
        if verbose:
            other_args.append("--verbose")
        # Pass temp manifest path to other generators in dry-run mode
        if temp_manifest_path:
            other_args.extend(["--manifest-path", temp_manifest_path])

        generators = []
        if run_manifest:
            generators.append(("generate_manifest.py", manifest_args))
        if run_version:
            generators.append(("generate_version.py", other_args if other_args else None))
        if run_readme:
            generators.append(("generate_readme.py", other_args if other_args else None))
        if run_shields:
            shields_args = []
            if dry_run:
                shields_args.append("--dry-run")
            shields_args.append("--quiet")  # quiet when running as part of normal flow
            generators.append(("generate_shields.py", shields_args if shields_args else None))
        if not generators:
            print("No generators selected to run.")
            return False

        for generator, extra_args in generators:
            if verbose:
                print(f"\nRunning {generator}...")
                print("-" * 60)
            if not run_generator(generator, str(package_dir), extra_args):
                from diff_utils import RED, RESET
                print(f"{RED}Failed at {generator}{RESET}")
                return False

        if verbose:
            print(f"\nAll generators completed for {package_dir}")

        return True
    finally:
        # Clean up temp manifest file
        if temp_manifest_path and os.path.exists(temp_manifest_path):
            os.unlink(temp_manifest_path)


def main():
    if ("--help" in sys.argv or "-h" in sys.argv) and "deps" not in sys.argv:
        print(__doc__)
        sys.exit(0)

    if "--version" in sys.argv or "-V" in sys.argv:
        tpack_dir = Path(__file__).resolve().parent
        manifest_path = tpack_dir / "manifest.json"
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            print(f"talon-pack v{manifest.get('version', 'unknown')}")
        except Exception:
            print("talon-pack (unknown version)")
        sys.exit(0)

    # Handle subcommands
    # Parse --search flag for dependency search path override
    search_dir = None
    search_dir_raw = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--search" and i + 1 < len(sys.argv):
            search_dir_raw = sys.argv[i + 1]
            search_dir = str(Path(search_dir_raw).resolve())
            break

    # Validate flags
    known_flags = {
        '--dry-run', '--yes', '-y', '-v', '--verbose', '--search',
        '--help', '-h', '--version', '-V', '--force',
        '--skip-version-check', '--optional', '--dev', '--description',
        '--no-optional', '--no-dev', '--no-description',
    }
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg.startswith('-') and arg not in known_flags:
            from diff_utils import RED, YELLOW, RESET
            print(f"{RED}Unknown flag: {arg}{RESET}")
            # Suggest if it looks like a subcommand
            subcommands = [
                'info', 'deps', 'patch', 'minor', 'major', 'version',
                'install', 'update', 'outdated', 'sync', 'release',
                'status', 'duplicate-check', 'platform', 'pip', 'generate', 'help',
            ]
            bare = arg.lstrip('-')
            if bare in subcommands:
                print(f"{YELLOW}Did you mean: tpack {bare}{RESET}")
            sys.exit(1)

    # Build positional args, skipping values that follow flags like --search and --description
    flags_with_values = {'--search', '--description'}
    args = []
    skip_next = False
    for a in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in flags_with_values:
            skip_next = True
            continue
        if not a.startswith('-'):
            args.append(a)

    # tpack info [directory]
    if len(args) >= 1 and args[0] == 'info':
        directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
        success = info_command(directory)
        sys.exit(0 if success else 1)

    # tpack deps [directory]
    # tpack deps add <package|url> [directory] [--optional] [--dev] [--description "..."]
    # tpack deps remove <package> [directory]
    if len(args) >= 1 and args[0] == 'deps':
        dry_run = "--dry-run" in sys.argv
        is_optional = "--optional" in sys.argv
        is_dev = "--dev" in sys.argv
        is_help = "--help" in sys.argv or "-h" in sys.argv
        description = ""
        for i, arg in enumerate(sys.argv):
            if arg == '--description' and i + 1 < len(sys.argv):
                description = sys.argv[i + 1]
                break
        if is_help or (len(args) == 1 and not Path(".").resolve().joinpath("manifest.json").exists()):
            from diff_utils import CYAN, DIM, RESET
            print(f"\n{CYAN}tpack deps{RESET} - Manage dependencies\n")
            print(f"  tpack deps                  List dependencies and install status")
            print(f"  tpack deps add <pkg|url>    Add dependency")
            print(f"  tpack deps remove <pkg>     Remove dependency")
            print(f"  tpack deps set <pkg>        Modify dependency properties\n")
            print(f"{DIM}Flags for add/set:{RESET}")
            print(f"  --optional                  Mark as optional (prompted Y/N during install)")
            print(f"  --dev                       Mark as dev-only (skipped during install)")
            print(f"  --description \"...\"          Add description\n")
            print(f"{DIM}Flags for set (remove properties):{RESET}")
            print(f"  --no-optional               Remove optional flag")
            print(f"  --no-dev                    Remove dev_only flag")
            print(f"  --no-description            Remove description")
            sys.exit(0)
        if len(args) >= 2 and args[1] == 'add':
            package_spec = args[2] if len(args) >= 3 else None
            directory = Path(args[3]).resolve() if len(args) >= 4 else Path(".").resolve()
            success = deps_modify_command("add", package_spec, directory, dry_run, is_optional, is_dev, description)
        elif len(args) >= 2 and args[1] == 'remove':
            package_spec = args[2] if len(args) >= 3 else None
            directory = Path(args[3]).resolve() if len(args) >= 4 else Path(".").resolve()
            success = deps_modify_command("remove", package_spec, directory, dry_run)
        elif len(args) >= 2 and args[1] == 'set':
            package_spec = args[2] if len(args) >= 3 else None
            directory = Path(args[3]).resolve() if len(args) >= 4 else Path(".").resolve()
            success = deps_modify_command("set", package_spec, directory, dry_run, is_optional, is_dev, description)
        elif len(args) >= 2 and args[1] not in ('add', 'remove', 'set') and (is_optional or is_dev or description or
                "--no-optional" in sys.argv or "--no-dev" in sys.argv or "--no-description" in sys.argv):
            # Shorthand: tpack deps <pkg> --optional => tpack deps set <pkg> --optional
            package_spec = args[1]
            directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
            success = deps_modify_command("set", package_spec, directory, dry_run, is_optional, is_dev, description)
        else:
            directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
            success = deps_command(directory, search_dir)
        sys.exit(0 if success else 1)

    # tpack version patch/minor/major [directory]
    # tpack patch/minor/major [directory] (aliases)
    if len(args) >= 1 and args[0] == 'version':
        if len(args) < 2 or args[1] not in ('patch', 'minor', 'major'):
            directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
            manifest_path = directory / "manifest.json"
            if not manifest_path.exists():
                print(f"No manifest.json found in {directory}")
                sys.exit(1)
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                from diff_utils import YELLOW, GREEN, CYAN, DIM, RESET
                name = manifest.get('name', directory.name)
                version = manifest.get('version', 'unknown')
                github_url = manifest.get('github', '')

                # Fetch remote version
                remote_version = None
                if github_url:
                    print(f"{DIM}Checking remote version...{RESET}")
                    remote_manifest = fetch_remote_manifest(github_url)
                    if remote_manifest:
                        remote_version = remote_manifest.get('version')

                if remote_version:
                    local_parts = [int(x) for x in version.split('.')]
                    remote_parts = [int(x) for x in remote_version.split('.')]
                    if local_parts > remote_parts:
                        status = f"{CYAN}unpublished{RESET}"
                    elif remote_parts > local_parts:
                        status = f"{YELLOW}update available{RESET}"
                    else:
                        status = f"{GREEN}up to date{RESET}"
                    print(f"{name}  {version} (local)  {remote_version} (remote)  {status}")
                else:
                    print(f"{name} v{version}")

                # Only suggest bumping if remote exists and version hasn't been bumped past it
                version_already_bumped = remote_version and [int(x) for x in version.split('.')] > [int(x) for x in remote_version.split('.')]
                if remote_version and not version_already_bumped:
                    local_changes = check_local_changes(directory, include_commits_ahead=True)
                    if local_changes:
                        print(f"\n  {YELLOW}Local changes detected: {local_changes}.{RESET}")
                        print(f"  {YELLOW}Consider running {GREEN}tpack patch{YELLOW}, {GREEN}tpack minor{YELLOW}, or {GREEN}tpack major{YELLOW}.{RESET}")

                print(f"\nUsage: tpack major|minor|patch")
                print(f"       tpack version major|minor|patch")
            except Exception as e:
                print(f"Error reading manifest.json: {e}")
                sys.exit(1)
            sys.exit(0)
        bump_type = args[1]
        directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
        dry_run = "--dry-run" in sys.argv
        success = version_command(bump_type, directory, dry_run)
        sys.exit(0 if success else 1)

    if len(args) >= 1 and args[0] in ('patch', 'minor', 'major'):
        bump_type = args[0]
        directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
        dry_run = "--dry-run" in sys.argv
        success = version_command(bump_type, directory, dry_run)
        sys.exit(0 if success else 1)

    # tpack status [directory]
    # tpack status <value> [directory]
    if len(args) >= 1 and args[0] == 'status':
        dry_run = "--dry-run" in sys.argv
        if len(args) >= 2 and args[1] in VALID_STATUSES:
            new_status = args[1]
            directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
        elif len(args) >= 2:
            # Could be a directory or a non-standard status
            candidate = Path(args[1])
            if candidate.is_dir():
                new_status = None
                directory = candidate.resolve()
            else:
                new_status = args[1]
                directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
        else:
            new_status = None
            directory = Path(".").resolve()
        success = status_command(new_status, directory, dry_run)
        sys.exit(0 if success else 1)

    # tpack duplicate-check [directory]
    # tpack duplicate-check on/off [directory]
    if len(args) >= 1 and args[0] == 'duplicate-check':
        dry_run = "--dry-run" in sys.argv
        if len(args) >= 2 and args[1] in ('on', 'off'):
            value = args[1] == 'on'
            directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
        elif len(args) >= 2:
            candidate = Path(args[1])
            if candidate.is_dir():
                value = None
                directory = candidate.resolve()
            else:
                from diff_utils import RED, RESET
                print(f"{RED}Invalid value: {args[1]}. Use 'on' or 'off'.{RESET}")
                sys.exit(1)
        else:
            value = None
            directory = Path(".").resolve()
        success = duplicate_check_command(value, directory, dry_run)
        sys.exit(0 if success else 1)

    # tpack platform [directory]
    # tpack platform add <platform> [...] [directory]
    # tpack platform remove <platform> [...] [directory]
    if len(args) >= 1 and args[0] == 'platform':
        dry_run = "--dry-run" in sys.argv
        if len(args) >= 3 and args[1] in ('add', 'remove'):
            action = args[1]
            # Collect platform names (split comma-separated, skip flags)
            raw_names = [a for a in args[2:] if not a.startswith('-')]
            # Split comma-separated values and strip whitespace
            platform_names = []
            directory = Path(".").resolve()
            for name in raw_names:
                parts = [p.strip().rstrip(',') for p in name.split(',') if p.strip().rstrip(',')]
                # Check if this looks like a directory (not a valid platform)
                if len(parts) == 1 and parts[0] not in VALID_PLATFORMS and Path(parts[0]).is_dir():
                    directory = Path(parts[0]).resolve()
                else:
                    platform_names.extend(parts)
        elif len(args) >= 2 and args[1] in ('add', 'remove'):
            action = args[1]
            platform_names = None
            directory = Path(".").resolve()
        elif len(args) >= 2:
            candidate = Path(args[1])
            if candidate.is_dir():
                action = None
                platform_names = None
                directory = candidate.resolve()
            else:
                from diff_utils import RED, RESET
                print(f"{RED}Unknown platform subcommand: {args[1]}{RESET}")
                print(f"Usage:")
                print(f"  tpack platform                       Show current platforms")
                print(f"  tpack platform add <platform> [...]   Add platform(s)")
                print(f"  tpack platform remove <platform> [...] Remove platform(s)")
                sys.exit(1)
        else:
            action = None
            platform_names = None
            directory = Path(".").resolve()
        success = platform_command(action, platform_names, directory, dry_run)
        sys.exit(0 if success else 1)

    # tpack install [dir] or tpack install <github_url>
    if len(args) >= 1 and args[0] == 'install':
        dry_run = "--dry-run" in sys.argv
        auto_yes = "--yes" in sys.argv or "-y" in sys.argv
        target = args[1] if len(args) >= 2 else None
        directory = Path(".").resolve()
        success = install_command(target, directory, dry_run, auto_yes, search_dir)
        sys.exit(0 if success else 1)

    # tpack update [directory]
    if len(args) >= 1 and args[0] == 'update':
        dry_run = "--dry-run" in sys.argv
        auto_yes = "--yes" in sys.argv or "-y" in sys.argv
        directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
        success = consumer_update_command(directory, dry_run, auto_yes, search_dir)
        sys.exit(0 if success else 1)

    # tpack outdated [directory]
    if len(args) >= 1 and args[0] == 'outdated':
        directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
        success = outdated_command(directory, search_dir, search_dir_raw)
        sys.exit(0 if success else 1)

    # tpack sync [dep_name] [directory]
    if len(args) >= 1 and args[0] == 'sync':
        dry_run = "--dry-run" in sys.argv
        dep_name = None
        directory = Path(".").resolve()
        # Parse remaining args: could be [dep_name] [directory] or just [directory]
        if len(args) >= 2:
            # If it looks like a path, treat as directory; otherwise it's a dep name
            candidate = Path(args[1])
            if candidate.is_dir():
                directory = candidate.resolve()
            else:
                dep_name = args[1]
                if len(args) >= 3:
                    directory = Path(args[2]).resolve()
        success = sync_command(dep_name, directory, dry_run, search_dir)
        sys.exit(0 if success else 1)

    # tpack release [directory]
    if len(args) >= 1 and args[0] == 'release':
        dry_run = "--dry-run" in sys.argv
        auto_yes = "--yes" in sys.argv or "-y" in sys.argv
        directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
        success = release_command(directory, dry_run, auto_yes)
        sys.exit(0 if success else 1)

    # tpack pip add <package> [directory]
    # tpack pip remove <package> [directory]
    # tpack pip list [directory]
    if len(args) >= 1 and args[0] == 'pip':
        dry_run = "--dry-run" in sys.argv
        if len(args) >= 2 and args[1] == 'remove':
            package_spec = args[2] if len(args) >= 3 else None
            directory = Path(args[3]).resolve() if len(args) >= 4 else Path(".").resolve()
            success = pip_command("remove", package_spec, directory, dry_run)
        elif len(args) >= 2 and args[1] == 'list':
            directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
            success = pip_command("list", None, directory, dry_run)
        elif len(args) >= 3 and args[1] == 'add':
            package_spec = args[2]
            directory = Path(args[3]).resolve() if len(args) >= 4 else Path(".").resolve()
            success = pip_command("add", package_spec, directory, dry_run)
        elif len(args) >= 2:
            package_spec = args[1]
            directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
            success = pip_command("add", package_spec, directory, dry_run)
        else:
            print("Usage: tpack pip add <package>       Add pip dependency")
            print("       tpack pip remove <package>   Remove pip dependency")
            print("       tpack pip list               List pip dependencies")
            sys.exit(1)
        sys.exit(0 if success else 1)


    # tpack generate <type> [directory]
    if len(args) >= 1 and args[0] == 'generate':
        if len(args) < 2:
            print("Usage: tpack generate <type> [directory]")
            print("Types: manifest, version, readme, shields, install-block, install-block-tpack, workflow-auto-release")
            sys.exit(1)
        gen_type = args[1]
        directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
        dry_run = "--dry-run" in sys.argv
        verbose = "--verbose" in sys.argv or "-v" in sys.argv

        gen_map = {
            "manifest": "generate_manifest.py",
            "version": "generate_version.py",
            "readme": "generate_readme.py",
            "shields": "generate_shields.py",
            "install-block": "generate_install_block.py",
            "install-block-tpack": "generate_install_block_tpack.py",
            "workflow-auto-release": "generate_workflow_auto_release.py",
        }

        if gen_type not in gen_map:
            from diff_utils import RED, RESET
            print(f"{RED}Unknown generator: {gen_type}{RESET}")
            print(f"Available: {', '.join(gen_map.keys())}")
            sys.exit(1)

        from diff_utils import CYAN, RESET
        print(f"\n{CYAN}{directory.name}/{RESET}")

        extra_args = []
        if dry_run:
            extra_args.append("--dry-run")
        if verbose:
            extra_args.append("--verbose")
        if "--force" in sys.argv:
            extra_args.append("--force")

        success = run_generator(gen_map[gen_type], str(directory), extra_args if extra_args else None)
        sys.exit(0 if success else 1)

    # Load config
    config = load_config()
    cfg_defaults = config.get("defaults", {})

    # Parse flags
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    # Determine which generators to run (from config defaults)
    run_manifest = cfg_defaults.get("manifest", True)
    run_version = cfg_defaults.get("version", True)
    run_readme = cfg_defaults.get("readme", True)
    run_shields = cfg_defaults.get("shields", False)

    # Get directories from arguments or use current directory
    # Filter out --search value and flags
    dir_args = [d for d in sys.argv[1:] if not d.startswith('-')]
    if search_dir_raw:
        dir_args = [d for d in dir_args if d != search_dir_raw]
    package_dirs = [Path(d).resolve() for d in dir_args]
    if not package_dirs:
        package_dirs = [Path(".").resolve()]

    if dry_run and verbose:
        print("DRY RUN MODE - No files will be modified\n")

    success_count = 0
    total_count = len(package_dirs)

    for package_dir in package_dirs:
        if process_directory(package_dir, dry_run, verbose, run_manifest, run_version, run_readme, run_shields, search_dir):
            success_count += 1

    from diff_utils import GREEN, DIM, RESET
    dry_run_note = f" {DIM}(dry run - no files modified){RESET}" if dry_run else ""
    if verbose:
        print("\n" + "=" * 60)
        if success_count == total_count:
            if total_count == 1:
                print(f"{GREEN}SUCCESS: All generators completed successfully!{RESET}{dry_run_note}")
            else:
                print(f"{GREEN}SUCCESS: All {total_count} directories processed successfully!{RESET}{dry_run_note}")
        else:
            print(f"Processed {success_count}/{total_count} directories successfully{dry_run_note}")
    else:
        # Non-verbose: simple completion message
        if dry_run:
            print(f"\n{DIM}Done. (dry run - no files modified){RESET}")
        else:
            print(f"\n{DIM}Done.{RESET}")


if __name__ == "__main__":
    main()
