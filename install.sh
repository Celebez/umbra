#!/usr/bin/env bash
# Umbra installer — one-liner for users:
#   curl -fsSL https://raw.githubusercontent.com/Celebez/umbra/main/install.sh | bash
#
# Installs two pieces, both from Celebez/umbra (fully self-contained, no
# dependency on any upstream repo):
#   1. the umbra-engine binary (built in-repo from engine/) into ~/.local/bin
#   2. the `umbra` Python package (pip, --user / venv friendly)
#
# The engine binds 127.0.0.1 by default — it is NOT exposed on a public IP/port.
set -euo pipefail

REPO="Celebez/umbra"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

err() { echo "error: $*" >&2; exit 1; }

OS="$(uname -s)"; ARCH="$(uname -m)"
case "$OS" in
  Linux)  OS_PART="linux" ;;
  Darwin) OS_PART="macos" ;;
  *) err "unsupported OS: $OS" ;;
esac
case "$ARCH" in
  x86_64|amd64) ARCH_PART="x86_64" ;;
  arm64|aarch64) ARCH_PART="aarch64" ;;
  *) err "unsupported arch: $ARCH" ;;
esac
ASSET="obscura-${ARCH_PART}-${OS_PART}.tar.gz"

# The engine binary is published to Celebez/umbra releases by this repo's own
# release workflow (built from engine/ in this repo).
latest_tag() {
  curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
    | grep -m1 '"tag_name"' | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/'
}
TAG="$(latest_tag || true)"
[ -n "$TAG" ] || err "no engine release found under $REPO (tag a release, e.g. v0.1.0)"
echo "[umbra] engine: $REPO @ $TAG ($ASSET)"

URL="https://github.com/$REPO/releases/download/$TAG/$ASSET"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fSL "$URL" -o "$TMP/$ASSET"
tar xzf "$TMP/$ASSET" -C "$TMP"

mkdir -p "$INSTALL_DIR"
install -m 0755 "$TMP/obscura" "$INSTALL_DIR/umbra-engine" 2>/dev/null \
  || sudo install -m 0755 "$TMP/obscura" "$INSTALL_DIR/umbra-engine" \
  || err "could not write to $INSTALL_DIR"
ln -sf "$INSTALL_DIR/umbra-engine" "$INSTALL_DIR/obscura" 2>/dev/null || true
echo "[umbra] engine installed: $INSTALL_DIR/umbra-engine"

echo "[umbra] installing python package..."
python3 -m pip install --user --upgrade "git+https://github.com/$REPO.git" 2>/dev/null \
  || python3 -m pip install --upgrade "git+https://github.com/$REPO.git" \
  || err "pip install failed (try inside a venv)"

echo
echo "[umbra] done. Usage (local loopback, not public):"
echo "  umbra fetch https://example.com --dump markdown"
echo "  umbra serve --port 9222     # binds 127.0.0.1:9222"
echo "  umbra identities new --name mybot"
