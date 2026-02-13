"""Generate installation instructions for a Talon repo"""
import json
import os
import sys
from pathlib import Path

# Ensure sibling modules are importable when using Talon's bundled Python
_script_dir = str(Path(__file__).parent.resolve())
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

def generate_installation_markdown(manifest: dict) -> str:
    """Generate installation section markdown from manifest data."""
    github_url = manifest.get('github', '')
    dependencies = manifest.get('dependencies', {})
    dev_dependencies = manifest.get('devDependencies', {})
    requires = manifest.get('requires', [])

    # Map requirement keys to user-friendly descriptions
    requirement_descriptions = {
        "talonBeta": "[**Talon Beta**](https://talon.wiki/Help/beta_talon/)",
        "gamepad": "**Gamepad** - Physical gamepad or joystick controller",
        "streamDeck": "**Elgato Stream Deck** - Elgato Stream Deck device (button panel or pedal)",
        "parrot": "**Parrot** - Trained parrot model with `parrot_integration.py` and `patterns.json` files",
        "eyeTracker": "**Eye Tracker** - Eye tracking device (e.g., Tobii 4C or Tobii 5)",
        "webcam": "**Webcam** - Camera for face tracking commands"
    }

    lines = ["## Installation"]

    # Combine Requirements and Dependencies sections
    has_requirements = bool(requires)
    has_dependencies = bool(dependencies)

    if has_requirements or has_dependencies:
        # Always use "Dependencies" as the title
        lines.append("\n### Dependencies")
        lines.append("")

        # Sort requirements to list Talon Beta first
        sorted_requires = []
        if 'talonBeta' in requires:
            sorted_requires.append('talonBeta')
        sorted_requires.extend([req for req in requires if req != 'talonBeta'])

        # Add requirements
        if has_requirements:
            for req in sorted_requires:
                description = requirement_descriptions.get(req, f"**{req}**")
                lines.append(f"- {description}")

        # Add dependencies
        if has_dependencies:
            for dep_name, dep_info in dependencies.items():
                version = dep_info.get('min_version') or dep_info.get('version', 'unknown')
                github = dep_info.get('github', '')
                if github:
                    lines.append(f"- [**{dep_name}**]({github}) (v{version}+)")
                else:
                    lines.append(f"- **{dep_name}** (v{version}+)")

    # Dev dependencies section
    if dev_dependencies:
        lines.append("\n### Development Dependencies")
        lines.append("\nOptional dependencies for development and testing:")

        for dep_name, dep_info in dev_dependencies.items():
            version = dep_info.get('min_version') or dep_info.get('version', 'unknown')
            github = dep_info.get('github', '')
            if github:
                lines.append(f"- [**{dep_name}**]({github}) (v{version}+)")
            else:
                lines.append(f"- **{dep_name}** (v{version}+)")

    # Install section
    if requires or dependencies or dev_dependencies:
        lines.append("\n### Install")

    if dependencies:
        lines.append("\nClone the dependencies and this repo into your [Talon](https://talonvoice.com/) user directory:")
    else:
        lines.append("\nClone this repo into your [Talon](https://talonvoice.com/) user directory:")

    lines.append("\n```sh")
    lines.append("# mac and linux")
    lines.append("cd ~/.talon/user")
    lines.append("")
    lines.append("# windows")
    lines.append("cd ~/AppData/Roaming/talon/user")

    # Dependencies clones
    if dependencies:
        lines.append("")
        lines.append("# Dependencies")
        for dep_name, dep_info in dependencies.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

    # This repo
    if dependencies or dev_dependencies:
        lines.append("")
        lines.append("# This repo")
    else:
        lines.append("")
    if github_url:
        lines.append(f"git clone {github_url}")
    else:
        lines.append("git clone <github_url>  # Add github URL to manifest.json")

    # Dev dependencies clones (after main repo since they're optional)
    if dev_dependencies:
        lines.append("")
        lines.append("# Dev Dependencies (optional)")
        for dep_name, dep_info in dev_dependencies.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

    lines.append("```")

    # Note
    if dependencies or dev_dependencies:
        lines.append("\n> **Note**: Review code from unfamiliar sources before installing.")

    return "\n".join(lines)


def generate_installation_instructions(package_dir: str):
    """Generate installation instructions from manifest.json and print them."""
    full_package_dir = os.path.abspath(package_dir)

    if not os.path.isdir(full_package_dir):
        print(f"Error: Directory not found: {full_package_dir}")
        sys.exit(1)

    manifest_path = os.path.join(full_package_dir, 'manifest.json')

    if not os.path.exists(manifest_path):
        print(f"Error: manifest.json not found in {full_package_dir}")
        print("Run generate_manifest.py first to create a manifest.")
        sys.exit(1)

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    installation_md = generate_installation_markdown(manifest)

    print("\n" + "=" * 60)
    print("Installation Instructions (copy to README.md)")
    print("=" * 60)
    print(installation_md)
    print("=" * 60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_install_block.py <directory>")
        print("Example: python generate_install_block.py ../my-repo")
        sys.exit(1)

    if len(sys.argv) > 2:
        print("Warning: Multiple directories provided, but only one is supported.")
        print("Processing only the first: " + sys.argv[1])
        print()

    package_dir = sys.argv[1]
    generate_installation_instructions(package_dir)
