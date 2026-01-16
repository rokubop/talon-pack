"""Generate installation instructions for a Talon package"""
import json
import os
import sys

def generate_installation_instructions(package_dir: str):
    """Generate installation instructions from manifest.json"""
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

    name = manifest.get('name', os.path.basename(full_package_dir))
    github_url = manifest.get('github', '')
    dependencies = manifest.get('dependencies', {})

    print("\n" + "=" * 60)
    print("Installation Instructions (copy to README.md)")
    print("=" * 60)
    print("\n## Installation")
    print("\nClone this repository into your Talon user directory:\n")
    print("```sh")
    print("# mac and linux")
    print("cd ~/.talon/user")
    print("")
    print("# windows")
    print("cd ~/AppData/Roaming/talon/user")
    print("")

    if github_url:
        print(f"git clone {github_url}")
    else:
        print(f"git clone <github_url>  # Add github URL to manifest.json")

    print("```")

    # Handle runtime dependencies
    if dependencies:
        print("\n### Dependencies\n")
        print("This package requires the following dependencies:\n")

        for dep_name, dep_info in dependencies.items():
            version = dep_info.get('version', 'unknown')
            github = dep_info.get('github', '')
            
            if github:
                print(f"- **{dep_name}** (v{version}+)")
                print(f"  ```sh")
                print(f"  git clone {github}")
                print(f"  ```")
            else:
                print(f"- **{dep_name}** (v{version}+)")

    # Handle development dependencies
    dev_dependencies = manifest.get('devDependencies', {})
    if dev_dependencies:
        print("\n### Development Dependencies\n")
        print("Optional dependencies for development and testing:\n")

        for dep_name, dep_info in dev_dependencies.items():
            version = dep_info.get('version', 'unknown')
            github = dep_info.get('github', '')
            
            if github:
                print(f"- **{dep_name}** (v{version}+)")
                print(f"  ```sh")
                print(f"  git clone {github}")
                print(f"  ```")
            else:
                print(f"- **{dep_name}** (v{version}+)")

    if dependencies or dev_dependencies:
        print("\n> **Note**: Review code from unfamiliar sources before installing.")
        print("> Restart Talon after installing dependencies.")

    print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_installation.py <package_directory>")
        print("Example: python generate_installation.py ../my-package")
        sys.exit(1)

    package_dir = sys.argv[1]
    generate_installation_instructions(package_dir)
