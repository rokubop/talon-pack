"""Generate installation instructions with talon-pack option first, manual clone second."""
import json
import os
import sys
from pathlib import Path

# Ensure sibling modules are importable when using Talon's bundled Python
_script_dir = str(Path(__file__).parent.resolve())
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from generate_install_block import generate_pip_install_commands, _platform_suffix


def generate_installation_markdown_tpack(manifest: dict) -> str:
    """Generate installation section with two options: tpack and manual clone."""
    github_url = manifest.get('github', '')
    dependencies = manifest.get('dependencies', {})
    peer_dependencies = manifest.get('peerDependencies', {})
    dev_dependencies = manifest.get('devDependencies', {})
    bundled_dependencies = manifest.get('bundledDependencies', {})
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
    lines.append("")
    lines.append("Install using [talon-pack](https://github.com/rokubop/talon-pack) or manually clone the repositories.")

    # Dependencies section
    has_requirements = bool(requires)
    has_dependencies = bool(dependencies)
    has_peer = bool(peer_dependencies)
    has_bundled = bool(bundled_dependencies)
    has_pip = bool(pip_dependencies)
    has_any_deps = has_requirements or has_dependencies or has_peer or has_bundled or has_pip

    if has_any_deps:
        lines.append("\n### Dependencies")
        lines.append("")

        # Sort requirements to list Talon Beta first
        sorted_requires = []
        if 'talonBeta' in requires:
            sorted_requires.append('talonBeta')
        sorted_requires.extend([req for req in requires if req != 'talonBeta'])

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

        if direct_deps:
            for dep_name, dep_info in direct_deps.items():
                version = dep_info.get('min_version') or dep_info.get('version', '')
                github = dep_info.get('github', '')
                plat = _platform_suffix(dep_info)
                ver_str = f" (v{version}+)" if version else ""
                if github:
                    lines.append(f"- [**{dep_name}**]({github}){ver_str}{plat}")
                else:
                    lines.append(f"- **{dep_name}**{ver_str}{plat}")

        if transitive_deps:
            for dep_name, dep_info in transitive_deps.items():
                version = dep_info.get('min_version') or dep_info.get('version', '')
                github = dep_info.get('github', '')
                required_by = dep_info.get('required_by', [])
                plat = _platform_suffix(dep_info)
                suffix = f" - required by {', '.join(required_by)}"
                ver_str = f" (v{version}+)" if version else ""
                if github:
                    lines.append(f"- [**{dep_name}**]({github}){ver_str}{plat}{suffix}")
                else:
                    lines.append(f"- **{dep_name}**{ver_str}{plat}{suffix}")

        if has_peer:
            for dep_name, dep_info in peer_dependencies.items():
                version = dep_info.get('min_version') or dep_info.get('version', '')
                github = dep_info.get('github', '')
                plat = _platform_suffix(dep_info)
                suffix = " *(peer dependency)*"
                ver_str = f" (v{version}+)" if version else ""
                if github:
                    lines.append(f"- [**{dep_name}**]({github}){ver_str}{plat}{suffix}")
                else:
                    lines.append(f"- **{dep_name}**{ver_str}{plat}{suffix}")

        if has_bundled:
            bundled_names = []
            for dep_name, dep_info in bundled_dependencies.items():
                version = dep_info.get('version', 'unknown')
                github = dep_info.get('github', '')
                if github:
                    bundled_names.append(f"[{dep_name}]({github}) v{version}")
                else:
                    bundled_names.append(f"{dep_name} v{version}")
            lines.append(f"- **Bundled**: {', '.join(bundled_names)}")

        if has_pip:
            direct_pip = {k: v for k, v in pip_dependencies.items() if not v.get('required_by')}
            transitive_pip = {k: v for k, v in pip_dependencies.items() if v.get('required_by')}

            for pip_name, pip_info in direct_pip.items():
                version = pip_info.get('version', '')
                suffix = f" ({version})" if version and version != '*' else ""
                pypi_url = f"https://pypi.org/project/{pip_name}/"
                optional_label = " *(optional)*" if pip_info.get('optional') else ""
                description = pip_info.get('description', '')
                desc_suffix = f" - {description}" if description and pip_info.get('optional') else ""
                lines.append(f"- [**{pip_name}**]({pypi_url}){suffix} (Python package){optional_label}{desc_suffix}")

            for pip_name, pip_info in transitive_pip.items():
                required_by = pip_info.get('required_by', [])
                version = pip_info.get('version', '')
                suffix = f" ({version})" if version and version != '*' else ""
                pypi_url = f"https://pypi.org/project/{pip_name}/"
                lines.append(f"- [**{pip_name}**]({pypi_url}){suffix} (Python package) - required by {', '.join(required_by)}")

    # Pip install step (before clone options, if needed)
    all_pip_optional = has_pip and all(v.get('optional') for v in pip_dependencies.values())
    if has_pip:
        pip_commands = generate_pip_install_commands(pip_dependencies)
        pip_heading = "Install Python Packages (Optional)" if all_pip_optional else "Install Python Packages"
        lines.append(f"\n### {pip_heading}")
        lines.append(f"\n{pip_commands}")

    # Option 1: Using talon-pack
    lines.append("\n### Option 1: Using talon-pack")
    lines.append("")
    lines.append("Set up [talon-pack](https://github.com/rokubop/talon-pack), then run:")
    lines.append("")
    lines.append("```sh")
    if github_url:
        lines.append(f"tpack install {github_url}")
    else:
        lines.append("tpack install <github_url>  # Add github URL to manifest.json")
    lines.append("```")

    # Option 2: Manual clone
    lines.append("\n### Option 2: Manual Clone")

    if dependencies or peer_dependencies:
        lines.append("\nClone the dependencies and this repo into your [Talon](https://talonvoice.com/) user directory:")
    else:
        lines.append("\nClone this repo into your [Talon](https://talonvoice.com/) user directory:")

    lines.append("\n```sh")
    lines.append("# Mac/Linux")
    lines.append("cd ~/.talon/user")
    lines.append("")
    lines.append("# Windows")
    lines.append("cd ~/AppData/Roaming/talon/user")

    if dependencies:
        lines.append("")
        lines.append("# Dependencies")
        for dep_name, dep_info in dependencies.items():
            if dep_info.get('required_by'):
                continue
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

        has_transitive = any(dep_info.get('required_by') for dep_info in dependencies.values())
        if has_transitive:
            lines.append("")
            lines.append("# Also required (by dependencies above)")
            for dep_name, dep_info in dependencies.items():
                if not dep_info.get('required_by'):
                    continue
                github = dep_info.get('github', '')
                if github:
                    lines.append(f"git clone {github}")

    # Peer dependencies clones
    if peer_dependencies:
        lines.append("")
        lines.append("# Peer dependencies (recommended)")
        for dep_name, dep_info in peer_dependencies.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

    if dependencies or peer_dependencies or dev_dependencies:
        lines.append("")
        lines.append("# This repo")
    else:
        lines.append("")
    if github_url:
        lines.append(f"git clone {github_url}")
    else:
        lines.append("git clone <github_url>  # Add github URL to manifest.json")

    lines.append("```")

    # Dev dependencies
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
    if dependencies or peer_dependencies or dev_dependencies:
        lines.append("\n> **Note**: Review code from unfamiliar sources before installing.")

    return "\n".join(lines)


def generate_installation_instructions_tpack(package_dir: str):
    """Generate installation instructions with tpack option and print them."""
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

    installation_md = generate_installation_markdown_tpack(manifest)

    print("\n" + "=" * 60)
    print("Installation Instructions (copy to README.md)")
    print("=" * 60)
    print(installation_md)
    print("=" * 60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_install_block_tpack.py <directory>")
        print("Example: python generate_install_block_tpack.py ../my-repo")
        sys.exit(1)

    if len(sys.argv) > 2:
        print("Warning: Multiple directories provided, but only one is supported.")
        print("Processing only the first: " + sys.argv[1])
        print()

    package_dir = sys.argv[1]
    generate_installation_instructions_tpack(package_dir)
