#!/usr/bin/env bash
# ==============================================================================
# Chess Analyzer Pro – macOS DMG builder using create-dmg
# ==============================================================================
# Prerequisites (install once):
#   brew install create-dmg
#
# Usage:
#   chmod +x build_dmg.sh
#   ./build_dmg.sh
#
# Output:
#   installers/mac/Output/ChessAnalyzerPro-2.1.0-macOS.dmg
# ==============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_NAME="Chess Analyzer Pro"
APP_VERSION="2.1.0"
BUNDLE_NAME="ChessAnalyzerPro"

# Paths (relative to project root — run this script from the project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

APP_BUNDLE="${PROJECT_ROOT}/dist/${BUNDLE_NAME}.app"
DMG_OUTPUT_DIR="${SCRIPT_DIR}/Output"
DMG_FILENAME="${BUNDLE_NAME}-${APP_VERSION}-macOS.dmg"
DMG_PATH="${DMG_OUTPUT_DIR}/${DMG_FILENAME}"

BACKGROUND_IMAGE="${PROJECT_ROOT}/installers/mac/dmg_background.png"
ICON_FILE="${PROJECT_ROOT}/assets/images/logo.png"

# DMG window layout
WINDOW_WIDTH=660
WINDOW_HEIGHT=400
ICON_SIZE=128
APP_ICON_X=165
APP_ICON_Y=190
APPLICATIONS_X=495
APPLICATIONS_Y=190

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
echo "==> Checking prerequisites..."

if ! command -v create-dmg &>/dev/null; then
    echo "ERROR: create-dmg not found. Install it with: brew install create-dmg"
    exit 1
fi

if [ ! -d "${APP_BUNDLE}" ]; then
    echo "ERROR: .app bundle not found at: ${APP_BUNDLE}"
    echo "       Run PyInstaller first: pyinstaller build.spec"
    exit 1
fi

# ---------------------------------------------------------------------------
# Prepare output directory
# ---------------------------------------------------------------------------
mkdir -p "${DMG_OUTPUT_DIR}"

# Remove stale DMG if it exists (create-dmg will error otherwise)
if [ -f "${DMG_PATH}" ]; then
    echo "==> Removing existing DMG: ${DMG_PATH}"
    rm -f "${DMG_PATH}"
fi

# ---------------------------------------------------------------------------
# Code-sign the .app (optional but recommended)
# Uncomment and set DEVELOPER_ID if you have an Apple Developer certificate.
# ---------------------------------------------------------------------------
# DEVELOPER_ID="Developer ID Application: Your Name (XXXXXXXXXX)"
# echo "==> Code-signing ${APP_BUNDLE}..."
# codesign --deep --force --verify --verbose \
#     --sign "${DEVELOPER_ID}" \
#     --options runtime \
#     "${APP_BUNDLE}"

# ---------------------------------------------------------------------------
# Build DMG
# ---------------------------------------------------------------------------
echo "==> Building DMG: ${DMG_FILENAME}"

CREATE_DMG_ARGS=(
    --volname "${APP_NAME} ${APP_VERSION}"
    --window-pos 200 120
    --window-size "${WINDOW_WIDTH}" "${WINDOW_HEIGHT}"
    --icon-size "${ICON_SIZE}"
    --icon "${BUNDLE_NAME}.app" "${APP_ICON_X}" "${APP_ICON_Y}"
    --hide-extension "${BUNDLE_NAME}.app"
    --app-drop-link "${APPLICATIONS_X}" "${APPLICATIONS_Y}"
    --no-internet-enable
)

# Add background image if it exists
if [ -f "${BACKGROUND_IMAGE}" ]; then
    CREATE_DMG_ARGS+=(--background "${BACKGROUND_IMAGE}")
    echo "   Using background: ${BACKGROUND_IMAGE}"
else
    echo "   NOTE: No background image found at ${BACKGROUND_IMAGE} — DMG will use plain white."
    echo "         Create a 660×400 PNG there for a polished look."
fi

# Add volume icon if a .icns file exists
ICNS_FILE="${PROJECT_ROOT}/assets/images/logo.icns"
if [ -f "${ICNS_FILE}" ]; then
    CREATE_DMG_ARGS+=(--volicon "${ICNS_FILE}")
fi

create-dmg "${CREATE_DMG_ARGS[@]}" \
    "${DMG_PATH}" \
    "${APP_BUNDLE}"

# ---------------------------------------------------------------------------
# Notarize (optional — requires Apple Developer account)
# Uncomment the block below if you want notarization for Gatekeeper.
# ---------------------------------------------------------------------------
# APPLE_ID="your@email.com"
# TEAM_ID="XXXXXXXXXX"
# APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"   # generated in appleid.apple.com
#
# echo "==> Submitting DMG for notarization..."
# xcrun notarytool submit "${DMG_PATH}" \
#     --apple-id "${APPLE_ID}" \
#     --team-id "${TEAM_ID}" \
#     --password "${APP_SPECIFIC_PASSWORD}" \
#     --wait
#
# echo "==> Stapling notarization ticket..."
# xcrun stapler staple "${DMG_PATH}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "✅  DMG created successfully:"
echo "    ${DMG_PATH}"
echo ""
echo "    Size: $(du -sh "${DMG_PATH}" | cut -f1)"
