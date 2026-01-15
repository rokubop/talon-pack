import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
import sys

"""
Script that generates a manifest.json file for folder(s).

Run `python generate_manifest.py <directory> [<directory2> ...]`

Manifest fields:
- name: Package identifier (defaults to folder name, preserved on updates)
- title: Human-readable title of the package
- description: Brief description of what the package does
- version: Version number (semver format)
- status: Package maturity level (manually maintained)
  - "development": Work in progress, not ready for users
  - "experimental": Usable, but expect breaking changes
  - "stable": Production-ready, safe to depend on
  - "deprecated": No longer maintained, migrate away
- namespace: Naming prefix for all contributions (e.g. user.my_package)
- github: GitHub repository URL
- preview: Preview image URL
- author: Package author name
- tags: Category tags for the package
- dependencies: Required packages with versions (auto-generated)
- devDependencies: Dev-only dependencies (manually maintained)
- contributes: Actions/settings/tags/lists/modes/scopes/captures this package provides (auto-generated)
- depends: Actions/settings/etc. this package uses (auto-generated)
- _generator: Tool that generated this manifest (auto-added)
- _generatorVersion: Version of the generator tool (auto-added)
"""

def get_generator_version() -> str:
    """Get the version of manifest_builder from its own manifest.json"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(script_dir, 'manifest.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            return manifest.get('version', '1.0.0')
    except:
        return '1.0.0'  # Fallback if manifest doesn't exist yet

# Require Python 3.12+
if sys.version_info < (3, 12):
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    sys.exit(
        f"Python 3.12 or higher is required (you have {current_version}).\n"
        f"Run with: py -3.12 {os.path.basename(__file__)}"
    )

ENTITIES = ["captures", "lists", "modes", "scopes", "settings", "tags", "actions"]
MOD_ATTR_CALLS = ["setting", "tag", "mode", "list"]
NAMESPACES = ["user", "edit", "core", "app", "code"]

@dataclass
class Entities:
    captures: set = field(default_factory=set)
    lists: set = field(default_factory=set)
    modes: set = field(default_factory=set)
    scopes: set = field(default_factory=set)
    settings: set = field(default_factory=set)
    tags: set = field(default_factory=set)
    actions: set = field(default_factory=set)

@dataclass
class AllEntities:
    contributes: Entities = field(default_factory=Entities)
    depends: Entities = field(default_factory=Entities)

class ParentNodeVisitor(ast.NodeVisitor):
    """A helper visitor class to set the parent attribute for each node."""
    def __init__(self):
        self.parent = None

    def visit(self, node):
        node.parent = self.parent
        previous_parent = self.parent
        self.parent = node
        super().visit(node)
        self.parent = previous_parent

class EntityVisitor(ParentNodeVisitor):
    def __init__(self, all_entities: AllEntities):
        super().__init__()
        self.all_entities = all_entities

    def visit_Attribute(self, node):
        # Check for actions like actions.user.something, actions.edit.something, or actions.core.something
        if isinstance(node.value, ast.Attribute):
            if node.value.attr in NAMESPACES:
                if isinstance(node.value.value, ast.Name) and node.value.value.id == 'actions':
                    # Construct the full action name
                    full_action_name = f"{node.value.attr}.{node.attr}"
                    if full_action_name not in self.all_entities.depends.actions:
                        self.all_entities.depends.actions.add(full_action_name)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        try:
            # function's parent is a class decorated with action_class
            if isinstance(node.parent, ast.ClassDef):
                class_def = node.parent
                for dec in class_def.decorator_list:
                    # @x.action_class(...)
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if dec.func.attr == 'action_class':
                            if isinstance(dec.args[0], ast.Constant):
                                # @ctx.action_class("context")
                                context = dec.args[0].value
                                full_action_name = f"{context}.{node.name}"
                                if full_action_name not in self.all_entities.depends.actions:
                                    self.all_entities.depends.actions.add(full_action_name)
                    # @x.action_class
                    elif isinstance(dec, ast.Attribute) and dec.attr == 'action_class':
                        full_action_name = f"user.{node.name}"
                        if full_action_name not in self.all_entities.contributes.actions:
                            self.all_entities.contributes.actions.add(full_action_name)

            # function directly decorated with action
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr == 'action' and isinstance(dec.args[0], ast.Constant):
                        # Assume full action name is already provided in the decorator
                        full_action_name = dec.args[0].value
                        if full_action_name not in self.all_entities.contributes.actions:
                            self.all_entities.contributes.actions.add(full_action_name)

        except Exception as e:
            print(f"Error processing function definition: {e}")
        finally:
            self.generic_visit(node)



    def visit_Assign(self, node):
        try:
            if isinstance(node.targets[0], ast.Attribute):
                target = node.targets[0].attr
                value = node.value

                # Handle lists (e.g., ctx.lists["user.symbol_key"] = {...})
                if isinstance(node.targets[0].value, ast.Attribute) and node.targets[0].value.attr == "lists":
                    if isinstance(value, ast.Dict) and target not in self.all_entities.depends.lists:
                        self.all_entities.depends.lists.add(target)

                # Handle tags (e.g., ctx.tags = ["user.tabs"])
                elif target == "tags":
                    if isinstance(value, ast.List):
                        for elt in value.elts:
                            if isinstance(elt, ast.Constant):
                                self.all_entities.depends.tags.add(elt.value)

            if isinstance(node.targets[0], ast.Attribute) and node.targets[0].attr == 'matches':
                if isinstance(node.value, ast.Constant):
                    full_string = node.value.value
                elif isinstance(node.value, ast.JoinedStr):
                    full_string = "".join(
                        value.value if isinstance(value, ast.Constant) else "" for value in node.value.values
                    )
                else:
                    full_string = ""

                matches = re.findall(r'(mode|tag):\s*([\w\.]+)', full_string)
                for match_type, match_value in matches:
                    if match_type == 'mode':
                        if match_value not in self.all_entities.depends.modes:
                            self.all_entities.depends.modes.add(match_value)
                    elif match_type == 'tag':
                        if match_value not in self.all_entities.depends.tags:
                            self.all_entities.depends.tags.add(match_value)

        except Exception as e:
            print(f"Error processing assignment: {e}")
        finally:
            self.generic_visit(node)

    def visit_Call(self, node):
        try:
            if isinstance(node.func, ast.Attribute):
                func_attr = node.func.attr
                if func_attr in MOD_ATTR_CALLS:
                    entity_name = None

                    # Handle positional arguments
                    if node.args and isinstance(node.args[0], ast.Constant):
                        entity_name = node.args[0].value

                    # Handle keyword arguments
                    if not entity_name and node.keywords:
                        for kw in node.keywords:
                            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                entity_name = kw.value.value

                    if entity_name and func_attr in MOD_ATTR_CALLS:
                        attr_name = func_attr + 's'
                        getattr(self.all_entities.contributes, attr_name).add(f"user.{entity_name}")

            # Handle actions.user.something calls
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute):
                if node.func.value.attr in NAMESPACES:
                    # Capture the full name, including the prefix
                    action_name = f"{node.func.value.attr}.{node.func.attr}"
                    if action_name not in self.all_entities.depends.actions:
                        self.all_entities.depends.actions.add(action_name)

            # Handle something.get('user.some_setting')
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'settings':
                arg = node.args[0]
                if isinstance(arg, ast.Constant):
                    entity_name = arg.value
                    if entity_name not in self.all_entities.depends.settings:
                        self.all_entities.depends.settings.add(entity_name)

        except Exception as e:
            print(f"Error processing call: {e}")
        finally:
            self.generic_visit(node)

def parse_file(file_path: str, all_entities: AllEntities) -> None:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()
        tree = ast.parse(file_content)
        visitor = EntityVisitor(all_entities)
        visitor.visit(tree)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

def process_folder(folder_path: str) -> AllEntities:
    all_entities = AllEntities()

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                parse_file(file_path, all_entities)

    return all_entities

def entity_extract(folder_path: str) -> AllEntities:
    if not os.path.isdir(folder_path):
        raise ValueError(f"The provided path is not a directory: {folder_path}")

    return process_folder(folder_path)

def scan_all_manifests(talon_root: str) -> dict:
    """
    Scan all manifest.json files in the talon directory tree.
    Returns a dict mapping entity names to package info: {entity: {"package": name, "version": ver}}
    Only indexes manifests generated by this tool.
    """
    # Skip these directories to speed up scanning
    SKIP_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        '.pytest_cache', '.mypy_cache', 'dist', 'build', '.vscode',
        '.idea', 'recordings', 'backup'
    }

    entity_to_package = {}
    manifest_count = 0

    for root, dirs, files in os.walk(talon_root):
        # Modify dirs in-place to skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if 'manifest.json' in files:
            manifest_path = os.path.join(root, 'manifest.json')
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)

                # Only index manifests from our generator
                if manifest.get('_generator') != 'talon-manifest-builder':
                    continue

                manifest_count += 1
                package_name = manifest.get('name')
                package_version = manifest.get('version', '0.0.0')

                if not package_name:
                    continue

                # Index all contributed entities
                contributes = manifest.get('contributes', {})
                for entity_type in ENTITIES:
                    entities = contributes.get(entity_type, [])
                    for entity in entities:
                        entity_to_package[entity] = {
                            'package': package_name,
                            'version': package_version
                        }
            except Exception as e:
                # Silently skip malformed manifests
                pass

    return entity_to_package, manifest_count

def resolve_package_dependencies(depends: Entities, entity_to_package: dict) -> dict:
    """
    Resolve package dependencies from entity dependencies.
    Returns a dict of package names to versions.
    """
    package_deps = {}

    for entity_type in ENTITIES:
        entities = getattr(depends, entity_type)
        for entity in entities:
            if entity in entity_to_package:
                pkg_info = entity_to_package[entity]
                pkg_name = pkg_info['package']
                pkg_version = pkg_info['version']

                # If we already have this package, keep existing version
                # (in case multiple entities from same package)
                if pkg_name not in package_deps:
                    package_deps[pkg_name] = pkg_version

    return dict(sorted(package_deps.items()))

def infer_namespace_from_entities(contributes: Entities) -> str | None:
    """
    Infer namespace from contributed entities.
    Finds the longest common prefix among all user.* entities.
    Returns None if no user.* entities exist.
    """
    user_entities = []

    # Collect all user.* entity suffixes
    for entity_type in ENTITIES:
        entities = getattr(contributes, entity_type)
        for entity in entities:
            if entity.startswith('user.'):
                # Extract part after 'user.'
                suffix = entity[5:]
                user_entities.append(suffix)

    if not user_entities:
        return None

    if len(user_entities) == 1:
        # Single entity - use everything before last underscore, or whole thing
        entity = user_entities[0]
        if '_' in entity:
            return entity.rsplit('_', 1)[0]
        return entity

    # Find longest common prefix
    prefix = user_entities[0]
    for entity in user_entities[1:]:
        # Find common prefix between current prefix and entity
        i = 0
        while i < len(prefix) and i < len(entity) and prefix[i] == entity[i]:
            i += 1
        prefix = prefix[:i]

        if not prefix:
            break

    # Clean up: remove trailing underscore if present
    if prefix.endswith('_'):
        prefix = prefix[:-1]

    return prefix if prefix else None

def infer_namespace_from_package_name(package_name: str) -> str:
    """
    Infer namespace from package name.
    Converts package name to snake_case if needed.
    """
    # Replace hyphens with underscores
    namespace = package_name.replace('-', '_').replace(' ', '_')
    # Remove any non-alphanumeric characters except underscores
    namespace = ''.join(c for c in namespace if c.isalnum() or c == '_')
    return namespace.lower()

def validate_namespace(namespace: str, contributes: Entities) -> None:
    """
    Validate that contributed entities match the package namespace.

    Warns if entities don't follow the user.<namespace>_* convention.
    """
def validate_namespace(namespace: str, contributes: Entities) -> None:
    """
    Validate that contributed entities match the package namespace.
    Warns if entities don't follow the user.<namespace>_* convention.
    """
    warnings = []

    # Strip 'user.' from namespace for comparison if present
    namespace_base = namespace[5:] if namespace.startswith('user.') else namespace

    for entity_type in ENTITIES:
        entities = getattr(contributes, entity_type)
        for entity in entities:
            # Check if entity starts with 'user.'
            if entity.startswith('user.'):
                # Extract the part after 'user.'
                entity_suffix = entity[5:]  # Remove 'user.'
                # Allow exact match or prefix with underscore
                # Valid: user.mouse_rig or user.mouse_rig_something
                # Invalid: user.other_thing
                if entity_suffix != namespace_base and not entity_suffix.startswith(f"{namespace_base}_"):
                    warnings.append(f"  ⚠ {entity_type}: {entity} (expected '{namespace}' or '{namespace}_*')")

    if warnings:
        print(f"\n⚠ Namespace warnings (expected namespace: {namespace}):")
        for warning in warnings:
            print(warning)
        print()

def update_manifest(package_dir: str, manifest_data) -> None:
    manifest_path = os.path.join(package_dir, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

def prune_empty_arrays(data):
    """
    Recursively prune empty arrays from the dictionary.
    """
    if isinstance(data, dict):
        # Recursively prune within each dictionary
        return {k: prune_empty_arrays(v) for k, v in data.items() if not (isinstance(v, list) and len(v) == 0)}
    return data

def prune_manifest_data(manifest_data):
    """
    Prune empty arrays from the 'contributes' and 'depends' sections of the manifest data,
    but keep other empty fields for documentation purposes.
    """
    # Prune contributes and depends sections only
    if 'contributes' in manifest_data:
        manifest_data['contributes'] = prune_empty_arrays(manifest_data['contributes'])

    if 'depends' in manifest_data:
        manifest_data['depends'] = prune_empty_arrays(manifest_data['depends'])

    return manifest_data

def load_existing_manifest(package_dir: str) -> dict:
    manifest_path = os.path.join(package_dir, 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def create_or_update_manifest() -> None:
    if len(sys.argv) < 2:
        print("Usage: python manifest_builder.py <directory> [<directory2> ...]")
        print("Example: python manifest_builder.py ../my-package")
        print("Example: python manifest_builder.py ../package1 ../package2")
        sys.exit(1)

    root_path = os.getcwd()
    CREATE_MANIFEST_DIRS = sys.argv[1:]
    print(f"Processing {len(CREATE_MANIFEST_DIRS)} package(s)...\n")

    # Find talon user directory by going up from script location
    talon_user_dir = root_path
    while talon_user_dir and os.path.basename(talon_user_dir) != 'user':
        parent = os.path.dirname(talon_user_dir)
        if parent == talon_user_dir:  # Reached filesystem root
            break
        talon_user_dir = parent

    if not os.path.exists(root_path):
        print(f"Error: Packages directory not found at {root_path}")
        return

    # Defer manifest scanning until we know if any package has dependencies
    entity_to_package = None
    manifest_count = 0

    for relative_dir in CREATE_MANIFEST_DIRS:
        full_package_dir = os.path.abspath(os.path.join(root_path, relative_dir))

        if os.path.isdir(full_package_dir):
            existing_manifest_data = load_existing_manifest(full_package_dir)
            is_new_manifest = not existing_manifest_data
            new_entity_data = entity_extract(full_package_dir)

            for key in ENTITIES:
                contributes_set = sorted(list(getattr(new_entity_data.contributes, key)))
                depends_filtered = sorted([
                    entity for entity in getattr(new_entity_data.depends, key)
                    if entity not in contributes_set
                ])
                setattr(new_entity_data.contributes, key, contributes_set)
                setattr(new_entity_data.depends, key, depends_filtered)

            package_name = os.path.basename(full_package_dir)

            # Use existing namespace if present, otherwise infer from contributed entities
            namespace = existing_manifest_data.get("namespace")
            if not namespace:
                namespace = infer_namespace_from_entities(new_entity_data.contributes)
            if not namespace:
                # Check if anything is contributed
                has_contributions = any([
                    new_entity_data.contributes.actions,
                    new_entity_data.contributes.settings,
                    new_entity_data.contributes.tags,
                    new_entity_data.contributes.lists,
                    new_entity_data.contributes.modes,
                    new_entity_data.contributes.scopes,
                    new_entity_data.contributes.captures
                ])
                if has_contributions:
                    # Fall back to package name if can't infer from entities
                    namespace = infer_namespace_from_package_name(package_name)
                else:
                    # No contributions, so no namespace needed
                    namespace = ""

            # Prepend 'user.' to namespace for clarity (unless it's empty)
            if namespace and not namespace.startswith('user.'):
                namespace = f"user.{namespace}"

            # Validate namespace only if there are contributions
            if namespace:
                validate_namespace(namespace, new_entity_data.contributes)

            # Check if we need to resolve dependencies
            has_dependencies = any([
                new_entity_data.depends.actions,
                new_entity_data.depends.settings,
                new_entity_data.depends.tags,
                new_entity_data.depends.lists,
                new_entity_data.depends.modes,
                new_entity_data.depends.scopes,
                new_entity_data.depends.captures
            ])

            package_dependencies = {}
            if has_dependencies:
                # Lazy load: only scan manifests if we have dependencies to resolve
                if entity_to_package is None:
                    print("Scanning for package manifests (to resolve dependencies)...")
                    entity_to_package, manifest_count = scan_all_manifests(talon_user_dir)
                    print(f"  Found {manifest_count} packages in workspace\n")

                # Resolve package dependencies
                package_dependencies = resolve_package_dependencies(new_entity_data.depends, entity_to_package)

                # Preserve manually specified versions from existing manifest
                existing_deps = existing_manifest_data.get("dependencies", {})
                for pkg_name in existing_deps:
                    if pkg_name in package_dependencies:
                        # Keep the manually specified version
                        package_dependencies[pkg_name] = existing_deps[pkg_name]

            # Track dependencies before filtering
            all_resolved_deps = dict(package_dependencies)

            # Remove any dependencies that are in devDependencies
            existing_dev_deps = existing_manifest_data.get("devDependencies", {})
            dev_deps_found = []
            for pkg_name in existing_dev_deps:
                if pkg_name in package_dependencies:
                    dev_deps_found.append(pkg_name)
                    package_dependencies.pop(pkg_name, None)

            if package_dependencies:
                print(f"Package dependencies:")
                for pkg_name, pkg_version in package_dependencies.items():
                    print(f"  ✓ {pkg_name} ({pkg_version})")
                print()
            elif dev_deps_found:
                print(f"Package dependencies (covered by devDependencies):")
                for pkg_name in dev_deps_found:
                    print(f"  ✓ {pkg_name} ({existing_dev_deps[pkg_name]}) [devDependency]")
                print()
            elif not has_dependencies:
                print(f"No package dependencies\n")
            else:
                print(f"Dependencies found but unable to resolve to packages\n")

            new_manifest_data = {
                "name": existing_manifest_data.get("name", os.path.basename(full_package_dir)),
                "title": existing_manifest_data.get("title", ""),
                "description": existing_manifest_data.get("description", "Add a description of your Talon package here." if is_new_manifest else "Auto-generated manifest."),
                "version": existing_manifest_data.get("version", "0.1.0"),
                "status": existing_manifest_data.get("status", "development"),
                "namespace": namespace,
                "github": existing_manifest_data.get("github", ""),
                "preview": existing_manifest_data.get("preview", ""),
                "author": existing_manifest_data.get("author", ""),
                "tags": existing_manifest_data.get("tags", []),
                "dependencies": package_dependencies,
                "devDependencies": existing_manifest_data.get("devDependencies", {}),
                "contributes": vars(new_entity_data.contributes),
                "depends": vars(new_entity_data.depends),
                "_generator": "talon-manifest-builder",
                "_generatorVersion": get_generator_version()
            }

            new_manifest_data = prune_manifest_data(new_manifest_data)
            update_manifest(full_package_dir, new_manifest_data)
            manifest_path = os.path.join(full_package_dir, 'manifest.json')
            print(f"Manifest updated: {manifest_path}")

if __name__ == "__main__":
    create_or_update_manifest()