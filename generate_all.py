"""
Run all generators in sequence: manifest, version, and readme.
Will update instead of overwriting existing code where relevant.

Usage:
  tpack [directory]              Generate all files (default: current directory)
  tpack --dry-run                Preview changes without writing files
  tpack --manifest-only          Only run manifest generator
  tpack --version-only           Only run version generator
  tpack --readme-only            Only run readme generator
  tpack --shields-only           Only run shields generator
  tpack --install-block-only     Only run install block generator (outputs to console)
  tpack --no-manifest            Skip manifest generator
  tpack --no-version             Skip version generator
  tpack --no-readme              Skip readme generator
  tpack --help                   Show this help message
"""

import sys
import subprocess
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.resolve()


def run_generator(script_name: str, directory: str, extra_args: list = None) -> bool:
    """Run a generator script and return success status."""
    try:
        # Build full path to the generator script
        script_path = SCRIPT_DIR / script_name
        cmd = [sys.executable, str(script_path), directory]
        if extra_args:
            cmd.extend(extra_args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout, end='')
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}:")
        print(e.stdout, end='')
        print(e.stderr, end='')
        return False


def process_directory(package_dir: Path, dry_run: bool = False,
                      run_manifest: bool = True, run_version: bool = True,
                      run_readme: bool = True, run_shields: bool = False,
                      run_install_block: bool = False) -> bool:
    """Process a single directory with selected generators."""
    if not package_dir.exists():
        print(f"Error: Directory not found: {package_dir}")
        return False

    # Use appropriate message based on mode
    if run_install_block and not (run_manifest or run_version or run_readme or run_shields):
        print(f"\nPackage: {package_dir}")
    else:
        print(f"\nGenerating files for: {package_dir}")
    print("=" * 60)

    # Run generators in sequence
    base_args = ["--skip-version-check"]
    if dry_run:
        base_args.append("--dry-run")

    generators = []
    if run_manifest:
        generators.append(("generate_manifest.py", base_args))
    if run_version:
        generators.append(("generate_version.py", ["--dry-run"] if dry_run else None))
    if run_readme:
        generators.append(("generate_readme.py", ["--dry-run"] if dry_run else None))
    if run_shields:
        generators.append(("generate_shields.py", ["--dry-run"] if dry_run else None))
    if run_install_block:
        generators.append(("generate_install_block.py", None))

    if not generators:
        print("No generators selected to run.")
        return False

    for generator, extra_args in generators:
        print(f"\nRunning {generator}...")
        print("-" * 60)
        if not run_generator(generator, str(package_dir), extra_args):
            print(f"Failed at {generator}")
            return False

    if not (run_install_block and not (run_manifest or run_version or run_readme or run_shields)):
        print(f"\nAll generators completed for {package_dir}")
    return True


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    # Parse flags
    dry_run = "--dry-run" in sys.argv
    no_manifest = "--no-manifest" in sys.argv
    no_version = "--no-version" in sys.argv
    no_readme = "--no-readme" in sys.argv
    manifest_only = "--manifest-only" in sys.argv
    version_only = "--version-only" in sys.argv
    readme_only = "--readme-only" in sys.argv
    shields_only = "--shields-only" in sys.argv
    install_block_only = "--install-block-only" in sys.argv

    # Determine which generators to run
    only_mode = manifest_only or version_only or readme_only or shields_only or install_block_only
    run_manifest = manifest_only if only_mode else not no_manifest
    run_version = version_only if only_mode else not no_version
    run_readme = readme_only if only_mode else not no_readme
    run_shields = shields_only if only_mode else False
    run_install_block = install_block_only if only_mode else False

    # Get directories from arguments or use current directory
    package_dirs = [Path(d).resolve() for d in sys.argv[1:] if not d.startswith('--')]
    if not package_dirs:
        package_dirs = [Path(".").resolve()]

    if dry_run:
        print("DRY RUN MODE - No files will be modified\n")

    success_count = 0
    total_count = len(package_dirs)

    for package_dir in package_dirs:
        if process_directory(package_dir, dry_run, run_manifest, run_version, run_readme, run_shields, run_install_block):
            success_count += 1

    # Skip noisy success messages for simple output modes
    if not install_block_only:
        print("\n" + "=" * 60)
        if success_count == total_count:
            if total_count == 1:
                print("SUCCESS: All generators completed successfully!")
            else:
                print(f"SUCCESS: All {total_count} directories processed successfully!")
        else:
            print(f"Processed {success_count}/{total_count} directories successfully")


if __name__ == "__main__":
    main()
