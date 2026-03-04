import json
import os
import sys
from pathlib import Path

"""
Generates a `_duplicate_check.py` file that detects if the same package
is loaded from multiple locations in Talon's user directory. This is useful
for packages that are bundled as git subtrees inside another package
(e.g., mouse-rig bundled inside gamekit).

Usage: python generate_duplicate_check.py <directory> [--dry-run] [--verbose]

Examples:
  python generate_duplicate_check.py ../talon-mouse-rig
  python generate_duplicate_check.py ../package1 ../package2
"""

# Ensure sibling modules are importable when using Talon's bundled Python
_script_dir = str(Path(__file__).parent.resolve())
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

def get_generator_version() -> str:
    """Get the version of talon-pack from its own manifest.json"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(script_dir, 'manifest.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            return manifest.get('version', '1.0.0')
    except:
        return '1.0.0'

def generate_duplicate_check(package_dir: str, dry_run: bool = False, verbose: bool = False, alt_manifest_path: str = None) -> None:
    """Generate duplicate check file for a package"""
    full_package_dir = os.path.abspath(package_dir)

    if not os.path.isdir(full_package_dir):
        print(f"Error: Directory not found: {full_package_dir}")
        sys.exit(1)

    manifest_path = alt_manifest_path or os.path.join(full_package_dir, 'manifest.json')
    if not os.path.exists(manifest_path):
        from diff_utils import RED, RESET
        print(f"{RED}Error: manifest.json not found in {full_package_dir}{RESET}")
        print("Run generate_manifest.py first to generate a manifest.")
        sys.exit(1)

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    namespace = manifest.get('namespace', '')
    package_name = manifest.get('name', os.path.basename(full_package_dir))

    if not namespace:
        from diff_utils import RED, RESET
        print(f"{RED}Error: No namespace found in manifest.json{RESET}")
        sys.exit(1)

    # Strip 'user.' prefix for action name
    if namespace.startswith('user.'):
        action_name = namespace[5:]
    else:
        action_name = namespace

    generator_version = get_generator_version()

    file_content = f'''"""Detects if this package is loaded from multiple locations."""
from talon import actions

_duplicate = False
try:
    actions.user.{action_name}_version()
    _duplicate = True
except Exception:
    pass

if _duplicate:
    print("============================================================")
    print("DUPLICATE PACKAGE: {package_name} ({namespace})")
    print("")
    print("  {package_name} is already loaded from another location.")
    print("  Remove the duplicate so only one copy exists in talon/user.")
    print("============================================================")
    raise RuntimeError(
        "Duplicate package: {package_name} ({namespace}) is already loaded."
    )
'''

    output_path = os.path.join(full_package_dir, '_duplicate_check.py')
    file_exists = os.path.exists(output_path)

    existing_content = ""
    if file_exists:
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()

    from diff_utils import diff_text, format_diff_output, status_no_change, status_created, DIM, RESET

    has_changes, diff_output = diff_text(existing_content, file_content, "_duplicate_check.py")

    if dry_run:
        if not file_exists:
            print(status_created("_duplicate_check.py") + f" {DIM}(dry run){RESET}")
            _, new_diff = diff_text("", file_content, "_duplicate_check.py")
            print(format_diff_output(new_diff))
        elif has_changes:
            print(f"_duplicate_check.py: {DIM}(dry run){RESET}")
            print(format_diff_output(diff_output))
        else:
            print(status_no_change("_duplicate_check.py"))
    else:
        if not file_exists:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
            print(status_created("_duplicate_check.py"))
            _, new_diff = diff_text("", file_content, "_duplicate_check.py")
            print(format_diff_output(new_diff))
        elif has_changes:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
            print(f"_duplicate_check.py:")
            print(format_diff_output(diff_output))
        else:
            print(status_no_change("_duplicate_check.py"))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_duplicate_check.py <directory> [--dry-run] [--verbose]")
        print("Example: python generate_duplicate_check.py ../talon-mouse-rig")
        sys.exit(1)

    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    alt_manifest_path = None
    skip_next = False
    package_dirs = []
    for i, arg in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if arg == "--manifest-path" and i + 1 < len(sys.argv):
            alt_manifest_path = sys.argv[i + 1]
            skip_next = True
        elif not arg.startswith('--'):
            package_dirs.append(arg)

    for package_dir in package_dirs:
        generate_duplicate_check(package_dir, dry_run, verbose, alt_manifest_path)
