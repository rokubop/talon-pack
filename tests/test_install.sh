#!/usr/bin/env bash
# Integration test for tpack install with a real GitHub repo
# This test clones from GitHub so it requires network access.
# Run: bash tests/test_install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -z "${PYTHON:-}" ]]; then
    if python3 --version &>/dev/null 2>&1; then PYTHON=python3
    elif python --version &>/dev/null 2>&1; then PYTHON=python
    else echo "Python not found"; exit 1; fi
fi
TPACK_SCRIPT="$TPACK_DIR/tpack.py"

GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

PASS=0
FAIL=0

tpack() {
    "$PYTHON" "$TPACK_SCRIPT" "$@"
}

run_test() {
    local expect="$1"
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

assert_dir_exists() {
    local desc="$1"
    local dir="$2"
    if [[ -d "$dir" ]]; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc (dir not found: $dir)"
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
        echo -e "    ${DIM}output: $(echo "$output" | head -3)${NC}"
        ((FAIL++)) || true
    fi
}

echo ""
echo "Talon Pack Install Tests (network required)"
echo "========================================"
echo ""

# Set up a fake talon directory structure so tpack can find the user dir.
# find_talon_user_dir walks up from SCRIPT_DIR looking for a parent named
# "talon" or ".talon" with a "user" subdir and talon.log.
# So we need: <tmp>/talon/talon-pack/... and <tmp>/talon/user/ and <tmp>/talon/talon.log
FAKE_ROOT="$(mktemp -d)"
FAKE_TALON="$FAKE_ROOT/talon"
FAKE_USER="$FAKE_TALON/user"
mkdir -p "$FAKE_USER"
touch "$FAKE_TALON/talon.log"

# Copy talon-pack into the fake talon dir so SCRIPT_DIR resolves inside "talon/"
cp -r "$TPACK_DIR" "$FAKE_TALON/talon-pack"
FAKE_TPACK_SCRIPT="$FAKE_TALON/talon-pack/tpack.py"

fake_tpack() {
    "$PYTHON" "$FAKE_TPACK_SCRIPT" "$@"
}

# --- Install dry-run (URL) ---
echo "install --dry-run (URL):"
assert_output_contains \
    "dry-run shows git clone command" \
    "git clone" \
    fake_tpack install --dry-run "https://github.com/rokubop/talon-mouse-rig"

assert_output_contains \
    "dry-run shows repo name" \
    "talon-mouse-rig" \
    fake_tpack install --dry-run "https://github.com/rokubop/talon-mouse-rig"

# --- Actual install ---
echo ""
echo "install (actual clone):"

# Run install with --yes to skip confirmation
fake_tpack install --yes "https://github.com/rokubop/talon-mouse-rig" > /dev/null 2>&1 || true

assert_dir_exists "talon-mouse-rig cloned" "$FAKE_USER/talon-mouse-rig"
assert_file_exists "cloned repo has manifest.json" "$FAKE_USER/talon-mouse-rig/manifest.json"

# --- Install again (already exists) ---
echo ""
echo "install (already exists):"
assert_output_contains \
    "reports already exists" \
    "already exists" \
    fake_tpack install --yes "https://github.com/rokubop/talon-mouse-rig"

# --- Info on cloned package ---
echo ""
echo "info on cloned package:"
run_test pass "tpack info on cloned package" fake_tpack info "$FAKE_USER/talon-mouse-rig"
assert_output_contains \
    "info shows package name" \
    "talon-mouse-rig" \
    fake_tpack info "$FAKE_USER/talon-mouse-rig"

# --- Outdated (network) ---
echo ""
echo "outdated:"
run_test pass "tpack outdated on cloned package" fake_tpack outdated "$FAKE_USER/talon-mouse-rig"

# --- Cleanup ---
rm -rf "$FAKE_ROOT"

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
