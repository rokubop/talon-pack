#!/usr/bin/env bash
# Talon Pack Setup Script
# Detects OS/shell, adds the tpack alias (and optional tab completion),
# shows a diff of changes, and sources the config file.

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}$*${NC}"; }
success() { echo -e "${GREEN}$*${NC}"; }
warn()  { echo -e "${YELLOW}$*${NC}"; }
error() { echo -e "${RED}$*${NC}" >&2; }

# --- Detect OS / environment ---
detect_os() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        echo "mac"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
    elif [[ "$(uname -s)" == "Linux" ]]; then
        echo "linux"
    elif [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]]; then
        echo "gitbash"
    else
        echo "unknown"
    fi
}

# --- Detect shell ---
detect_shell() {
    local shell_name
    shell_name="$(basename "${SHELL:-unknown}")"
    case "$shell_name" in
        zsh)  echo "zsh" ;;
        bash) echo "bash" ;;
        *)    echo "unknown" ;;
    esac
}

# --- Find the script's own directory ---
get_script_dir() {
    local dir
    dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "$dir"
}

# --- Build the alias command ---
build_alias() {
    local os="$1"
    local script_dir="$2"

    case "$os" in
        mac)
            local python="/Applications/Talon.app/Contents/Resources/python/bin/python3"
            local tpack="$HOME/.talon/talon-pack/tpack.py"
            if [[ ! -f "$python" ]]; then
                python="python3"
                warn "Talon Python not found at default Mac path, falling back to system python3"
            fi
            echo "alias tpack=\"\\\"$python\\\" \\\"$tpack\\\"\""
            ;;
        linux)
            local python="$HOME/.talon/bin/python3"
            local tpack="$HOME/.talon/talon-pack/tpack.py"
            if [[ ! -f "$python" ]]; then
                python="python3"
                warn "Talon Python not found at ~/.talon/bin/python3, falling back to system python3"
            fi
            echo "alias tpack=\"\\\"$python\\\" \\\"$tpack\\\"\""
            ;;
        wsl)
            local python="/mnt/c/Program Files/Talon/python.exe"
            # Convert script_dir to Windows path for the python arg
            local win_user
            win_user="$(cmd.exe /C "echo %USERNAME%" 2>/dev/null | tr -d '\r' || true)"
            if [[ -z "$win_user" ]]; then
                win_user="$(basename "$(wslpath "$(wslvar USERPROFILE 2>/dev/null || true)")" 2>/dev/null || true)"
            fi
            local tpack="C:/Users/$win_user/AppData/Roaming/talon/talon-pack/tpack.py"
            if [[ ! -f "$python" ]]; then
                warn "Talon python.exe not found at '$python'"
                warn "You may need to adjust the alias path manually"
            fi
            echo "alias tpack=\"'$python' '$tpack'\""
            ;;
        gitbash)
            local python="'/c/Program Files/Talon/python.exe'"
            local tpack="~/AppData/Roaming/talon/talon-pack/tpack.py"
            echo "alias tpack=\"$python $tpack\""
            ;;
        *)
            error "Could not detect OS. Please set up the alias manually (see README.md)."
            exit 1
            ;;
    esac
}

# --- Shell config file ---
get_rc_file() {
    local shell="$1"
    case "$shell" in
        zsh)  echo "$HOME/.zshrc" ;;
        bash) echo "$HOME/.bashrc" ;;
        *)
            error "Unsupported shell: $shell. Please set up the alias manually (see README.md)."
            exit 1
            ;;
    esac
}

# --- Tab completion snippets ---
zsh_completion() {
    cat <<'COMPLETION'

# --- tpack tab completion ---
_tpack() {
  local -a commands=(
    'info' 'patch' 'minor' 'major' 'version'
    'install' 'update' 'outdated' 'sync'
    'pip' 'generate' 'help'
  )
  local -a generate_types=(
    'manifest' 'version' 'readme' 'shields'
    'duplicate-check' 'install-block'
  )
  local -a pip_cmds=('remove' 'list')
  local -a flags=(
    '--dry-run' '--yes' '-y' '-v' '--verbose'
    '--no-manifest' '--no-version' '--no-readme'
    '--no-shields' '--no-duplicate-check' '--help'
  )

  if (( CURRENT == 2 )); then
    _describe 'command' commands
    _describe 'flag' flags
  elif (( CURRENT == 3 )); then
    case ${words[2]} in
      generate) _describe 'type' generate_types ;;
      pip) _describe 'pip command' pip_cmds ;;
    esac
  fi
}
compdef _tpack tpack
# --- end tpack tab completion ---
COMPLETION
}

bash_completion() {
    cat <<'COMPLETION'

# --- tpack tab completion ---
_tpack() {
  local cur prev commands generate_types pip_cmds flags
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  commands="info patch minor major version install update outdated sync pip generate help"
  generate_types="manifest version readme shields duplicate-check install-block"
  pip_cmds="remove list"
  flags="--dry-run --yes -y -v --verbose --no-manifest --no-version --no-readme --no-shields --no-duplicate-check --help"

  if (( COMP_CWORD == 1 )); then
    COMPREPLY=($(compgen -W "$commands $flags" -- "$cur"))
  elif (( COMP_CWORD == 2 )); then
    case "$prev" in
      generate) COMPREPLY=($(compgen -W "$generate_types" -- "$cur")) ;;
      pip) COMPREPLY=($(compgen -W "$pip_cmds" -- "$cur")) ;;
    esac
  fi
}
complete -F _tpack tpack
# --- end tpack tab completion ---
COMPLETION
}

# --- Confirm prompt ---
confirm() {
    local prompt="$1"
    local response
    echo -en "${BOLD}${prompt} [Y/n] ${NC}"
    read -r response
    case "$response" in
        [nN][oO]|[nN]) return 1 ;;
        *) return 0 ;;
    esac
}

# --- Main ---
main() {
    echo ""
    info "Talon Pack Setup"
    echo "────────────────────────────────────"
    echo ""

    local os shell rc_file alias_cmd script_dir
    os="$(detect_os)"
    shell="$(detect_shell)"
    script_dir="$(get_script_dir)"
    rc_file="$(get_rc_file "$shell")"
    alias_cmd="$(build_alias "$os" "$script_dir")"

    info "Detected: OS=$os  Shell=$shell"
    info "Config:   $rc_file"
    echo ""

    # Check what already exists
    local has_alias=false
    local has_completion=false
    if [[ -f "$rc_file" ]]; then
        grep -q 'alias tpack=' "$rc_file" 2>/dev/null && has_alias=true
        grep -q '# --- tpack tab completion ---' "$rc_file" 2>/dev/null && has_completion=true
    fi

    if $has_alias && $has_completion; then
        success "Already set up! Alias and tab completion found in $rc_file"
        echo ""
        return 0
    fi

    # Create rc file if it doesn't exist
    if [[ ! -f "$rc_file" ]]; then
        touch "$rc_file"
    fi

    # Save a copy for diff
    local backup
    backup="$(mktemp)"
    cp "$rc_file" "$backup"

    # --- Alias ---
    if $has_alias; then
        success "Alias already exists in $rc_file (skipping)"
        echo ""
    else
        echo -e "The following alias will be added to ${BOLD}$rc_file${NC}:"
        echo ""
        echo -e "  ${GREEN}$alias_cmd${NC}"
        echo ""

        if ! confirm "Add alias?"; then
            info "Alias skipped."
        else
            echo "" >> "$rc_file"
            echo "# --- tpack alias ---" >> "$rc_file"
            echo "$alias_cmd" >> "$rc_file"
            echo "# --- end tpack alias ---" >> "$rc_file"
            success "Alias added."
        fi
        echo ""
    fi

    # --- Tab completion ---
    if $has_completion; then
        success "Tab completion already exists in $rc_file (skipping)"
        echo ""
    else
        if confirm "Add tab completion?"; then
            if [[ "$shell" == "zsh" ]]; then
                zsh_completion >> "$rc_file"
            else
                bash_completion >> "$rc_file"
            fi
            success "Tab completion added."
        fi
        echo ""
    fi

    # --- Show diff ---
    if diff -q "$backup" "$rc_file" > /dev/null 2>&1; then
        info "No changes were made."
        rm "$backup"
    else
        echo ""
        info "Changes made to $rc_file:"
        echo "────────────────────────────────────"
        diff --color=always "$backup" "$rc_file" || true
        echo "────────────────────────────────────"
        rm "$backup"

        echo ""
        info "Run this to activate:"
        echo ""
        echo -e "  ${BOLD}source $rc_file${NC}"
        echo ""
    fi

    echo ""
    success "Setup complete! Try: tpack --help"
    echo ""
}

main "$@"
