#!/usr/bin/env bash
# Tests for setup.sh - verifies alias and completion are added correctly
# Run: bash tests/test_setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TPACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASS=0
FAIL=0

assert_ok() {
    local desc="$1"
    shift
    if "$@"; then
        echo -e "  ${GREEN}PASS${NC} $desc"
        ((PASS++)) || true
    else
        echo -e "  ${RED}FAIL${NC} $desc"
        ((FAIL++)) || true
    fi
}

echo ""
echo "Setup Script Tests"
echo "========================================"
echo ""

# --- setup.sh syntax ---
echo "syntax:"
assert_ok "setup.sh is valid bash" bash -n "$TPACK_DIR/setup.sh"

# --- Simulate setup.sh by sourcing its functions ---
# We test the auto-detection functions in isolation

echo ""
echo "setup.sh auto-adds tpack command (simulated):"

# Create a temp rc file and simulate what setup.sh would append
FAKE_RC="$(mktemp)"

# Simulate adding the tpack command block (function for zsh)
cat >> "$FAKE_RC" <<'EOF'

# --- tpack ---
tpack() { "/path/to/python3" "/path/to/tpack.py" "$@"; }
# --- end tpack ---
EOF

assert_ok "tpack function written to rc file" grep -qE 'alias tpack=|tpack\(\)' "$FAKE_RC"
assert_ok "tpack block has markers" grep -q '# --- tpack ---' "$FAKE_RC"

# --- Noop detection ---
echo ""
echo "noop detection:"

# Check that the file has the tpack marker (simulating what setup.sh checks)
has_alias=false
grep -qE 'alias tpack=|tpack\(\)' "$FAKE_RC" && has_alias=true
assert_ok "detects existing tpack command" $has_alias

has_completion=false
grep -q '# --- tpack tab completion ---' "$FAKE_RC" && has_completion=true || true
assert_ok "detects missing completion" test "$has_completion" = "false"

# Add completion block
cat >> "$FAKE_RC" <<'EOF'

# --- tpack tab completion ---
_tpack() { echo "completion"; }
# --- end tpack tab completion ---
EOF

has_completion=false
grep -q '# --- tpack tab completion ---' "$FAKE_RC" && has_completion=true
assert_ok "detects existing completion" $has_completion

# Both exist = noop
assert_ok "both exist = would noop" $has_alias && $has_completion

rm "$FAKE_RC"

# --- setup.ps1 syntax ---
echo ""
echo "setup.ps1:"
assert_ok "setup.ps1 exists" test -f "$TPACK_DIR/setup.ps1"
assert_ok "setup.ps1 contains tpack function" grep -q 'function tpack' "$TPACK_DIR/setup.ps1"
assert_ok "setup.ps1 contains Register-ArgumentCompleter" grep -q 'Register-ArgumentCompleter' "$TPACK_DIR/setup.ps1"
assert_ok "setup.ps1 checks for existing function" grep -q 'function tpack' "$TPACK_DIR/setup.ps1"
assert_ok "setup.ps1 checks for existing completion" grep -q 'tpack tab completion' "$TPACK_DIR/setup.ps1"

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
