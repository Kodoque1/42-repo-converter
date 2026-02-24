#!/usr/bin/env bash
# setup_42.sh – 42 School compliance toolchain setup
#
# Usage:
#   source setup_42.sh          # loads 42clone into your current shell
#   bash setup_42.sh            # installs the pre-push hook in the current repo
#
# Functions exported when sourced:
#   42clone  <vogsphere_url> <github_url> [branch] [project_name]
#   install_42_hook  [repo_dir]

# Resolve the directory that contains this script regardless of how it is
# invoked (sourced or executed directly).
if [[ "${BASH_SOURCE[0]}" != "" ]]; then
    _SETUP_42_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    _SETUP_42_DIR="$(pwd)"
fi

# ---------------------------------------------------------------------------
# 42clone – clone a Vogsphere repo then import source files from GitHub
#           without overwriting the Vogsphere Git history.
# ---------------------------------------------------------------------------

42clone() {
    if [[ $# -lt 2 ]]; then
        echo "Usage: 42clone <vogsphere_url> <github_url> [branch] [project_name]" >&2
        return 1
    fi

    local vogsphere_url="$1"
    local github_url="$2"
    local branch="${3:-main}"
    local project_name="${4:-}"
    local dest_dir

    dest_dir="$(basename "$vogsphere_url" .git)"

    # 1. Clone the Vogsphere repository (this is the destination whose history
    #    we want to preserve).  --recurse-submodules ensures any nested
    #    submodules are also initialised and checked out.
    echo "[42clone] Cloning Vogsphere repo: $vogsphere_url"
    git clone --recurse-submodules "$vogsphere_url" "$dest_dir" || return 1

    pushd "$dest_dir" > /dev/null || return 1

    # 2. Add a *temporary* remote pointing to the GitHub source.
    git remote add _tmp_github "$github_url"

    # 3. Fetch the desired branch from GitHub (objects only, no merge).
    echo "[42clone] Fetching content from GitHub: $github_url (branch: $branch)"
    if ! git fetch _tmp_github "$branch"; then
        echo "[42clone] ERROR: could not fetch '$branch' from $github_url" >&2
        git remote remove _tmp_github
        popd > /dev/null
        return 1
    fi

    # 4. Check out the *files* from the GitHub branch into the working tree.
    #    This copies file content without importing GitHub's commit history,
    #    so the Vogsphere history remains intact.
    if ! git checkout "_tmp_github/$branch" -- .; then
        echo "[42clone] ERROR: could not check out files from _tmp_github/$branch" >&2
        git remote remove _tmp_github
        popd > /dev/null
        return 1
    fi

    # 5. Remove the temporary remote – it is no longer needed.
    git remote remove _tmp_github

    # 6. Set the 42 project name so that check_42.py knows which project this is.
    if [[ -n "$project_name" ]]; then
        git config project.name "$project_name"
        echo "[42clone] Set git config project.name = $project_name"
    fi

    echo "[42clone] Done. Review the staged changes, then commit and push."
    popd > /dev/null

    # 7. Install the pre-push hook so check_42.py runs automatically on push.
    install_42_hook "$dest_dir"
}

# ---------------------------------------------------------------------------
# install_42_hook – install a pre-push hook that runs check_42.py
# ---------------------------------------------------------------------------

install_42_hook() {
    local repo_dir="${1:-.}"
    local hooks_dir="$repo_dir/.git/hooks"
    local hook_path="$hooks_dir/pre-push"

    if [[ ! -d "$repo_dir/.git" ]]; then
        echo "[install_42_hook] ERROR: '$repo_dir' is not a Git repository." >&2
        return 1
    fi

    mkdir -p "$hooks_dir"

    # Prefer the check_42.py that lives next to setup_42.sh; fall back to the
    # repository root at hook execution time.
    local check_script_install_path="$_SETUP_42_DIR/check_42.py"

    cat > "$hook_path" << EOF
#!/usr/bin/env bash
# pre-push hook installed by setup_42.sh

# 1. Try the path recorded at install time.
CHECK_SCRIPT="$check_script_install_path"

# 2. Fall back to the repository root (useful when check_42.py is committed).
if [[ ! -f "\$CHECK_SCRIPT" ]]; then
    CHECK_SCRIPT="\$(git rev-parse --show-toplevel)/check_42.py"
fi

if [[ -f "\$CHECK_SCRIPT" ]]; then
    python3 "\$CHECK_SCRIPT"
    exit \$?
fi

echo "[pre-push] WARNING: check_42.py not found – compliance check skipped."
exit 0
EOF

    chmod +x "$hook_path"
    echo "[install_42_hook] Pre-push hook installed at $hook_path"
}

# ---------------------------------------------------------------------------
# Main – when executed directly (not sourced) install the hook and print help
# ---------------------------------------------------------------------------

_setup_42_main() {
    echo "=== 42 compliance toolchain setup ==="

    if [[ -d ".git" ]]; then
        install_42_hook "."
    else
        echo "[setup] Not inside a Git repository – skipping hook installation."
        echo "        Run 'install_42_hook <repo_dir>' manually after cloning."
    fi

    # Persist 42clone into ~/.zshrc so it is available in every new shell.
    local zshrc="$HOME/.zshrc"
    local marker="# added by setup_42.sh"
    local source_line="source \"$_SETUP_42_DIR/setup_42.sh\""
    if grep -qF "$marker" "$zshrc" 2>/dev/null; then
        echo "[setup] 42clone already present in $zshrc"
    else
        if [[ ! -f "$zshrc" ]]; then
            touch "$zshrc"
            echo "[setup] Created $zshrc"
        fi
        printf '\n# 42 School toolchain %s\n%s\n' "$marker" "$source_line" >> "$zshrc"
        echo "[setup] Added 42clone to $zshrc"
        echo "        Restart your terminal or run: source \"$zshrc\""
    fi

    echo ""
    echo "To use 42clone in your current shell:"
    echo "  source \"$_SETUP_42_DIR/setup_42.sh\""
}

# Run _setup_42_main only when this script is *executed*, not *sourced*.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    _setup_42_main
fi
