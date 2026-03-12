"""Generate installation instructions for a Talon repo"""
import json
import os
import sys
from pathlib import Path

# Ensure sibling modules are importable when using Talon's bundled Python
_script_dir = str(Path(__file__).parent.resolve())
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

ALL_PLATFORMS = {"windows", "mac", "linux"}

def _platform_suffix(dep_info: dict) -> str:
    """Return a platform note like ' (Windows/Linux only)' if platforms are restricted."""
    platforms = dep_info.get('platforms', [])
    if not platforms or set(platforms) >= ALL_PLATFORMS:
        return ""
    names = [p.capitalize() if p != "mac" else "Mac" for p in sorted(platforms)]
    return f" ({'/'.join(names)} only)"


def _pip_spec(pip_name: str, pip_info: dict) -> str:
    """Build a single pip install spec string."""
    version = pip_info.get('version', '')
    if version and version != '*':
        return f"{pip_name}{version}"
    return pip_name


def _pip_install_block(pip_specs: list[str]) -> list[str]:
    """Generate platform-specific pip install lines for given specs."""
    all_specs = " ".join(pip_specs)
    return [
        "```sh",
        "# Windows",
        f"~/AppData/Roaming/talon/venv/[VERSION]/Scripts/pip.bat install {all_specs}",
        "",
        "# Linux/Mac",
        f"~/.talon/bin/pip install {all_specs}",
        "```",
    ]


def generate_pip_install_commands(pip_dependencies: dict) -> str | None:
    """Generate the pip install command block. Returns None if no pip deps."""
    if not pip_dependencies:
        return None

    required = {k: v for k, v in pip_dependencies.items() if not v.get('optional')}
    optional = {k: v for k, v in pip_dependencies.items() if v.get('optional')}

    lines = []

    if required:
        lines.append("Install using Talon's bundled pip:")
        lines.append("")
        lines.extend(_pip_install_block([_pip_spec(k, v) for k, v in required.items()]))

    if optional:
        if required:
            lines.append("")
        for pip_name, pip_info in optional.items():
            description = pip_info.get('description', '')
            desc_suffix = f" - {description}" if description else ""
            lines.append(f"**Optional**: `{pip_name}`{desc_suffix}")
            lines.append("")
            lines.extend(_pip_install_block([_pip_spec(pip_name, pip_info)]))

    if not required and not optional:
        return None

    return "\n".join(lines)


def _split_dependencies(dependencies: dict) -> tuple[dict, dict, dict, dict]:
    """Split dependencies into (required_direct, transitive, optional, dev_only) by properties."""
    required_direct = {}
    transitive = {}
    optional = {}
    dev_only = {}
    for dep_name, dep_info in dependencies.items():
        if dep_info.get('dev_only'):
            dev_only[dep_name] = dep_info
        elif dep_info.get('optional'):
            optional[dep_name] = dep_info
        elif dep_info.get('required_by'):
            transitive[dep_name] = dep_info
        else:
            required_direct[dep_name] = dep_info
    return required_direct, transitive, optional, dev_only


def generate_installation_markdown(manifest: dict) -> str:
    """Generate installation section markdown from manifest data."""
    github_url = manifest.get('github', '')
    dependencies = manifest.get('dependencies', {})
    bundled_dependencies = manifest.get('bundledDependencies', {})
    pip_dependencies = manifest.get('pipDependencies', {})
    requires = manifest.get('requires', [])

    # Split dependencies by properties
    required_direct, transitive_deps, optional_deps, dev_deps = _split_dependencies(dependencies)
    required_deps = {**required_direct, **transitive_deps}

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
    has_bundled = bool(bundled_dependencies)
    has_pip = bool(pip_dependencies)
    has_any_deps = has_requirements or bool(dependencies) or has_bundled or has_pip

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

        # Add direct required dependencies
        if required_direct:
            for dep_name, dep_info in required_direct.items():
                version = dep_info.get('min_version') or dep_info.get('version', '')
                github = dep_info.get('github', '')
                plat = _platform_suffix(dep_info)
                ver_str = f" (v{version}+)" if version else ""
                if github:
                    lines.append(f"- [**{dep_name}**]({github}){ver_str}{plat}")
                else:
                    lines.append(f"- **{dep_name}**{ver_str}{plat}")

        # Add transitive dependencies
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

        # Add optional dependencies
        if optional_deps:
            for dep_name, dep_info in optional_deps.items():
                version = dep_info.get('min_version') or dep_info.get('version', '')
                github = dep_info.get('github', '')
                plat = _platform_suffix(dep_info)
                description = dep_info.get('description', '')
                required_by = dep_info.get('required_by', [])
                if description:
                    desc_suffix = f" - {description}"
                elif required_by:
                    desc_suffix = f" - required by {', '.join(required_by)}"
                else:
                    desc_suffix = ""
                ver_str = f" (v{version}+)" if version else ""
                suffix = f" *(optional)*{desc_suffix}"
                if github:
                    lines.append(f"- [**{dep_name}**]({github}){ver_str}{plat}{suffix}")
                else:
                    lines.append(f"- **{dep_name}**{ver_str}{plat}{suffix}")

        # Add bundled dependencies
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

        # Add pip dependencies to the listing
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

    # Determine number of install steps
    has_pip_step = has_pip
    has_clone_step = True  # Always have a clone step
    all_pip_optional = has_pip and all(v.get('optional') for v in pip_dependencies.values())
    use_numbered_steps = has_pip_step and not all_pip_optional  # Number steps when there are 2+ required

    step = 1

    # Step: Install Python packages (before cloning so code can load)
    if has_pip_step:
        pip_commands = generate_pip_install_commands(pip_dependencies)
        pip_heading = "Install Python Packages (Optional)" if all_pip_optional else "Install Python Packages"
        if use_numbered_steps:
            lines.append(f"\n### {step}. {pip_heading}")
            step += 1
        else:
            lines.append(f"\n### {pip_heading}")
        lines.append(f"\n{pip_commands}")

    # Step: Clone repositories
    if use_numbered_steps:
        lines.append(f"\n### {step}. Clone Repositories")
    elif has_any_deps or dev_deps:
        lines.append("\n### Install")

    if required_deps or optional_deps:
        lines.append("\nClone the dependencies and this repo into your [Talon](https://talonvoice.com/) user directory:")
    else:
        lines.append("\nClone this repo into your [Talon](https://talonvoice.com/) user directory:")

    lines.append("\n```sh")
    lines.append("# Mac/Linux")
    lines.append("cd ~/.talon/user")
    lines.append("")
    lines.append("# Windows")
    lines.append("cd ~/AppData/Roaming/talon/user")

    # Required dependencies clones
    if required_direct:
        lines.append("")
        lines.append("# Dependencies")
        for dep_name, dep_info in required_direct.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

    # Transitive dependencies
    if transitive_deps:
        lines.append("")
        lines.append("# Also required (by dependencies above)")
        for dep_name, dep_info in transitive_deps.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

    # Optional dependencies clones
    if optional_deps:
        lines.append("")
        lines.append("# Optional dependencies")
        for dep_name, dep_info in optional_deps.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")

    # This repo
    if required_deps or optional_deps or dev_deps:
        lines.append("")
        lines.append("# This repo")
    else:
        lines.append("")
    if github_url:
        lines.append(f"git clone {github_url}")
    else:
        lines.append("git clone <github_url>  # Add github URL to manifest.json")

    lines.append("```")

    # Dev dependencies section (at the bottom)
    if dev_deps:
        lines.append("\n### Development Dependencies")
        lines.append("\nOptional dependencies for development and testing:")

        for dep_name, dep_info in dev_deps.items():
            version = dep_info.get('min_version') or dep_info.get('version', '')
            github = dep_info.get('github', '')
            version_suffix = f" (v{version}+)" if version else ""
            if github:
                lines.append(f"- [**{dep_name}**]({github}){version_suffix}")
            else:
                lines.append(f"- **{dep_name}**{version_suffix}")

        lines.append("\n```sh")
        for dep_name, dep_info in dev_deps.items():
            github = dep_info.get('github', '')
            if github:
                lines.append(f"git clone {github}")
        lines.append("```")

    # Note
    if dependencies:
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
