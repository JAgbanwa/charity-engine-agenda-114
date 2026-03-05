#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# install-ce-cli.sh — Download and install the Charity Engine CLI
#
# The CE Remote CLI docs:
#   https://www.charityengine.com/docs/Computing+with+Charity+Engine
#
# This script attempts to download ce-cli. If the direct download URL
# changes, update CE_CLI_URL below or install manually from their docs.
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

echo "Charity Engine CLI installer"
echo "============================"
echo ""

# Check if already installed
if command -v ce-cli &>/dev/null; then
  echo "ce-cli is already installed at: $(which ce-cli)"
  ce-cli --version 2>/dev/null || true
  exit 0
fi

echo "ce-cli not found. Attempting to install..."
echo ""

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Darwin)
    echo "Detected: macOS ($ARCH)"
    # Try fetching from CE's known distribution points
    # (Update this URL if CE changes their distribution)
    CE_CLI_URL="https://downloads.charityengine.com/ce-cli/ce-cli-macos"
    ;;
  Linux)
    echo "Detected: Linux ($ARCH)"
    CE_CLI_URL="https://downloads.charityengine.com/ce-cli/ce-cli-linux"
    ;;
  *)
    echo "Unsupported OS: $OS"
    echo "Please download ce-cli manually from the Charity Engine dashboard."
    exit 1
    ;;
esac

echo ""
echo "If the automatic download fails, you can install ce-cli manually:"
echo "  1. Log in to https://dashboard.charityengine.com"
echo "  2. Download the CLI tool from the dashboard"
echo "  3. Place it in $INSTALL_DIR/ce-cli"
echo "  4. Run: chmod +x $INSTALL_DIR/ce-cli"
echo ""

# Attempt download
echo "Trying: $CE_CLI_URL ..."
if curl -fsSL -o "$INSTALL_DIR/ce-cli" "$CE_CLI_URL" 2>/dev/null; then
  chmod +x "$INSTALL_DIR/ce-cli"
  echo "Installed ce-cli to $INSTALL_DIR/ce-cli"
else
  echo ""
  echo "Automatic download failed (URL may have changed)."
  echo "Please download ce-cli manually from the CE dashboard"
  echo "and place it at: $INSTALL_DIR/ce-cli"
  exit 1
fi

# Ensure PATH includes install dir
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
  echo ""
  echo "Add this to your shell profile (~/.zshrc or ~/.bashrc):"
  echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi

echo ""
echo "Done. Test with: ce-cli --help"
