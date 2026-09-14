#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPOSITORY_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="${1:-0.1.0}"
PACKAGE_NAME="Codex-Bridge-macOS-v${VERSION}"
OUTPUT_DIR="$REPOSITORY_DIR/dist"
STAGING_DIR="$(mktemp -d)"

cleanup() {
    rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$STAGING_DIR/$PACKAGE_NAME/macos" "$OUTPUT_DIR"
cp "$REPOSITORY_DIR/tools/codex_bridge.py" "$STAGING_DIR/$PACKAGE_NAME/codex_bridge.py"
cp "$REPOSITORY_DIR/tools/requirements-codex-bridge.txt" \
    "$STAGING_DIR/$PACKAGE_NAME/requirements-codex-bridge.txt"
cp "$SCRIPT_DIR/README.txt" "$STAGING_DIR/$PACKAGE_NAME/README.txt"
cp "$SCRIPT_DIR/macos/"*.command "$STAGING_DIR/$PACKAGE_NAME/macos/"
chmod +x "$STAGING_DIR/$PACKAGE_NAME/macos/"*.command

rm -f "$OUTPUT_DIR/$PACKAGE_NAME.zip"
(
    cd "$STAGING_DIR"
    zip -q -r -X "$OUTPUT_DIR/$PACKAGE_NAME.zip" "$PACKAGE_NAME"
)

echo "$OUTPUT_DIR/$PACKAGE_NAME.zip"
