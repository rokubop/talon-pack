#!/usr/bin/env bash
# Run all talon-pack tests
# Usage: bash tests/test_all.sh
# Note: Self-fixes Windows CRLF line endings on first run

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Fix CRLF line endings (Windows/Git Bash) then re-exec if needed
if grep -rPl '\r$' "$SCRIPT_DIR"/*.sh >/dev/null 2>&1; then
    sed -i 's/\r$//' "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/../setup.sh 2>/dev/null || true
    exec bash "$0" "$@"
fi

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0
SUITES=()

run_suite() {
    local name="$1"
    local script="$2"
    echo ""
    echo "========================================"
    echo " $name"
    echo "========================================"
    if bash "$SCRIPT_DIR/$script"; then
        ((PASSED++)) || true
    else
        ((FAILED++)) || true
    fi
    SUITES+=("$name")
}

run_suite "Core Tests" "test_tpack.sh"
run_suite "Setup Tests" "test_setup.sh"

# Install tests need network — skip with --no-network
if [[ "${1:-}" != "--no-network" ]]; then
    run_suite "Install Tests (network)" "test_install.sh"
else
    echo ""
    echo "Skipping install tests (--no-network)"
fi

echo ""
echo "========================================"
echo " Summary"
echo "========================================"
TOTAL=$((PASSED + FAILED))
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All $TOTAL suites passed!${NC}"
else
    echo -e "${RED}$FAILED/$TOTAL suites failed${NC}"
fi
echo ""

exit $FAILED
