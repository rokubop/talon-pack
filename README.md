# Manifest Tools for Talon

Generate a manifest.json and _version.py for your Talon repo which includes talon dependencies, contributions, versioning, and dependency checking.

Also includes a script for generating installation instructions.

## Installation

Clone this repository into your Talon user directory:

```sh
# mac and linux
cd ~/.talon/user

# windows
cd ~/AppData/Roaming/talon/user

git clone https://github.com/rokubop/manifest_builder
```

## Usage
```bash
cd talon-manifest-tools

# Primary script
python generate_manifest.py ../talon-package # generates or updates ../talon-package/manifest.json
python generate_manifest.py ../talon-package1 ../talon-package2 # example with multiple packages

# Additional helper scripts
python generate_version.py ../talon-package # generates ../talon-package/_version.py
python generate_install_block.py ../talon-package # outputs install instructions
```

## Troubleshooting

### Python Version Error

The script requires **Python 3.12 or higher**. If you get a version error, you can use Talon's bundled Python 3.13 instead:

**Windows:**
```bash
"C:\Program Files\Talon\python.exe" generate_manifest.py ../talon-package
```

**Mac:**
```bash
/Applications/Talon.app/Contents/Resources/python/bin/python3 generate_manifest.py ../talon-package
```

**Linux:**
```bash
~/.talon/bin/python3 generate_manifest.py ../talon-package
```

## How Manifest Generation Works

Parses Python files using AST to detect Talon actions, settings, tags, lists, modes, scopes, and captures you contribute or depend on. Scans user directory to find all other packages with manifests to build an index of available packages. Maps your imported actions/settings to specific packages and their versions. Creates or updates manifest.json with all discovered information, preserving your manual edits to fields like name, description, etc.

## Example Manifest Output

```json
{
  "name": "talon-my-package",
  "title": "My Package",
  "description": "A brief description of what the package does",
  "version": "1.0.0",
  "namespace": "user.my_package",
  "github": "https://github.com/user/my-package",
  "preview": "",
  "status": "development",
  "author": "Your Name",
  "tags": ["productivity", "editing"],
  "dependencies": {
    "talon-ui-elements": {
      "version": "0.10.0",
      "namespace": "user.ui_elements",
      "github": "https://github.com/user/talon-ui-elements"
    }
  },
  "devDependencies": {},
  "contributes": {
    "actions": ["user.my_package_action"],
    "settings": ["user.my_package_setting"]
  },
  "depends": {
    "actions": ["user.ui_elements_show"]
  },
  "_generator": "talon-manifest-tools",
  "_generatorVersion": "2.0.0"
}
```

### Manifest Fields

| Field | Description |
|-------|-------------|
| name | Package identifier (defaults to folder name, preserved on updates). Recommendation for folder & name: prefix with "talon-". |
| title | Human-readable package title. Recommendation: "Title Case" format |
| description | Brief description of package functionality |
| version | Semantic version number (Major.Minor.Patch) |
| namespace | Naming prefix for all talon actions in this package (e.g. `user.ui_elements` means all actions in this package are `user.ui_elements_*`) |
| github | GitHub repository URL |
| preview | Preview image URL |
| author | Package author name |
| status | Recommended values: "development" (WIP - not ready for users), "experimental" (usable but expect minor bugs or breaking changes later), "stable" (production-ready), "inactive" (no longer maintained) |
| tags | Arbitrary category tags for the package |
| dependencies | Required packages as dict mapping package name to object with `version` (minimum version required, e.g. "0.10.0" means 0.10.0 or higher), `namespace`, and `github` fields. Auto-generated, but once set, versions are preserved - update manually if needed. |
| devDependencies | Dev-only dependencies (manually move items here from `dependencies` if only needed for testing/development) |
| contributes | Actions/settings/etc. this package provides (auto-generated) |
| depends | Actions/settings/etc. this package uses (auto-generated) |
| _generator | Tool that generated this manifest e.g. "talon-manifest-tools" |
| _generatorVersion | Version of the generator tool |

Most fields are preserved across regenerations, but `contributes`, `depends`, and `dependencies` are auto-generated each time.