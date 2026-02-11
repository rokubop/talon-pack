"""
Run all generators in sequence: manifest, version, and readme.
Will update instead of overwriting existing code where relevant.

Usage:
  tpack [directory]              Update manifest, _version, and readme
  tpack info [dir]               List contributions, dependencies, and info
  tpack version patch [dir]      Bump patch version (1.0.0 -> 1.0.1)
  tpack version minor [dir]      Bump minor version (1.0.0 -> 1.1.0)
  tpack version major [dir]      Bump major version (1.0.0 -> 2.0.0)
  tpack --dry-run                Preview changes without writing files
  tpack -v, --verbose            Show detailed output (default: show only changes)
  tpack --manifest-only          Only run manifest generator
  tpack --version-only           Only run version generator
  tpack --readme-only            Only run readme generator
  tpack --shields-only           Only run shields generator
  tpack --install-block-only     Only run install block generator (outputs to console)
  tpack --no-manifest            Skip manifest generator
  tpack --no-version             Skip version generator
  tpack --no-readme              Skip readme generator
  tpack --no-shields             Skip shields generator
  tpack --help                   Show this help message

Config:
  Edit tpack.config.json to change default behavior (which generators run by default).
"""

import sys
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
                min_ver = dep_info.get('min_version', dep_info.get('version', '?'))
                dep_github = dep_info.get('github', '')
                print(f"  {dep_name} >={min_ver}")
                if dep_github:
                    print(f"    {DIM}{dep_github}{RESET}")

        # Show message if nothing meaningful found
        has_content = requires or contributes or depends or dependencies
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
                      run_install_block: bool = False, shields_only: bool = False) -> bool:
    """Process a single directory with selected generators."""
    if not package_dir.exists():
        from diff_utils import RED, RESET
        print(f"{RED}Error: Directory not found: {package_dir}{RESET}")
        return False

    # Show package name header
    package_name = package_dir.name
    if verbose:
        if run_install_block and not (run_manifest or run_version or run_readme or run_shields):
            print(f"\nPackage: {package_dir}")
        else:
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
            if not shields_only:  # quiet when running as part of normal flow
                shields_args.append("--quiet")
            generators.append(("generate_shields.py", shields_args if shields_args else None))
        if run_install_block:
            generators.append(("generate_install_block.py", None))

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

        if verbose and not (run_install_block and not (run_manifest or run_version or run_readme or run_shields)):
            print(f"\nAll generators completed for {package_dir}")
        return True
    finally:
        # Clean up temp manifest file
        if temp_manifest_path and os.path.exists(temp_manifest_path):
            os.unlink(temp_manifest_path)


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    # Handle subcommands
    args = [a for a in sys.argv[1:] if not a.startswith('-')]

    # tpack info [directory]
    if len(args) >= 1 and args[0] == 'info':
        directory = Path(args[1]).resolve() if len(args) >= 2 else Path(".").resolve()
        success = info_command(directory)
        sys.exit(0 if success else 1)

    # tpack version patch/minor/major [directory]
    if len(args) >= 1 and args[0] == 'version':
        if len(args) < 2 or args[1] not in ('patch', 'minor', 'major'):
            print("Usage: tpack version <patch|minor|major> [directory] [--dry-run]")
            sys.exit(1)
        bump_type = args[1]
        directory = Path(args[2]).resolve() if len(args) >= 3 else Path(".").resolve()
        dry_run = "--dry-run" in sys.argv
        success = version_command(bump_type, directory, dry_run)
        sys.exit(0 if success else 1)

    # Load config
    config = load_config()
    cfg_defaults = config.get("defaults", {})

    # Parse flags
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    no_manifest = "--no-manifest" in sys.argv
    no_version = "--no-version" in sys.argv
    no_readme = "--no-readme" in sys.argv
    no_shields = "--no-shields" in sys.argv
    manifest_only = "--manifest-only" in sys.argv
    version_only = "--version-only" in sys.argv
    readme_only = "--readme-only" in sys.argv
    shields_only = "--shields-only" in sys.argv
    install_block_only = "--install-block-only" in sys.argv

    # Determine which generators to run (config defaults, overridden by flags)
    only_mode = manifest_only or version_only or readme_only or shields_only or install_block_only
    run_manifest = manifest_only if only_mode else (cfg_defaults.get("manifest", True) and not no_manifest)
    run_version = version_only if only_mode else (cfg_defaults.get("version", True) and not no_version)
    run_readme = readme_only if only_mode else (cfg_defaults.get("readme", True) and not no_readme)
    run_shields = shields_only if only_mode else (cfg_defaults.get("shields", False) and not no_shields)
    run_install_block = install_block_only if only_mode else False

    # Get directories from arguments or use current directory
    package_dirs = [Path(d).resolve() for d in sys.argv[1:] if not d.startswith('-')]
    if not package_dirs:
        package_dirs = [Path(".").resolve()]

    if dry_run and verbose:
        print("DRY RUN MODE - No files will be modified\n")

    success_count = 0
    total_count = len(package_dirs)

    for package_dir in package_dirs:
        if process_directory(package_dir, dry_run, verbose, run_manifest, run_version, run_readme, run_shields, run_install_block, shields_only):
            success_count += 1

    # Skip noisy success messages for simple output modes
    if not install_block_only:
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
