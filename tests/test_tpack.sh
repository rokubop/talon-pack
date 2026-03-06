#!/usr/bin/env bash
# Integration tests for talon-pack
# Run: bash tests/test_tpack.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FIXTURE_DIR="$SCRIPT_DIR/fixtures/sample-package"
if [[ -z "${PYTHON:-}" ]]; then
    if python3 --version &>/dev/null 2>&1; then PYTHON=python3
    elif python --version &>/dev/null 2>&1; then PYTHON=python
    else echo "Python not found"; exit 1; fi
fi
TPACK_SCRIPT="$TPACK_DIR/tpack.py"

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

# Create a fresh working copy of the fixture
setup_workdir() {
    local workdir
    workdir="$(mktemp -d)"
    cp -r "$FIXTURE_DIR/"* "$workdir/"
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
assert_file_contains "manifest detects sample_action" "$WORKDIR/manifest.json" 'sample_action'
assert_file_contains "manifest detects sample_setting" "$WORKDIR/manifest.json" 'sample_setting'
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
run_test pass "tpack pip add succeeds" tpack pip "vgamepad>=1.0.0" "$WORKDIR"
assert_file_contains "pip dep added to manifest" "$WORKDIR/manifest.json" '"vgamepad"'
assert_file_contains "pip dep has version" "$WORKDIR/manifest.json" '>=1.0.0'

run_test pass "tpack pip list succeeds" tpack pip list "$WORKDIR"
assert_output_contains "pip list shows package" "vgamepad" tpack pip list "$WORKDIR"

run_test pass "tpack pip remove succeeds" tpack pip remove vgamepad "$WORKDIR"
# After removing the only pip dep, pipDependencies key should be gone
run_test pass "pip dep removed from manifest" bash -c "! grep -q 'vgamepad' '$WORKDIR/manifest.json'"

# --- Generate Individual ---
echo ""
echo "generate individual:"
run_test pass "generate manifest succeeds" tpack generate manifest "$WORKDIR"
run_test pass "generate version succeeds" tpack generate version "$WORKDIR"
run_test pass "generate readme succeeds" tpack generate readme "$WORKDIR"
run_test pass "generate install-block succeeds" tpack generate install-block "$WORKDIR"

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

# --- Skip flags ---
echo ""
echo "skip flags:"
run_test pass "--no-manifest flag works" tpack --no-manifest --dry-run "$WORKDIR"
run_test pass "--no-version flag works" tpack --no-version --dry-run "$WORKDIR"
run_test pass "--no-readme flag works" tpack --no-readme --dry-run "$WORKDIR"

# --- Error Cases ---
echo ""
echo "error cases:"
run_test fail "generate unknown type fails" tpack generate badtype "$WORKDIR"

cleanup_workdir "$WORKDIR"

# --- Setup Script (bash) ---
echo ""
echo "setup.sh:"
run_test pass "setup.sh passes bash -n syntax check" bash -n "$TPACK_DIR/setup.sh"

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
