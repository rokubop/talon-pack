import ast
from collections import Counter
from dataclasses import dataclass, field
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
- status: Package status/category (manually maintained). Can be any value, but these get automatic shield colors:
  - "reference": Personal config/examples, not meant to be used directly
  - "prototype": Proof of concept, testing ideas
  - "experimental": Early stage, expect rough edges
  - "preview": Functional but still improving
  - "stable": Production-ready, safe to depend on
  - "deprecated": Stop using, migrate to alternative
  - "archived": No longer maintained
- namespace: Naming prefix for all contributions (e.g. user.my_package)
- github: GitHub repository URL
- preview: Preview image URL
- author: Package author name (string) or names (list of strings)
- tags: Category tags for the package
- platforms: Platform compatibility (manually added, optional). Array of platform names, e.g. ["windows", "mac", "linux"]
- license: License type (auto-detected from LICENSE file on first run, manually editable, optional). Only included if LICENSE file exists or manually set
- requires: Hardware/software requirements (auto-detected). Possible values: "talonBeta", "eyeTracker", "parrot", "gamepad", "streamDeck", "webcam". Add "requires" to "_generatorFrozenFields" to preserve manual edits
- validateDependencies: Whether to validate dependencies at runtime (default: true)
  - true: Print errors on startup if dependencies not met
  - false: Skip dependency validation
- dependencies: Required packages with versions (auto-generated)
- devDependencies: Dev-only dependencies (manually maintained)
- contributes: Actions/settings/tags/lists/modes/scopes/captures this package provides (auto-generated)
- depends: Actions/settings/etc. this package uses (auto-generated)
- _generator: Tool that generated this manifest (auto-added)
- _generatorVersion: Version of the generator tool (auto-added)
- _generatorRequiresVersionAction: Whether generator should require version action (auto-added)
- _generatorStrictNamespace: Whether generator should validate namespace consistency (default: true, auto-added)
- _generatorFrozenFields: Array of field names to prevent from being auto-updated (optional)
  - Valid values: "requires", "license", "preview", "platforms", "contributes", "depends", "dependencies"
  - Can also freeze sub-fields: "contributes.actions", "depends.tags", etc.
  - Example: ["requires", "license"] to manually control these fields
- _generatorShields: Whether to generate/update shield badges in README.md (default: true, optional)
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

ENTITIES = ["apps", "tags", "modes", "scopes", "settings", "captures", "lists", "actions"]
MOD_ATTR_CALLS = ["setting", "tag", "mode", "list"]
NAMESPACES = ["user", "edit", "core", "app", "code"]

# Built-in Talon action namespaces that should not be added to dependencies
# Sourced from: set(action.split('.')[0] for action in registry.actions) - {'user'}
BUILTIN_ACTION_NAMESPACES = {
    "app", "auto_format", "auto_insert", "browser", "bytes", "clip", "code", "core",
    "deck", "dict", "dictate", "edit", "insert", "key", "list", "math", "menu",
    "migrate", "mimic", "mode", "mouse_click", "mouse_drag", "mouse_move", "mouse_nudge",
    "mouse_release", "mouse_scroll", "mouse_x", "mouse_y", "paste", "path",
    "print", "random", "set", "settings", "skip", "sleep", "sound", "speech", "string",
    "time", "tracking", "tuple", "types", "win"
}

# Built-in Talon tags that should not be added to dependencies
# Sourced from: [tag for tag in registry.tags if not tag.startswith('user.')]
BUILTIN_TAGS = {
    "browser", "terminal"
}

# Built-in Talon modes that should not be added to dependencies
BUILTIN_MODES = {
    "all", "command", "dictation", "sleep"
}

# Built-in Talon settings that should not be added to dependencies
# Sourced from: [setting for setting in registry.settings if not setting.startswith('user.')]
BUILTIN_SETTINGS = {
    "dictate.punctuation", "dictate.word_map", "hotkey_wait", "imgui.dark_mode", "imgui.scale",
    "insert_wait", "key_hold", "key_wait", "paste_wait", "speech._engine_id", "speech._subtitles",
    "speech.debug", "speech.engine", "speech.gain", "speech.language", "speech.latency",
    "speech.microphone", "speech.normalize", "speech.record_all", "speech.record_labels",
    "speech.record_path", "speech.threshold", "speech.timeout", "tracking.zoom_height",
    "tracking.zoom_live", "tracking.zoom_scale", "tracking.zoom_width"
}

# Built-in Talon captures that should not be added to dependencies
# Sourced from: [cap for cap in registry.captures if not cap.startswith('user.')]
BUILTIN_CAPTURES = {
    "digit_string", "digits", "key", "letter", "modifiers", "number", "number_signed",
    "number_small", "number_string", "special_key", "symbol"
}

# Built-in Talon lists that should not be added to dependencies
# Sourced from: [lst for lst in registry.lists if not lst.startswith('user.')]
BUILTIN_LISTS = {
    "digit", "letter", "modifier", "number_meta", "number_scale", "number_sign",
    "number_small", "special_key", "symbol"
}

TALON_BETA_DETECTION_PATTERNS = {
    'talon_files': [
        'parrot(',
        'face(',
        'deck(',
    ],
    'ctx_calls': [
        'dynamic_list',
    ],
    'ctx_subscripts': [
        "selections",
    ],
}

def is_builtin_action(action_name: str) -> bool:
    """Check if an action is a built-in Talon action that shouldn't be tracked as a dependency."""
    namespace = action_name.split('.')[0]
    return namespace in BUILTIN_ACTION_NAMESPACES

def is_builtin_tag(tag_name: str) -> bool:
    """Check if a tag is a built-in Talon tag that shouldn't be tracked as a dependency."""
    return tag_name in BUILTIN_TAGS

def is_builtin_mode(mode_name: str) -> bool:
    """Check if a mode is a built-in Talon mode that shouldn't be tracked as a dependency."""
    return mode_name in BUILTIN_MODES

def is_builtin_setting(setting_name: str) -> bool:
    """Check if a setting is a built-in Talon setting that shouldn't be tracked as a dependency."""
    return setting_name in BUILTIN_SETTINGS

def is_builtin_capture(capture_name: str) -> bool:
    """Check if a capture is a built-in Talon capture that shouldn't be tracked as a dependency."""
    return capture_name in BUILTIN_CAPTURES

def is_builtin_list(list_name: str) -> bool:
    """Check if a list is a built-in Talon list that shouldn't be tracked as a dependency."""
    return list_name in BUILTIN_LISTS

@dataclass
class Entities:
    apps: set = field(default_factory=set)
    tags: set = field(default_factory=set)
    modes: set = field(default_factory=set)
    scopes: set = field(default_factory=set)
    settings: set = field(default_factory=set)
    captures: set = field(default_factory=set)
    lists: set = field(default_factory=set)
    actions: set = field(default_factory=set)

@dataclass
class AllEntities:
    contributes: Entities = field(default_factory=Entities)
    depends: Entities = field(default_factory=Entities)
    requires_beta: bool = False
    requires: set = field(default_factory=set)  # Hardware and software requirements (parrot, gamepad, eyeTracker, etc.)
    all_actions_used: set = field(default_factory=set)  # Track all actions including built-ins for requirement detection

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

            # function directly decorated with action or capture
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    # @mod.action("full.action.name")
                    if dec.func.attr == 'action' and isinstance(dec.args[0], ast.Constant):
                        # Assume full action name is already provided in the decorator
                        full_action_name = dec.args[0].value
                        if full_action_name not in self.all_entities.contributes.actions:
                            self.all_entities.contributes.actions.add(full_action_name)
                    # @mod.capture(rule="...")
                    elif dec.func.attr == 'capture':
                        full_capture_name = f"user.{node.name}"
                        if full_capture_name not in self.all_entities.contributes.captures:
                            self.all_entities.contributes.captures.add(full_capture_name)

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

            # Handle mod.apps.app_name = "matcher" pattern
            if isinstance(node.targets[0], ast.Attribute):
                # Check if it's mod.apps.something
                if isinstance(node.targets[0].value, ast.Attribute):
                    if node.targets[0].value.attr == "apps":
                        app_name = node.targets[0].attr
                        if app_name not in self.all_entities.contributes.apps:
                            self.all_entities.contributes.apps.add(app_name)

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
                # Check for beta features: ctx.dynamic_list(...), etc.
                if node.func.attr in TALON_BETA_DETECTION_PATTERNS['ctx_calls'] and isinstance(node.func.value, ast.Name):
                    var_name = node.func.value.id
                    if 'ctx' in var_name.lower():
                        self.all_entities.requires_beta = True

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
                # Check if it's an actions.* call
                if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == 'actions':
                    # Capture the full name for all actions (for requirement detection)
                    action_name = f"{node.func.value.attr}.{node.func.attr}"
                    self.all_entities.all_actions_used.add(action_name)

                    # Only add to depends if it's a user-defined namespace
                    if node.func.value.attr in NAMESPACES:
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

    def visit_Subscript(self, node):
        try:
            # Check for beta features: *ctx.selections[ (ctx, app_ctx, etc.)
            # Uses TALON_BETA_DETECTION_PATTERNS['ctx_subscripts'] for detection
            # Only match if variable name contains 'ctx' to avoid false positives
            if isinstance(node.value, ast.Attribute) and node.value.attr in TALON_BETA_DETECTION_PATTERNS['ctx_subscripts']:
                if isinstance(node.value.value, ast.Name):
                    var_name = node.value.value.id
                    if 'ctx' in var_name.lower():
                        self.all_entities.requires_beta = True
        except Exception as e:
            print(f"Error processing subscript: {e}")
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

LICENSE_PATTERNS = {
    "MIT": ["Permission is hereby granted, free of charge", "MIT License"],
    "Apache-2.0": ["Apache License", "Version 2.0"],
    "GPL-3.0": ["GNU GENERAL PUBLIC LICENSE", "Version 3"],
    "GPL-2.0": ["GNU GENERAL PUBLIC LICENSE", "Version 2"],
    "BSD-3-Clause": ["Redistribution and use", "neither the name"],
    "BSD-2-Clause": ["Redistribution and use", "without specific prior written permission"],
    "ISC": ["Permission to use, copy, modify", "ISC"],
    "Unlicense": ["This is free and unencumbered software"],
}

def detect_license(package_dir: str) -> str | None:
    """
    Auto-detect license type from LICENSE file in package directory.

    Returns:
        License type string (e.g., 'MIT', 'Apache-2.0') or None if not found
    """
    license_filenames = ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENCE', 'LICENCE.txt', 'LICENCE.md']

    for filename in license_filenames:
        license_path = os.path.join(package_dir, filename)
        if os.path.exists(license_path):
            try:
                with open(license_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check each license pattern
                for license_type, patterns in LICENSE_PATTERNS.items():
                    if all(pattern.lower() in content.lower() for pattern in patterns):
                        return license_type

                # License file exists but type not recognized
                return "Custom"
            except Exception as e:
                print(f"Warning: Could not read license file {license_path}: {e}")
                return None

    return None

def check_requires_talon_beta_in_talon_files(folder_path: str) -> bool:
    """
    Check if .talon files use beta features.
    Uses patterns defined in TALON_BETA_DETECTION_PATTERNS['talon_files'] constant.
    (Python beta features are detected during AST parsing)

    Returns:
        True if beta features detected, False otherwise
    """
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.talon'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content_lower = f.read().lower()
                        for pattern in TALON_BETA_DETECTION_PATTERNS['talon_files']:
                            if pattern in content_lower:
                                return True
                except Exception as e:
                    # Skip files that can't be read
                    pass

    return False

# ==============================================================================
# TALON FILE PARSING
# ==============================================================================

def parse_talon_file(file_path: str, all_entities: AllEntities) -> None:
    """
    Parse a .talon file to extract dependencies (actions, captures, lists, settings, tags, modes, scopes).

    Context header patterns (before '-' separator):
    - tag: user.tag_name
    - mode: command
    - scope: user.scope_name
    - settings(): user.setting = value

    Command body patterns (after '-' separator):
    - Actions: user.action_name() or actions.user.action_name()
    - Captures: <user.capture_name>
    - Lists: {user.list_name}
    - Settings: settings.get("user.setting_name")

    Note: Ignores configuration settings like 'code.language: python' as these are not dependencies.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split context header from command body
        # Handle both formats: "context\n-\ncommands" and "-\ncommands" (no context header)
        if content.startswith('-\n') or content.startswith('-\r\n'):
            # No context header, everything is command body
            context_header = ""
            command_body = content.split('\n', 1)[1] if '\n' in content else ""
        else:
            # Has context header, split on separator
            parts = content.split('\n-\n', 1)
            if len(parts) == 1:
                parts = content.split('\r\n-\r\n', 1)  # Handle Windows line endings
            context_header = parts[0] if len(parts) > 0 else ""
            command_body = parts[1] if len(parts) > 1 else ""

        # ==============================================================================
        # CONTEXT HEADER PARSING (before '-')
        # ==============================================================================

        # Extract tags: tag: user.tag_name
        # Match lines like 'tag: user.my_tag' or 'and tag: user.my_tag' or 'not tag: user.my_tag'
        tag_pattern = r'^\s*(?:and\s+|not\s+)?tag:\s+(user\.[a-z_][a-z0-9_]*)'
        for match in re.finditer(tag_pattern, context_header, re.MULTILINE):
            all_entities.depends.tags.add(match.group(1))

        # Extract apps: app: app_name
        # Match lines like 'app: vscode' or 'app: celeste'
        app_pattern = r'^\s*(?:and\s+|not\s+)?app:\s+([a-z_][a-z0-9_]*)'
        for match in re.finditer(app_pattern, context_header, re.MULTILINE):
            all_entities.depends.apps.add(match.group(1))

        # Extract modes: mode: command or mode: user.custom_mode
        # Match lines like 'mode: command' or 'and mode: dictation' or 'mode: user.my_mode'
        mode_pattern = r'^\s*(?:and\s+|not\s+)?mode:\s+([a-z_][a-z0-9_.]*)'
        for match in re.finditer(mode_pattern, context_header, re.MULTILINE):
            all_entities.depends.modes.add(match.group(1))

        # Extract scopes: scope: user.scope_name
        # Match lines like 'scope: user.my_scope'
        scope_pattern = r'^\s*(?:and\s+|not\s+)?scope:\s+(user\.[a-z_][a-z0-9_]*)'
        for match in re.finditer(scope_pattern, context_header, re.MULTILINE):
            all_entities.depends.scopes.add(match.group(1))

        # Extract settings from settings() block: user.setting_name = value
        # Match patterns like 'user.my_setting = 100'
        settings_in_block_pattern = r'^\s+(user\.[a-z_][a-z0-9_]*)\s*='
        for match in re.finditer(settings_in_block_pattern, context_header, re.MULTILINE):
            all_entities.depends.settings.add(match.group(1))

        # ==============================================================================
        # COMMAND BODY PARSING (after '-')
        # ==============================================================================

        # Extract user actions: user.action_name()
        # Matches: user.my_action(), user.my_action(arg1, arg2)
        user_action_pattern = r'\buser\.([a-z_][a-z0-9_]*)\s*\('
        for match in re.finditer(user_action_pattern, command_body):
            action_name = f"user.{match.group(1)}"
            all_entities.depends.actions.add(action_name)

        # Extract actions with explicit namespace: actions.user.action_name()
        # Matches: actions.user.my_action()
        actions_user_pattern = r'\bactions\.user\.([a-z_][a-z0-9_]*)\s*\('
        for match in re.finditer(actions_user_pattern, command_body):
            action_name = f"user.{match.group(1)}"
            all_entities.depends.actions.add(action_name)

        # Extract captures: <user.capture_name>
        # Matches: <user.my_capture>, <user.text>, etc.
        capture_pattern = r'<(user\.[a-z_][a-z0-9_]*)>'
        for match in re.finditer(capture_pattern, command_body):
            all_entities.depends.captures.add(match.group(1))

        # Extract lists: {user.list_name}
        # Matches: {user.my_list}, {user.letters}, etc.
        list_pattern = r'\{(user\.[a-z_][a-z0-9_]*)\}'
        for match in re.finditer(list_pattern, command_body):
            all_entities.depends.lists.add(match.group(1))

        # Extract settings: settings.get("user.setting_name")
        # Matches: settings.get("user.my_setting") or settings.get('user.my_setting')
        settings_get_pattern = r'settings\.get\s*\(\s*["\']([^"\']+)["\']\s*\)'
        for match in re.finditer(settings_get_pattern, command_body):
            all_entities.depends.settings.add(match.group(1))

        # ==============================================================================
        # REQUIREMENTS DETECTION
        # ==============================================================================

        # Detect gamepad requirement: gamepad(
        if re.search(r'\bgamepad\s*\(', command_body):
            all_entities.requires.add("gamepad")

        # Detect Stream Deck requirement: deck(
        if re.search(r'\bdeck\s*\(', command_body):
            all_entities.requires.add("streamDeck")

        # Detect parrot requirement: parrot(
        if re.search(r'\bparrot\s*\(', command_body):
            all_entities.requires.add("parrot")

        # Detect webcam requirement: face(
        if re.search(r'\bface\s*\(', command_body):
            all_entities.requires.add("webcam")

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

def apply_frozen_fields(new_manifest: dict, existing_manifest: dict, frozen_fields: set):
    """
    Apply frozen fields from existing manifest to new manifest.
    Handles both top-level fields (e.g., "requires") and sub-fields (e.g., "contributes.actions").
    """
    for frozen in frozen_fields:
        if '.' in frozen:
            # Handle sub-field like "contributes.actions"
            parent, child = frozen.split('.', 1)
            if parent in existing_manifest and child in existing_manifest[parent]:
                if parent not in new_manifest:
                    new_manifest[parent] = {}
                if isinstance(existing_manifest[parent], dict):
                    new_manifest[parent][child] = existing_manifest[parent][child]
        else:
            # Handle top-level field like "requires"
            if frozen in existing_manifest:
                new_manifest[frozen] = existing_manifest[frozen]

# ==============================================================================
# FOLDER PROCESSING
# ==============================================================================

def process_folder(folder_path: str) -> tuple[AllEntities, int, int]:
    """
    Walk through a folder and parse all .py and .talon files to extract entities.
    Returns (all_entities, py_file_count, talon_file_count)
    """
    SKIP_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        '.pytest_cache', '.mypy_cache', 'dist', 'build', '.vscode',
        '.idea', 'recordings', 'backup', '.subtrees'
    }

    all_entities = AllEntities()
    py_count = 0
    talon_count = 0

    for root, dirs, files in os.walk(folder_path):
        # Modify dirs in-place to skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith('.py'):
                parse_file(file_path, all_entities)
                py_count += 1
            elif file.endswith('.talon'):
                parse_talon_file(file_path, all_entities)
                talon_count += 1

    return all_entities, py_count, talon_count

def entity_extract(folder_path: str) -> tuple[AllEntities, int, int]:
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
        '.idea', 'recordings', 'backup', '.subtrees'
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
                if manifest.get('_generator') != 'talon-manifest-generator':
                    continue

                manifest_count += 1
                package_name = manifest.get('name')
                package_version = manifest.get('version', '0.0.0')
                package_namespace = manifest.get('namespace', '')
                package_github = manifest.get('github', '')

                if not package_name:
                    continue

                # Index all contributed entities
                contributes = manifest.get('contributes', {})
                for entity_type in ENTITIES:
                    entities = contributes.get(entity_type, [])
                    for entity in entities:
                        entity_to_package[entity] = {
                            'package': package_name,
                            'version': package_version,
                            'namespace': package_namespace,
                            'github': package_github
                        }
            except Exception as e:
                # Silently skip malformed manifests
                pass

    return entity_to_package, manifest_count

def resolve_package_dependencies(depends: Entities, entity_to_package: dict, current_package: str = None) -> dict:
    """
    Resolve package dependencies from entity dependencies.
    Returns a dict of package names to {version, namespace, github}.
    Excludes current_package to prevent self-dependencies.
    """
    package_deps = {}

    for entity_type in ENTITIES:
        entities = getattr(depends, entity_type)
        for entity in entities:
            if entity in entity_to_package:
                pkg_info = entity_to_package[entity]
                pkg_name = pkg_info['package']
                pkg_version = pkg_info['version']
                pkg_namespace = pkg_info['namespace']
                pkg_github = pkg_info.get('github', '')

                if current_package and pkg_name == current_package:
                    continue

                # If we already have this package, keep existing version
                # (in case multiple entities from same package)
                if pkg_name not in package_deps:
                    dep_info = {
                        'version': pkg_version,
                        'namespace': pkg_namespace
                    }
                    if pkg_github:
                        dep_info['github'] = pkg_github
                    package_deps[pkg_name] = dep_info

    return dict(sorted(package_deps.items()))

def infer_namespace_from_entities(contributes: Entities) -> str | None:
    """
    Infer namespace from contributed entities.
    Finds the longest prefix that appears in the majority (>50%) of entities.
    Returns None if no entities exist or no common pattern found.
    """
    all_entities = []

    # Collect all entities from all namespaces
    for entity_type in ENTITIES:
        # Skip apps - they don't follow user.namespace pattern
        if entity_type == 'apps':
            continue

        entities = getattr(contributes, entity_type)
        for entity in entities:
            # Only process entities with a namespace prefix (user., edit., core., etc.)
            if '.' in entity:
                all_entities.append(entity)

    if not all_entities:
        return None

    if len(all_entities) == 1:
        # Single entity - use everything before last underscore, or whole thing
        entity = all_entities[0]
        if '_' in entity:
            return entity.rsplit('_', 1)[0]
        return entity

    # Generate all possible underscore-delimited prefixes for each entity
    prefix_counts = Counter()
    for entity in all_entities:
        parts = entity.split('_')
        # Generate all prefixes: first part, first two parts, etc.
        for i in range(1, len(parts) + 1):
            prefix = '_'.join(parts[:i])
            prefix_counts[prefix] += 1

    # Find longest prefix that appears in >50% of entities
    threshold = len(all_entities) * 0.5
    candidates = [(prefix, count) for prefix, count in prefix_counts.items() if count > threshold]

    if candidates:
        # Sort by length (longest first), then by count (highest first)
        candidates.sort(key=lambda x: (len(x[0]), x[1]), reverse=True)
        return candidates[0][0]

    return None

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

def validate_namespace(namespace: str, contributes: Entities, strict: bool = True) -> int:
    """
    Validates that contributed entities match the expected namespace pattern.
    Prints warnings for any entities that don't follow the pattern.

    Expected pattern: namespace or namespace_*
    Example: If namespace is 'user.my_package', all entities should be:
    - user.my_package (exact match), or
    - user.my_package_something (prefixed)

    Args:
        namespace: Expected namespace pattern
        contributes: Contributed entities to validate
        strict: If False, skip validation entirely

    Returns:
        Number of warnings found
    """
    if not strict:
        return 0

    warnings = []

    # Strip 'user.' prefix for comparison
    namespace_base = namespace[5:] if namespace.startswith('user.') else namespace

    for entity_type in ENTITIES:
        # Skip apps - they don't follow user.namespace pattern
        if entity_type == 'apps':
            continue

        entities = getattr(contributes, entity_type)
        for entity in entities:
            # Only check user.* entities
            if not entity.startswith('user.'):
                continue

            entity_suffix = entity[5:]  # Remove 'user.' prefix

            # Check if entity matches expected pattern
            if entity_suffix:
                # Allow exact match or prefix with underscore
                # Valid: user.mouse_rig or user.mouse_rig_something
                # Invalid: user.other_thing
                if entity_suffix != namespace_base and not entity_suffix.startswith(f"{namespace_base}_"):
                    warnings.append(f"  WARNING: {entity_type}: {entity} (expected '{namespace}' or '{namespace}_*')")

    if warnings:
        print(f"\nNamespace warnings (expected namespace: {namespace}):")
        for warning in warnings:
            print(warning)
        print(f"  To disable these warnings, set '_generatorStrictNamespace': false in manifest.json")
        print()

    return len(warnings)

def check_version_action(namespace: str, contributes: Entities, version_check: bool, package_name: str, package_dir: str, skip_version_errors: bool = False) -> int:
    """
    Check if package provides a version action.

    Args:
        namespace: Package namespace (e.g., 'user.my_package')
        contributes: Contributed entities
        version_check: True to error if missing, False to skip check
        package_name: Name of the package
        package_dir: Absolute path to package directory
        skip_version_errors: If True, suppress error messages (used by generate_all.py)

    Returns:
        Number of errors found (0 or 1)
    """
    if not version_check:
        return 0

    # Strip 'user.' prefix to get base namespace
    namespace_base = namespace[5:] if namespace.startswith('user.') else namespace
    expected_action = f"user.{namespace_base}_version"

    has_version_action = expected_action in contributes.actions

    if not has_version_action:
        # Check if _version.py file exists
        version_file = os.path.join(package_dir, '_version.py')
        if not os.path.exists(version_file):
            if not skip_version_errors:
                print(f"\nERROR: Missing required version action '{expected_action}'")
                print(f"   Run: python generate_version.py {package_name}")
                print(f"   Or set \"_generatorRequiresVersionAction\": false in manifest.json to skip this check")
                print()
                return 1
            # When skipping errors (generate_all.py), don't count as error since it will be fixed next
            return 0
        else:
            print(f"\nWARNING: _version.py exists but action '{expected_action}' not detected")
            print(f"   The file may need to be regenerated or Talon needs to be reloaded")
            print()
            return 0

    return 0

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
    Prune empty arrays from the manifest data.
    Removes empty arrays from 'contributes' and 'depends' sections,
    and removes top-level empty arrays for 'requires' and 'platforms'.
    Keeps 'tags' even if empty (user-defined metadata).
    """
    # Prune contributes and depends sections
    if 'contributes' in manifest_data:
        manifest_data['contributes'] = prune_empty_arrays(manifest_data['contributes'])

    if 'depends' in manifest_data:
        manifest_data['depends'] = prune_empty_arrays(manifest_data['depends'])

    # Prune top-level empty arrays (but keep tags as it's user-defined)
    for field in ['requires', 'platforms']:
        if field in manifest_data and isinstance(manifest_data[field], list) and len(manifest_data[field]) == 0:
            del manifest_data[field]

    return manifest_data

def load_existing_manifest(package_dir: str) -> dict:
    manifest_path = os.path.join(package_dir, 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def create_or_update_manifest(skip_version_errors: bool = False) -> None:
    if len(sys.argv) < 2:
        print("Usage: python manifest_builder.py <directory> [<directory2> ...]")
        print("Example: python manifest_builder.py ../my-package")
        print("Example: python manifest_builder.py ../package1 ../package2")
        sys.exit(1)

    root_path = os.getcwd()

    CREATE_MANIFEST_DIRS = [arg for arg in sys.argv[1:] if not arg.startswith('--')]

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
    total_warnings = 0
    total_errors = 0

    for idx, relative_dir in enumerate(CREATE_MANIFEST_DIRS):
        full_package_dir = os.path.abspath(os.path.join(root_path, relative_dir))

        if os.path.isdir(full_package_dir):
            package_name = os.path.basename(full_package_dir)
            print(f"[{idx + 1}/{len(CREATE_MANIFEST_DIRS)}] Processing {package_name}")

            existing_manifest_data = load_existing_manifest(full_package_dir)
            is_new_manifest = not existing_manifest_data
            new_entity_data, py_count, talon_count = entity_extract(full_package_dir)

            for key in ENTITIES:
                contributes_set = sorted(list(getattr(new_entity_data.contributes, key)))
                depends_list = getattr(new_entity_data.depends, key)

                # Filter out entities that are contributed by this package
                depends_filtered = [entity for entity in depends_list if entity not in contributes_set]

                # Filter out built-in entities based on type
                if key == 'actions':
                    depends_filtered = [entity for entity in depends_filtered if not is_builtin_action(entity)]
                elif key == 'tags':
                    depends_filtered = [entity for entity in depends_filtered if not is_builtin_tag(entity)]
                elif key == 'modes':
                    depends_filtered = [entity for entity in depends_filtered if not is_builtin_mode(entity)]
                elif key == 'settings':
                    depends_filtered = [entity for entity in depends_filtered if not is_builtin_setting(entity)]
                elif key == 'captures':
                    depends_filtered = [entity for entity in depends_filtered if not is_builtin_capture(entity)]
                elif key == 'lists':
                    depends_filtered = [entity for entity in depends_filtered if not is_builtin_list(entity)]

                depends_filtered = sorted(depends_filtered)

                setattr(new_entity_data.contributes, key, contributes_set)
                setattr(new_entity_data.depends, key, depends_filtered)

            # Check if package has any contributions (used for namespace and version checks)
            has_contributions = any([
                new_entity_data.contributes.actions,
                new_entity_data.contributes.settings,
                new_entity_data.contributes.tags,
                new_entity_data.contributes.lists,
                new_entity_data.contributes.modes,
                new_entity_data.contributes.scopes,
                new_entity_data.contributes.captures
            ])

            # Check strict namespace setting
            strict_namespace = existing_manifest_data.get("_generatorStrictNamespace", True)

            # Use existing namespace if present, otherwise infer from contributed entities
            namespace = existing_manifest_data.get("namespace")
            if not namespace and strict_namespace:
                # Only infer namespace if strict mode is enabled
                namespace = infer_namespace_from_entities(new_entity_data.contributes)

                if not namespace:
                    if has_contributions:
                        # No clear namespace pattern detected
                        print(f"WARNING: Could not infer namespace - no prefix appears in >50% of contributions")
                        print(f"  Contributions don't follow a consistent naming pattern")
                        print(f"  Best practice: Use a common prefix for all contributions (e.g., 'user.my_pkg' or 'user.my_pkg_*')")
                        print(f"  Or set 'namespace' manually in manifest.json")
                        print(f"  Or set '_generatorStrictNamespace' to false to skip this check")
                        print()
                        total_warnings += 1
                        namespace = ""
                    else:
                        # No contributions, so no namespace needed
                        namespace = ""

            # Prepend 'user.' to namespace for clarity (unless it's empty and not already prefixed)
            if namespace and not namespace.startswith(('user.', 'edit.', 'core.', 'app.', 'code.')):
                namespace = f"user.{namespace}"

            # Validate namespace only if strict mode is enabled and there are contributions
            if namespace and strict_namespace:
                total_warnings += validate_namespace(namespace, new_entity_data.contributes, strict_namespace)

            # Check version action
            version_check = existing_manifest_data.get("_generatorRequiresVersionAction", True)
            if namespace:  # Only check if package has a namespace
                total_errors += check_version_action(namespace, new_entity_data.contributes, version_check, package_name, full_package_dir, skip_version_errors)

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

                # Resolve package dependencies (exclude current package to prevent self-dependency)
                current_pkg_name = existing_manifest_data.get('name', package_name)
                package_dependencies = resolve_package_dependencies(new_entity_data.depends, entity_to_package, current_pkg_name)

                # Preserve manually specified versions and github URLs from existing manifest
                existing_deps = existing_manifest_data.get("dependencies", {})
                for pkg_name in existing_deps:
                    if pkg_name in package_dependencies:
                        # Handle both old (string) and new (dict) formats
                        if isinstance(existing_deps[pkg_name], str):
                            package_dependencies[pkg_name]['version'] = existing_deps[pkg_name]
                        else:
                            if 'version' in existing_deps[pkg_name]:
                                package_dependencies[pkg_name]['version'] = existing_deps[pkg_name]['version']
                            # Preserve github URL if it exists in the existing manifest
                            if 'github' in existing_deps[pkg_name]:
                                package_dependencies[pkg_name]['github'] = existing_deps[pkg_name]['github']

            # Track dependencies before filtering
            all_resolved_deps = dict(package_dependencies)

            # Remove any dependencies that are in devDependencies
            existing_dev_deps = existing_manifest_data.get("devDependencies", {})
            dev_deps_found = []
            for pkg_name in existing_dev_deps:
                if pkg_name in package_dependencies:
                    dev_deps_found.append(pkg_name)
                    package_dependencies.pop(pkg_name, None)

            # Count contributes and depends
            contributes_count = sum(len(getattr(new_entity_data.contributes, key)) for key in ENTITIES)
            depends_count = sum(len(getattr(new_entity_data.depends, key)) for key in ENTITIES)

            # Show dependency information
            if package_dependencies:
                print(f"Package dependencies:")
                for pkg_name, pkg_info in package_dependencies.items():
                    print(f"  - {pkg_name} ({pkg_info['version']})")
                print()
            elif dev_deps_found:
                print(f"Package dependencies (covered by devDependencies):")
                for pkg_name in dev_deps_found:
                    dev_dep_info = existing_dev_deps[pkg_name]
                    version = dev_dep_info.get('version', 'unknown') if isinstance(dev_dep_info, dict) else dev_dep_info
                    print(f"  - {pkg_name} ({version}) [devDependency]")
                print()
            else:
                print(f"No package dependencies\n")

            # Show contributes breakdown
            if contributes_count > 0:
                breakdown = []
                for key in ENTITIES:
                    count = len(getattr(new_entity_data.contributes, key))
                    if count > 0:
                        breakdown.append(f"{count} {key}")
                print(f"  Contributes: {contributes_count} items ({', '.join(breakdown)})")
            else:
                print(f"  Contributes: 0 items")

            # Show depends breakdown
            if depends_count > 0:
                breakdown = []
                for key in ENTITIES:
                    count = len(getattr(new_entity_data.depends, key))
                    if count > 0:
                        if key == "actions":
                            # Split actions into package and built-in
                            all_actions = getattr(new_entity_data.depends, key)
                            builtin_count = sum(1 for action in all_actions if is_builtin_action(action))
                            package_count = count - builtin_count
                            if package_count > 0 and builtin_count > 0:
                                breakdown.append(f"{package_count} actions, {builtin_count} built-in")
                            elif builtin_count > 0:
                                breakdown.append(f"{builtin_count} built-in actions")
                            else:
                                breakdown.append(f"{count} actions")
                        else:
                            breakdown.append(f"{count} {key}")
                print(f"  Depends: {depends_count} items ({', '.join(breakdown)})")
            else:
                print(f"  Depends: 0 items")

            # Display scan statistics
            print(f"  Scanned {py_count} .py file(s), {talon_count} .talon file(s)")
            print()

            # Auto-detect requirements (parrot, gamepad, streamDeck, webcam, eyeTracker, talonBeta)
            requires_set = set(new_entity_data.requires)

            # Check for eye tracker requirement based on tracking.* actions
            if any(action.startswith('tracking.') for action in new_entity_data.all_actions_used):
                requires_set.add("eyeTracker")

            # Auto-detect Talon beta requirement
            if new_entity_data.requires_beta or check_requires_talon_beta_in_talon_files(full_package_dir):
                requires_set.add("talonBeta")

            # Generate title from package name if this is a new manifest
            default_title = ""
            if is_new_manifest:
                pkg_name = existing_manifest_data.get("name", os.path.basename(full_package_dir))
                # Remove 'talon-' prefix if present
                title_base = pkg_name.replace('talon-', '').replace('talon_', '')
                # Convert to Title Case: hyphens/underscores to spaces, capitalize words
                default_title = title_base.replace('-', ' ').replace('_', ' ').title()

            # Auto-detect preview image if preview field is empty
            preview_value = existing_manifest_data.get("preview", "")
            if not preview_value:
                # Check for common image formats
                for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                    preview_path = os.path.join(full_package_dir, f"preview{ext}")
                    if os.path.exists(preview_path):
                        github_url = existing_manifest_data.get("github", "")
                        if github_url:
                            # Convert github.com URL to raw.githubusercontent.com URL for preview image
                            preview_value = github_url.replace("github.com", "raw.githubusercontent.com").rstrip('/') + f"/main/preview{ext}"
                            print(f"Detected preview image: preview{ext}\n")
                        break

            if "license" in existing_manifest_data:
                license_value = existing_manifest_data["license"]
            else:
                license_value = detect_license(full_package_dir)
                if license_value:
                    print(f"Detected license: {license_value}\n")

            new_manifest_data = {
                "name": existing_manifest_data.get("name", os.path.basename(full_package_dir)),
                "title": existing_manifest_data.get("title", default_title),
                "description": existing_manifest_data.get("description", "Add a description of your Talon package here." if is_new_manifest else "Auto-generated manifest."),
                "version": existing_manifest_data.get("version", "0.1.0"),
                "status": existing_manifest_data.get("status", "experimental"),
                "namespace": namespace,
                "github": existing_manifest_data.get("github", ""),
                "preview": preview_value,
                "author": existing_manifest_data.get("author", ""),
                "tags": existing_manifest_data.get("tags", []),
            }

            # Add optional license field if detected or exists
            if license_value:
                new_manifest_data["license"] = license_value

            # Determine default for _generatorRequiresVersionAction
            # If no contributions exist, should be False. Otherwise preserve existing value or default to True
            if not has_contributions:
                default_require_version = False
            elif is_new_manifest:
                default_require_version = True
            else:
                default_require_version = existing_manifest_data.get("_generatorRequiresVersionAction", True)

            # Filter built-in actions from depends before adding to manifest
            filtered_depends_dict = vars(new_entity_data.depends).copy()
            filtered_depends_dict['actions'] = sorted([
                action for action in new_entity_data.depends.actions
                if not is_builtin_action(action)
            ])

            new_manifest_data.update({
                "requires": sorted(list(requires_set)),
                "dependencies": package_dependencies,
                "devDependencies": existing_manifest_data.get("devDependencies", {}),
                "contributes": vars(new_entity_data.contributes),
                "depends": filtered_depends_dict,
            })

            # Only include validateDependencies if user explicitly set it or there are dependencies
            if "validateDependencies" in existing_manifest_data:
                new_manifest_data["validateDependencies"] = existing_manifest_data["validateDependencies"]
            elif package_dependencies:
                new_manifest_data["validateDependencies"] = True

            new_manifest_data.update({
                "_generator": "talon-manifest-generator",
                "_generatorVersion": get_generator_version(),
                "_generatorRequiresVersionAction": default_require_version,
                "_generatorStrictNamespace": existing_manifest_data.get("_generatorStrictNamespace", True),
                "_generatorFrozenFields": existing_manifest_data.get("_generatorFrozenFields", [])
            })

            # Apply frozen fields if any are specified
            frozen_fields = set(new_manifest_data["_generatorFrozenFields"])
            if frozen_fields:
                # Apply frozen fields: copy specified fields from existing to new manifest
                apply_frozen_fields(new_manifest_data, existing_manifest_data, frozen_fields)

            new_manifest_data = prune_manifest_data(new_manifest_data)
            update_manifest(full_package_dir, new_manifest_data)
            manifest_path = os.path.join(relative_dir, 'manifest.json').replace('\\', '/')
            print(f"Manifest updated: {manifest_path}")

            # Add separator if there are more packages to process
            if idx < len(CREATE_MANIFEST_DIRS) - 1:
                print()

            # Check if _version.py needs updating
            version_file_path = os.path.join(full_package_dir, '_version.py')
            if os.path.exists(version_file_path):
                try:
                    with open(version_file_path, 'r', encoding='utf-8') as f:
                        first_lines = f.read(200)
                        if 'talon-manifest-generator v' in first_lines:
                            existing_version = first_lines.split('v')[1].split('"')[0].split('\n')[0].strip()
                            current_version = get_generator_version()
                            if existing_version != current_version:
                                # Only warn on major or minor version changes, skip patch updates
                                should_warn = False
                                existing_parts = existing_version.split('.')
                                current_parts = current_version.split('.')

                                if len(existing_parts) >= 2 and len(current_parts) >= 2:
                                    existing_major_minor = f"{existing_parts[0]}.{existing_parts[1]}"
                                    current_major_minor = f"{current_parts[0]}.{current_parts[1]}"
                                    should_warn = existing_major_minor != current_major_minor
                                else:
                                    # Can't parse version, show warning
                                    should_warn = True

                                if should_warn:
                                    rel_path = os.path.relpath(full_package_dir)
                                    print(f"WARNING: _version.py is outdated (v{existing_version}, current: v{current_version})")
                                    print(f"  Run: py generate_version.py {rel_path}")
                except:
                    pass

    # Print summary
    if total_warnings > 0 or total_errors > 0:
        print(f"\n{'='*60}")
        print("Summary:")
        if total_warnings > 0:
            print(f"  {total_warnings} warning(s)")
        if total_errors > 0:
            print(f"  {total_errors} error(s)")
        print(f"{'='*60}")

if __name__ == "__main__":
    skip_version_errors = "--skip-version-check" in sys.argv
    create_or_update_manifest(skip_version_errors)