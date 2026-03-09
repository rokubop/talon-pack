#!/usr/bin/env bash
# Integration tests for talon-pack
# Run: bash tests/test_tpack.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# No static fixture files — generated at runtime to avoid Talon loading them
if [[ -z "${PYTHON:-}" ]]; then
    if python3 --version &>/dev/null 2>&1; then PYTHON=python3
    elif python --version &>/dev/null 2>&1; then PYTHON=python
    else echo "Python not found"; exit 1; fi
fi
# Set up a fake talon directory so tpack's find_talon_user_dir works.
# It walks up from SCRIPT_DIR looking for a parent named "talon" with user/ and talon.log.
FAKE_ROOT="$(mktemp -d)"
FAKE_TALON="$FAKE_ROOT/talon"
mkdir -p "$FAKE_TALON/user"
touch "$FAKE_TALON/talon.log"
cp -r "$TPACK_DIR" "$FAKE_TALON/talon-pack"
TPACK_SCRIPT="$FAKE_TALON/talon-pack/tpack.py"

cleanup_talon() {
    rm -rf "$FAKE_ROOT"
}
trap cleanup_talon EXIT

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

PASS=0
FAIL=0

# --- Helpers ---

tpack() {
    "$PYTHON" "$TPACK_SCRIPT" "$@"
}

run_test() {
    local expect="$1"  # "pass" or "fail"
    local desc="$2"
    shift 2
    local rc=0
    "$@" > /dev/null 2>&1 || rc=$?
    if [[ "$expect" == "pass" && $rc -eq 0 ]] || [[ "$expect" == "fail" && $rc -ne 0 ]]; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc (exit=$rc, expected=$expect)"
        ((FAIL++)) || true
    fi
}

assert_file_exists() {
    local desc="$1"
    local file="$2"
    if [[ -f "$file" ]]; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc (file not found: $file)"
        ((FAIL++)) || true
    fi
}

assert_file_not_exists() {
    local desc="$1"
    local file="$2"
    if [[ ! -f "$file" ]]; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc (file should not exist: $file)"
        ((FAIL++)) || true
    fi
}

assert_file_contains() {
    local desc="$1"
    local file="$2"
    local pattern="$3"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc (pattern not found: $pattern)"
        ((FAIL++)) || true
    fi
}

assert_output_contains() {
    local desc="$1"
    local pattern="$2"
    shift 2
    local output
    output="$("$@" 2>&1)" || true
    if echo "$output" | grep -q "$pattern"; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc (pattern not found: $pattern)"
        echo -e "    ${DIM}output: $(echo "$output" | head -5)${NC}"
        ((FAIL++)) || true
    fi
}

# Create a fresh working dir with generated fixture files
setup_workdir() {
    local workdir
    workdir="$(mktemp -d)"

    cat > "$workdir/sample.py" << 'PYEOF'
from talon import Module, actions

mod = Module()
mod.setting("tpack_test_setting", type=str, default="hello", desc="A test setting")

@mod.action_class
class Actions:
    def tpack_test_action():
        """A test action"""
        pass

    def tpack_test_other_action(text: str) -> str:
        """Another test action"""
        return text
PYEOF

    cat > "$workdir/sample.talon" << 'TALONEOF'
hello world: user.tpack_test_action()
say <user.text>: user.tpack_test_other_action(text)
TALONEOF

    echo "$workdir"
}

cleanup_workdir() {
    rm -rf "$1"
}

# ============================================================
# Tests
# ============================================================

echo ""
echo "Talon Pack Integration Tests"
echo "========================================"
echo "Python: $($PYTHON --version 2>&1)"
echo ""

# --- Help ---
echo "help:"
run_test pass "tpack --help exits 0" tpack --help
assert_output_contains "--help shows usage" "Usage" tpack --help

# --- Info (no manifest) ---
echo ""
echo "info (no manifest):"
WORKDIR="$(setup_workdir)"
run_test pass "tpack info on dir without manifest" tpack info "$WORKDIR"
cleanup_workdir "$WORKDIR"

# --- Dry Run ---
echo ""
echo "dry-run:"
WORKDIR="$(setup_workdir)"
run_test pass "tpack --dry-run succeeds" tpack --dry-run "$WORKDIR"
assert_file_not_exists "dry-run does not create manifest.json" "$WORKDIR/manifest.json"
assert_file_not_exists "dry-run does not create _version.py" "$WORKDIR/_version.py"
cleanup_workdir "$WORKDIR"

# --- Generate (full run) ---
echo ""
echo "generate (full run):"
WORKDIR="$(setup_workdir)"
run_test pass "tpack generates files" tpack --yes "$WORKDIR"
assert_file_exists "manifest.json created" "$WORKDIR/manifest.json"
assert_file_contains "manifest has name" "$WORKDIR/manifest.json" '"name"'
assert_file_contains "manifest has version" "$WORKDIR/manifest.json" '"version"'
assert_file_contains "manifest has contributes" "$WORKDIR/manifest.json" '"contributes"'
assert_file_contains "manifest detects tpack_test_action" "$WORKDIR/manifest.json" 'tpack_test_action'
assert_file_contains "manifest detects tpack_test_setting" "$WORKDIR/manifest.json" 'tpack_test_setting'
assert_file_contains "manifest has _generator" "$WORKDIR/manifest.json" '"_generator": "talon-pack"'
assert_file_exists "README.md created" "$WORKDIR/README.md"

# --- Info (with manifest) ---
echo ""
echo "info (with manifest):"
run_test pass "tpack info succeeds" tpack info "$WORKDIR"
assert_output_contains "info shows contributes" "Contributes" tpack info "$WORKDIR"
assert_output_contains "info shows actions" "actions" tpack info "$WORKDIR"

# --- Version Bumping ---
echo ""
echo "version bumping:"
assert_output_contains "version shows current version" "v0.0.0\|v0.1.0\|version" tpack version "$WORKDIR"

run_test pass "tpack patch succeeds" tpack patch "$WORKDIR"
assert_file_contains "patch bumped version" "$WORKDIR/manifest.json" '"version": "0.1.1"'

run_test pass "tpack minor succeeds" tpack minor "$WORKDIR"
assert_file_contains "minor bumped version" "$WORKDIR/manifest.json" '"version": "0.2.0"'

run_test pass "tpack major succeeds" tpack major "$WORKDIR"
assert_file_contains "major bumped version" "$WORKDIR/manifest.json" '"version": "1.0.0"'

# --- Pip Commands ---
echo ""
echo "pip commands:"
run_test pass "tpack pip add succeeds" tpack pip add "vgamepad>=1.0.0" "$WORKDIR"
assert_file_contains "pip dep added to manifest" "$WORKDIR/manifest.json" '"vgamepad"'
assert_file_contains "pip dep has version" "$WORKDIR/manifest.json" '>=1.0.0'

run_test pass "tpack pip list succeeds" tpack pip list "$WORKDIR"
assert_output_contains "pip list shows package" "vgamepad" tpack pip list "$WORKDIR"

run_test pass "tpack pip remove succeeds" tpack pip remove vgamepad "$WORKDIR"
# After removing the only pip dep, pipDependencies key should be gone
run_test pass "pip dep removed from manifest" bash -c "! grep -q 'vgamepad' '$WORKDIR/manifest.json'"

# --- Peer Commands ---
echo ""
echo "peer commands:"
# Add a peer dep by injecting a fake installed package
FAKE_PEER_DIR="$FAKE_TALON/user/talon-fake-peer"
mkdir -p "$FAKE_PEER_DIR"
cat > "$FAKE_PEER_DIR/manifest.json" << 'PEEREOF'
{
  "name": "talon-fake-peer",
  "version": "1.2.0",
  "namespace": "user.fake_peer",
  "github": "https://github.com/test/talon-fake-peer",
  "platforms": ["windows", "linux"],
  "_generator": "talon-pack"
}
PEEREOF

run_test pass "tpack peer add succeeds" tpack peer add talon-fake-peer "$WORKDIR"
assert_file_contains "peer dep added to manifest" "$WORKDIR/manifest.json" '"talon-fake-peer"'
assert_file_contains "peer dep has peerDependencies key" "$WORKDIR/manifest.json" '"peerDependencies"'
assert_file_contains "peer dep has min_version" "$WORKDIR/manifest.json" '"min_version": "1.2.0"'
assert_file_contains "peer dep has namespace" "$WORKDIR/manifest.json" '"namespace": "user.fake_peer"'
assert_file_contains "peer dep has platforms" "$WORKDIR/manifest.json" '"platforms"'

run_test pass "tpack peer list succeeds" tpack peer list "$WORKDIR"
assert_output_contains "peer list shows package" "talon-fake-peer" tpack peer list "$WORKDIR"

# Adding same peer dep again should be a noop
run_test pass "tpack peer add duplicate is noop" tpack peer add talon-fake-peer "$WORKDIR"

run_test pass "tpack peer remove succeeds" tpack peer remove talon-fake-peer "$WORKDIR"
run_test pass "peer dep removed from manifest" bash -c "! grep -q 'talon-fake-peer' '$WORKDIR/manifest.json'"
run_test pass "peerDependencies key removed when empty" bash -c "! grep -q 'peerDependencies' '$WORKDIR/manifest.json'"

# Error cases
run_test fail "peer add nonexistent package fails" tpack peer add talon-nonexistent-pkg "$WORKDIR"
run_test fail "peer remove nonexistent package fails" tpack peer remove talon-nonexistent-pkg "$WORKDIR"

# --- Peer Deps in Install Block ---
echo ""
echo "peer deps in install block:"
run_test pass "re-add peer dep for install block test" tpack peer add talon-fake-peer "$WORKDIR"
assert_output_contains "install-block shows peer dependency label" "peer dependency" tpack generate install-block "$WORKDIR"
assert_output_contains "install-block shows peer clone comment" "Peer dependencies" tpack generate install-block "$WORKDIR"
assert_output_contains "install-block shows peer github url" "talon-fake-peer" tpack generate install-block "$WORKDIR"
assert_output_contains "install-block-tpack shows peer dependency label" "peer dependency" tpack generate install-block-tpack "$WORKDIR"

# --- Platform Suffix in Install Block ---
echo ""
echo "platform suffix in install block:"
# The fake peer dep has platforms: ["windows", "linux"], so it should show platform restriction
assert_output_contains "install-block shows platform restriction" "Windows" tpack generate install-block "$WORKDIR"
assert_output_contains "install-block shows platform restriction (Linux)" "Linux" tpack generate install-block "$WORKDIR"

# Clean up peer dep for remaining tests
run_test pass "clean up peer dep" tpack peer remove talon-fake-peer "$WORKDIR"
rm -rf "$FAKE_PEER_DIR"

# --- Deps Command ---
echo ""
echo "deps command:"
# Re-create fake peer package (cleaned up in platform suffix tests)
FAKE_PEER_DIR="$FAKE_TALON/user/talon-fake-peer"
mkdir -p "$FAKE_PEER_DIR"
cat > "$FAKE_PEER_DIR/manifest.json" << 'PEEREOF2'
{
  "name": "talon-fake-peer",
  "version": "1.2.0",
  "namespace": "user.fake_peer",
  "github": "https://github.com/test/talon-fake-peer",
  "platforms": ["windows", "linux"],
  "_generator": "talon-pack"
}
PEEREOF2
# Re-add peer dep and pip dep to test deps view
run_test pass "add peer dep for deps test" tpack peer add talon-fake-peer "$WORKDIR"
run_test pass "add pip dep for deps test" tpack pip add "vgamepad>=1.0.0" "$WORKDIR"

run_test pass "tpack deps succeeds" tpack deps "$WORKDIR"
assert_output_contains "deps shows Dependencies section" "Dependencies" tpack deps "$WORKDIR"
assert_output_contains "deps shows Peer Dependencies section" "Peer Dependencies" tpack deps "$WORKDIR"
assert_output_contains "deps shows Pip Dependencies section" "Pip Dependencies" tpack deps "$WORKDIR"
assert_output_contains "deps shows peer dep name" "talon-fake-peer" tpack deps "$WORKDIR"
assert_output_contains "deps shows pip dep name" "vgamepad" tpack deps "$WORKDIR"
assert_output_contains "deps shows install status for peer" "installed\|not installed" tpack deps "$WORKDIR"

# Clean up
run_test pass "remove peer dep after deps test" tpack peer remove talon-fake-peer "$WORKDIR"
run_test pass "remove pip dep after deps test" tpack pip remove vgamepad "$WORKDIR"
rm -rf "$FAKE_PEER_DIR"

# No deps case
WORKDIR_NODEPS="$(setup_workdir)"
run_test pass "tpack generates files for nodeps" tpack --yes "$WORKDIR_NODEPS"
run_test pass "tpack deps with no deps succeeds" tpack deps "$WORKDIR_NODEPS"
assert_output_contains "deps shows no deps message" "No dependencies" tpack deps "$WORKDIR_NODEPS"
cleanup_workdir "$WORKDIR_NODEPS"

# --- Duplicate Check ---
echo ""
echo "duplicate-check:"
run_test pass "duplicate-check shows status" tpack duplicate-check "$WORKDIR"
assert_output_contains "duplicate-check shows off by default" "off" tpack duplicate-check "$WORKDIR"
run_test pass "duplicate-check on succeeds" tpack duplicate-check on "$WORKDIR"
assert_file_contains "manifest has _generatorDuplicateCheck true" "$WORKDIR/manifest.json" '"_generatorDuplicateCheck": true'
assert_file_contains "_version.py has duplicate check" "$WORKDIR/_version.py" "DUPLICATE PACKAGE"
run_test pass "duplicate-check off succeeds" tpack duplicate-check off "$WORKDIR"
assert_file_contains "manifest has _generatorDuplicateCheck false" "$WORKDIR/manifest.json" '"_generatorDuplicateCheck": false'
run_test pass "_version.py no longer has duplicate check" bash -c "! grep -q 'DUPLICATE PACKAGE' '$WORKDIR/_version.py'"

# --- Generate Individual ---
echo ""
echo "generate individual:"
run_test pass "generate manifest succeeds" tpack generate manifest "$WORKDIR"
run_test pass "generate version succeeds" tpack generate version "$WORKDIR"
run_test pass "generate readme succeeds" tpack generate readme "$WORKDIR"
run_test pass "generate install-block succeeds" tpack generate install-block "$WORKDIR"
run_test pass "generate install-block-tpack succeeds" tpack generate install-block-tpack "$WORKDIR"
run_test pass "generate workflow-auto-release succeeds" tpack generate workflow-auto-release "$WORKDIR" --force
assert_file_exists "release.yml created" "$WORKDIR/.github/workflows/release.yml"
assert_file_contains "release.yml has version check" "$WORKDIR/.github/workflows/release.yml" "manifest.json"
# Running again should be idempotent (already up to date)
run_test pass "generate workflow-auto-release idempotent" tpack generate workflow-auto-release "$WORKDIR" --force

# --- Regenerate (idempotent) ---
echo ""
echo "idempotent regeneration:"
cp "$WORKDIR/manifest.json" "$WORKDIR/manifest.json.before"
run_test pass "second tpack run succeeds" tpack --yes "$WORKDIR"
assert_file_contains "manifest still valid after regen" "$WORKDIR/manifest.json" '"_generator": "talon-pack"'

# --- Dry-run with --verbose ---
echo ""
echo "verbose dry-run:"
run_test pass "tpack --dry-run --verbose succeeds" tpack --dry-run --verbose "$WORKDIR"

# --- Error Cases ---
echo ""
echo "error cases:"
run_test fail "generate unknown type fails" tpack generate badtype "$WORKDIR"

cleanup_workdir "$WORKDIR"

# --- Workflow Auto-Release Visibility Checks ---
echo ""
echo "workflow-auto-release visibility checks:"

# No github URL in manifest -> should fail without --force
WORKDIR_VIS="$(setup_workdir)"
tpack --yes "$WORKDIR_VIS" > /dev/null 2>&1
# Remove github field to simulate no URL
"$PYTHON" -c "
import json, sys
p = sys.argv[1] + '/manifest.json'
with open(p) as f: d = json.load(f)
d.pop('github', None)
with open(p, 'w') as f: json.dump(d, f, indent=2)
" "$WORKDIR_VIS"
run_test fail "no github URL blocks without --force" tpack generate workflow-auto-release "$WORKDIR_VIS"
assert_file_not_exists "release.yml not created without --force" "$WORKDIR_VIS/.github/workflows/release.yml"
run_test pass "no github URL proceeds with --force" tpack generate workflow-auto-release "$WORKDIR_VIS" --force
assert_file_exists "release.yml created with --force" "$WORKDIR_VIS/.github/workflows/release.yml"
cleanup_workdir "$WORKDIR_VIS"

# Public repo URL -> should succeed without --force
WORKDIR_PUB="$(setup_workdir)"
tpack --yes "$WORKDIR_PUB" > /dev/null 2>&1
"$PYTHON" -c "
import json, sys
p = sys.argv[1] + '/manifest.json'
with open(p) as f: d = json.load(f)
d['github'] = 'https://github.com/rokubop/talon-pack'
with open(p, 'w') as f: json.dump(d, f, indent=2)
" "$WORKDIR_PUB"
run_test pass "public repo succeeds without --force" tpack generate workflow-auto-release "$WORKDIR_PUB"
assert_file_exists "release.yml created for public repo" "$WORKDIR_PUB/.github/workflows/release.yml"
cleanup_workdir "$WORKDIR_PUB"

# Dry-run should not create file
WORKDIR_DRY="$(setup_workdir)"
tpack --yes "$WORKDIR_DRY" > /dev/null 2>&1
"$PYTHON" -c "
import json, sys
p = sys.argv[1] + '/manifest.json'
with open(p) as f: d = json.load(f)
d['github'] = 'https://github.com/rokubop/talon-pack'
with open(p, 'w') as f: json.dump(d, f, indent=2)
" "$WORKDIR_DRY"
run_test pass "workflow-auto-release dry-run succeeds" tpack generate workflow-auto-release "$WORKDIR_DRY" --dry-run
assert_file_not_exists "release.yml not created on dry-run" "$WORKDIR_DRY/.github/workflows/release.yml"
cleanup_workdir "$WORKDIR_DRY"

# --- Setup Script (bash) ---
echo ""
echo "setup.sh:"
run_test pass "setup.sh passes bash -n syntax check" bash -n "$TPACK_DIR/setup.sh"

# --- Community Repo Detection ---
echo ""
echo "community repo detection:"

# Create a fake community repo structure
FAKE_COMMUNITY="$FAKE_TALON/user/community"
mkdir -p "$FAKE_COMMUNITY/core"
mkdir -p "$FAKE_COMMUNITY/apps"
mkdir -p "$FAKE_COMMUNITY/lang"
mkdir -p "$FAKE_COMMUNITY/plugin"
mkdir -p "$FAKE_COMMUNITY/tags"
touch "$FAKE_COMMUNITY/settings.talon"

# Add a contributed action to the community repo
cat > "$FAKE_COMMUNITY/core/sample_community.py" << 'COMMEOF'
from talon import Module

mod = Module()

@mod.action_class
class Actions:
    def community_test_action():
        """A community action"""
        pass
COMMEOF

# Create a package that depends on the community action
WORKDIR_COMM="$(setup_workdir)"
cat > "$WORKDIR_COMM/uses_community.py" << 'USESEOF'
from talon import actions

def do_something():
    actions.user.community_test_action()
USESEOF

run_test pass "tpack generates with community dep" tpack --yes "$WORKDIR_COMM"
assert_file_contains "manifest detects community dependency" "$WORKDIR_COMM/manifest.json" '"community"'
assert_file_contains "manifest has community github url" "$WORKDIR_COMM/manifest.json" 'talonhub/community'
# Community deps should not have min_version
run_test pass "manifest has no min_version for community" bash -c "! grep -A2 '\"community\"' '$WORKDIR_COMM/manifest.json' | grep -q 'min_version'"
# deps command should show community as installed
assert_output_contains "deps shows community dep" "community" tpack deps "$WORKDIR_COMM"
assert_output_contains "deps shows community installed" "installed" tpack deps "$WORKDIR_COMM"
# info command works with community dep
run_test pass "info works with community dep" tpack info "$WORKDIR_COMM"
# README should not show vunknown for community
run_test pass "README has no vunknown for community" bash -c "! grep -q 'vunknown' '$WORKDIR_COMM/README.md'"
# Regenerate is idempotent with community dep
run_test pass "regenerate with community dep is idempotent" tpack --yes "$WORKDIR_COMM"

cleanup_workdir "$WORKDIR_COMM"
rm -rf "$FAKE_COMMUNITY"

# ============================================================
# Summary
# ============================================================

echo ""
echo "========================================"
TOTAL=$((PASS + FAIL))
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}All $TOTAL tests passed!${NC}"
else
    echo -e "${RED}$FAIL/$TOTAL tests failed${NC}"
fi
echo ""

exit $FAIL
