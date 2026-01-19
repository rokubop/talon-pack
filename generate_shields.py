"""
Generate shield badges from manifest.json.

e.g., version, status, platform (optional), license (optional), requiresTalonBeta (only if true).
(version | 1.0.0)
(status | stable)
(platform | windows | mac | linux)
(license | MIT)
(talon beta | required)

Usage:
  py generate_shields.py [directory]    # Generate shields for directory (default: current)
                                         # If shields exist in README, updates them
                                         # If not, prints a display block to copy
"""

import json
import re
import sys
from pathlib import Path

STATUS_COLORS = {
    "stable": "green",
    "preview": "orange",
    "experimental": "orange",
    "prototype": "red",
    "reference": "blue",
    "deprecated": "red",
    "archived": "lightgrey"
}

def should_generate_shields(manifest: dict) -> tuple[bool, str]:
    """Check if shields should be generated. Returns (should_generate, reason)."""
    if manifest.get('_generatorShields') == False:
        return False, "_generatorShields is set to false"

    return True, ""


def generate_shields(manifest: dict) -> list[str]:
    """Generate shield badge markdown lines from manifest data."""
    shields = []

    # Version badge
    version = manifest.get("version", "0.0.0").replace("-", "--")
    shields.append(f"![Version](https://img.shields.io/badge/version-{version}-blue)")

    # Status badge with color
    status = manifest.get("status", "unknown").lower().replace("-", "--")
    status_color = STATUS_COLORS.get(status, "lightgrey")
    shields.append(f"![Status](https://img.shields.io/badge/status-{status}-{status_color})")

    # Platform badge (optional)
    platforms = manifest.get("platforms")
    if platforms:
        platform_str = "%20%7C%20".join(p.replace("-", "--") for p in platforms)  # " | " encoded
        shields.append(f"![Platform](https://img.shields.io/badge/platform-{platform_str}-lightgrey)")

    # License badge (optional)
    license_type = manifest.get("license")
    if license_type:
        license_escaped = license_type.replace("-", "--")
        shields.append(f"![License](https://img.shields.io/badge/license-{license_escaped}-green)")

    return shields


def update_readme(readme_path: Path, manifest: dict) -> bool:
    """Update README.md shields. Returns True if updated."""
    if not readme_path.exists():
        return False

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern to match any shield badge
    shield_pattern = r"!\[[^\]]+\]\(https://img\.shields\.io/badge/[^\)]+\)"
    
    # Check if shields exist
    if not re.search(shield_pattern, content):
        return False
    
    # Generate new shields
    new_shields = generate_shields(manifest)
    new_shields_block = "\n".join(new_shields)
    
    # Find all consecutive shields and replace as a block
    shield_block_pattern = r"(?:" + shield_pattern + r"\s*)+"
    content = re.sub(shield_block_pattern, new_shields_block + "\n\n", content, count=1)
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return True


def print_display_block(shields: list[str]):
    """Print shields in a display block format similar to generate_install_block."""
    print("\n" + "=" * 60)
    print("Shield Badges (copy to README.md)")
    print("=" * 60)
    for shield in shields:
        print(shield)
    print("=" * 60 + "\n")


def process_directory(package_dir: str):
    """Process a single directory."""
    package_dir = Path(package_dir).resolve()

    # Find manifest.json
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: manifest.json not found in {package_dir}")
        return False

    # Load manifest
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Check if README exists
        readme_path = package_dir / "README.md"

        # Check if we should generate shields
        should_generate, reason = should_generate_shields(manifest)
        if not should_generate:
            print(f"Skipping shields generation: {reason}")
            return True

        # Generate shields
        shields = generate_shields(manifest)

        if readme_path.exists():
            updated = update_readme(readme_path, manifest)
            if updated:
                print(f"Updated shields in {readme_path}")
            else:
                # README exists but no shields found - print display block
                print(f"\nShields for {package_dir}:")
                print_display_block(shields)
        else:
            # No README - print display block
            print(f"\nShields for {package_dir}:")
            print_display_block(shields)
        return True
    except Exception as e:
        print(f"Error processing {package_dir}: {e}")
        return False


def main():
    # Get directories from arguments or use current directory
    if len(sys.argv) > 1:
        package_dirs = sys.argv[1:]
    else:
        package_dirs = ["."]

    success_count = 0
    total_count = len(package_dirs)

    for package_dir in package_dirs:
        if process_directory(package_dir):
            success_count += 1

    if total_count > 1:
        print(f"\nProcessed {success_count}/{total_count} directories successfully")


if __name__ == "__main__":
    main()
