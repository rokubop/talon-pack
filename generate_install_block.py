"""Generate installation instructions for a Talon repo"""
import json
import os
import sys
from pathlib import Path

# Ensure sibling modules are importable when using Talon's bundled Python
_script_dir = str(Path(__file__).parent.resolve())
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

def generate_pip_install_commands(pip_dependencies: dict) -> str | None:
    """Generate the pip install command block. Returns None if no pip deps."""
    if not pip_dependencies:
        return None

    lines = []
    lines.append("Install using Talon's bundled pip:")
    lines.append("")

    # Build install specs (include version constraint if specified)
    pip_specs = []
    for pip_name, pip_info in pip_dependencies.items():
        version = pip_info.get('version', '')
        if version and version != '*':
            pip_specs.append(f"{pip_name}{version}")
        else:
            pip_specs.append(pip_name)
    all_pip_specs = " ".join(pip_specs)
    lines.append("```sh")
    lines.append("# Windows")
    lines.append(f"~/AppData/Roaming/talon/venv/[VERSION]/Scripts/pip.bat install {all_pip_specs}")
    lines.append("")
    lines.append("# Linux/Mac")
    lines.append(f"~/.talon/bin/pip install {all_pip_specs}")
    lines.append("```")

    return "\n".join(lines)


def generate_installation_markdown(manifest: dict) -> str:
    """Generate installation section markdown from manifest data."""
    github_url = manifest.get('github', '')
    dependencies = manifest.get('dependencies', {})
    dev_dependencies = manifest.get('devDependencies', {})
    pip_dependencies = manifest.get('pipDependencies', {})
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
    has_pip = bool(pip_dependencies)
    has_any_deps = has_requirements or has_dependencies or has_pip

    if has_any_deps:
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

        # Split dependencies into direct and transitive
        direct_deps = {}
        transitive_deps = {}
        if has_dependencies:
            for dep_name, dep_info in dependencies.items():
                if dep_info.get('required_by'):
                    transitive_deps[dep_name] = dep_info
                else:
                    direct_deps[dep_name] = dep_info

        # Add direct dependencies
        if direct_deps:
            for dep_name, dep_info in direct_deps.items():
                version = dep_info.get('min_version') or dep_info.get('version', 'unknown')
                github = dep_info.get('github', '')
                if github:
                    lines.append(f"- [**{dep_name}**]({github}) (v{version}+)")
                else:
                    lines.append(f"- **{dep_name}** (v{version}+)")

        # Add transitive dependencies
        if transitive_deps:
            for dep_name, dep_info in transitive_deps.items():
                version = dep_info.get('min_version') or dep_info.get('version', 'unknown')
                github = dep_info.get('github', '')
                required_by = dep_info.get('required_by', [])
                suffix = f" — required by {', '.join(required_by)}"
                if github:
                    lines.append(f"- [**{dep_name}**]({github}) (v{version}+){suffix}")
                else:
                    lines.append(f"- **{dep_name}** (v{version}+){suffix}")

        # Add pip dependencies to the listing
        if has_pip:
            direct_pip = {k: v for k, v in pip_dependencies.items() if not v.get('required_by')}
            transitive_pip = {k: v for k, v in pip_dependencies.items() if v.get('required_by')}

            for pip_name, pip_info in direct_pip.items():
                version = pip_info.get('version', '')
                suffix = f" ({version})" if version and version != '*' else ""
                pypi_url = f"https://pypi.org/project/{pip_name}/"
                lines.append(f"- [**{pip_name}**]({pypi_url}){suffix} (Python package)")

            for pip_name, pip_info in transitive_pip.items():
                required_by = pip_info.get('required_by', [])
                version = pip_info.get('version', '')
                suffix = f" ({version})" if version and version != '*' else ""
                pypi_url = f"https://pypi.org/project/{pip_name}/"
                lines.append(f"- [**{pip_name}**]({pypi_url}){suffix} (Python package) — required by {', '.join(required_by)}")

    # Determine number of install steps
    has_pip_step = has_pip
    has_clone_step = True  # Always have a clone step
    use_numbered_steps = has_pip_step  # Number steps when there are 2+

    step = 1

    # Step: Install Python packages (before cloning so code can load)
    if has_pip_step:
        pip_commands = generate_pip_install_commands(pip_dependencies)
        if use_numbered_steps:
            lines.append(f"\n### {step}. Install Python Packages")
            step += 1
        else:
            lines.append("\n### Install Python Packages")
        lines.append(f"\n{pip_commands}")

    # Step: Clone repositories
    if use_numbered_steps:
        lines.append(f"\n### {step}. Clone Repositories")
    elif has_any_deps or dev_dependencies:
        lines.append("\n### Install")

    if dependencies:
        lines.append("\nClone the dependencies and this repo into your [Talon](https://talonvoice.com/) user directory:")
    else:
        lines.append("\nClone this repo into your [Talon](https://talonvoice.com/) user directory:")

    lines.append("\n```sh")
    lines.append("# Mac/Linux")
    lines.append("cd ~/.talon/user")
    lines.append("")
    lines.append("# Windows")
    lines.append("cd ~/AppData/Roaming/talon/user")

    # Dependencies clones
    if dependencies:
        lines.append("")
        lines.append("# Dependencies")
        for dep_name, dep_info in dependencies.items():
            required_by = dep_info.get('required_by')
            if required_by:
                continue  # Show transitive deps separately
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

        # Transitive dependencies
        has_transitive = any(dep_info.get('required_by') for dep_info in dependencies.values())
        if has_transitive:
            lines.append("")
            lines.append("# Also required (by dependencies above)")
            for dep_name, dep_info in dependencies.items():
                required_by = dep_info.get('required_by')
                if not required_by:
                    continue
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

    lines.append("```")

    # Dev dependencies section (at the bottom — these are optional)
    if dev_dependencies:
        lines.append("\n### Development Dependencies")
        lines.append("\nOptional dependencies for development and testing:")

        for dep_name, dep_info in dev_dependencies.items():
            version = dep_info.get('min_version') or dep_info.get('version', '')
            github = dep_info.get('github', '')
            version_suffix = f" (v{version}+)" if version else ""
            if github:
                lines.append(f"- [**{dep_name}**]({github}){version_suffix}")
            else:
                lines.append(f"- **{dep_name}**{version_suffix}")

        lines.append("\n```sh")
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
