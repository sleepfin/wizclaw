#!/usr/bin/env bash
#
# One-line installer for wizclaw on macOS / Linux.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/sleepfin/wizclaw/main/scripts/install-wizclaw.sh | bash
#
# The script downloads the latest wizclaw binary from GitHub Releases,
# installs it to ~/.local/bin, and adds that directory to PATH if needed.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────

REPO_OWNER="sleepfin"
REPO_NAME="wizclaw"
INSTALL_DIR="${HOME}/.local/bin"

# ── Helpers ───────────────────────────────────────────────────────────────

info()  { printf "\033[0;36m%s\033[0m\n" "$*"; }
ok()    { printf "\033[0;32m%s\033[0m\n" "$*"; }
err()   { printf "\033[0;31m%s\033[0m\n" "$*" >&2; }

detect_platform() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"

    case "$os" in
        Darwin) os="macos" ;;
        Linux)  os="linux" ;;
        *)
            err "Unsupported operating system: $os"
            exit 1
            ;;
    esac

    case "$arch" in
        x86_64)  arch="x64"   ;;
        aarch64) arch="arm64" ;;
        arm64)   arch="arm64" ;;
        *)
            err "Unsupported architecture: $arch"
            exit 1
            ;;
    esac

    echo "${os}-${arch}"
}

get_latest_download_url() {
    local platform="$1"
    local api_url="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"
    local release_json

    release_json="$(curl -fsSL -H "User-Agent: wizclaw-installer" "$api_url")" || {
        err "Failed to query GitHub releases API."
        exit 1
    }

    local pattern="wizclaw-${platform}"
    local url
    url="$(echo "$release_json" | grep -o "\"browser_download_url\": *\"[^\"]*${pattern}[^\"]*\"" | head -1 | cut -d'"' -f4)"

    if [ -z "$url" ]; then
        err "No release asset matching '${pattern}' found."
        err "Available assets:"
        echo "$release_json" | grep '"name"' | head -10 | sed 's/.*"name": *"//;s/".*/  - &/' >&2
        exit 1
    fi

    echo "$url"
}

add_to_path() {
    local dir="$1"

    # Already in PATH
    if echo "$PATH" | tr ':' '\n' | grep -qx "$dir"; then
        info "$dir is already in your PATH."
        return
    fi

    local shell_rc=""
    case "${SHELL:-}" in
        */zsh)  shell_rc="${HOME}/.zshrc" ;;
        */bash)
            if [ -f "${HOME}/.bash_profile" ]; then
                shell_rc="${HOME}/.bash_profile"
            else
                shell_rc="${HOME}/.bashrc"
            fi
            ;;
        *)
            # Try zsh first (default on macOS), then bashrc
            if [ -f "${HOME}/.zshrc" ]; then
                shell_rc="${HOME}/.zshrc"
            elif [ -f "${HOME}/.bashrc" ]; then
                shell_rc="${HOME}/.bashrc"
            fi
            ;;
    esac

    if [ -n "$shell_rc" ]; then
        local export_line="export PATH=\"${dir}:\$PATH\""
        if ! grep -qF "$dir" "$shell_rc" 2>/dev/null; then
            echo "" >> "$shell_rc"
            echo "# Added by wizclaw installer" >> "$shell_rc"
            echo "$export_line" >> "$shell_rc"
            info "Added $dir to PATH in $shell_rc"
        else
            info "$dir already referenced in $shell_rc"
        fi
    else
        info "Could not detect shell rc file. Please add $dir to your PATH manually."
    fi

    # Also update current session
    export PATH="${dir}:${PATH}"
}

# ── Main ──────────────────────────────────────────────────────────────────

echo ""
info "=== wizclaw installer ==="
echo ""

platform="$(detect_platform)"
info "Detected platform: ${platform}"

download_url="$(get_latest_download_url "$platform")"
info "Downloading from: ${download_url}"

mkdir -p "$INSTALL_DIR"
dest="${INSTALL_DIR}/wizclaw"

curl -fsSL -o "$dest" "$download_url" || {
    err "Download failed."
    exit 1
}

chmod +x "$dest"

# macOS: remove quarantine attribute to avoid Gatekeeper prompt
if [ "$(uname -s)" = "Darwin" ]; then
    xattr -d com.apple.quarantine "$dest" 2>/dev/null || true
fi

ok "Installed to: ${dest}"

add_to_path "$INSTALL_DIR"

echo ""
ok "Installation complete!"
echo ""
echo "Usage:"
echo "  wizclaw            # first run will guide you through setup"
echo "  wizclaw config     # re-configure"
echo "  wizclaw version    # show version"
echo ""
echo "You may need to restart your terminal for PATH changes to take effect."
echo ""
