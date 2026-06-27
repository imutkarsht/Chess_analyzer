#!/usr/bin/env bash
# ==============================================================================
# Chess Analyzer Pro – Linux AppImage builder
# ==============================================================================
# Prerequisites (install once on Ubuntu/Debian):
#   sudo apt-get install -y fuse libfuse2 desktop-file-utils
#   # appimagetool is downloaded automatically below if not present
#
# Usage (run from project root):
#   chmod +x installers/linux/build_appimage.sh
#   ./installers/linux/build_appimage.sh
#
# Output:
#   installers/linux/Output/ChessAnalyzerPro-2.1.0-x86_64.AppImage
# ==============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_NAME="ChessAnalyzerPro"
APP_VERSION="2.1.0"
BUNDLE_ID="com.imutkarsht.chessanalyzerpro"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DIST_DIR="${PROJECT_ROOT}/dist/${APP_NAME}"
OUTPUT_DIR="${SCRIPT_DIR}/Output"
APPDIR="${SCRIPT_DIR}/AppDir"
APPIMAGE_OUT="${OUTPUT_DIR}/${APP_NAME}-${APP_VERSION}-x86_64.AppImage"

APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
APPIMAGETOOL="${SCRIPT_DIR}/appimagetool-x86_64.AppImage"

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
echo "==> Checking prerequisites..."

if [ ! -d "${DIST_DIR}" ]; then
    echo "ERROR: PyInstaller output not found at: ${DIST_DIR}"
    echo "       Run: pyinstaller build.spec"
    exit 1
fi

# Download appimagetool if not present
if [ ! -f "${APPIMAGETOOL}" ]; then
    echo "==> Downloading appimagetool..."
    curl -sSfL "${APPIMAGETOOL_URL}" -o "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
fi

# ---------------------------------------------------------------------------
# Build AppDir structure
# ---------------------------------------------------------------------------
echo "==> Building AppDir structure..."

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib/${APP_NAME}"
mkdir -p "${OUTPUT_DIR}"

# Copy the entire PyInstaller COLLECT output into usr/lib/<APP>
echo "==> Copying application files..."
cp -r "${DIST_DIR}/." "${APPDIR}/usr/lib/${APP_NAME}/"

# Create a launcher wrapper in usr/bin so the AppRun can find the real binary
cat > "${APPDIR}/usr/bin/${APP_NAME}" << 'LAUNCHER'
#!/usr/bin/env bash
# Launcher that sets up the correct library paths for the AppImage environment.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_LIB="$(cd "${SELF_DIR}/../lib/ChessAnalyzerPro" && pwd)"
exec "${APP_LIB}/ChessAnalyzerPro" "$@"
LAUNCHER
chmod +x "${APPDIR}/usr/bin/${APP_NAME}"

# AppRun – the entry-point that the AppImage runtime calls
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/usr/bin/env bash
# AppRun: Entry point executed when the AppImage is launched.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR="${HERE}"

# Prefer the bundled Qt/Python libraries
export LD_LIBRARY_PATH="${HERE}/usr/lib/ChessAnalyzerPro:${LD_LIBRARY_PATH:-}"
export PATH="${HERE}/usr/bin:${PATH}"

exec "${HERE}/usr/lib/ChessAnalyzerPro/ChessAnalyzerPro" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

# ---------------------------------------------------------------------------
# Desktop entry
# ---------------------------------------------------------------------------
echo "==> Creating .desktop entry..."
cat > "${APPDIR}/${APP_NAME}.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Chess Analyzer Pro
Comment=Analyze your chess games with AI-powered insights
Exec=ChessAnalyzerPro
Icon=ChessAnalyzerPro
Categories=Game;BoardGame;Education;
Keywords=chess;analyzer;stockfish;AI;
StartupNotify=true
Terminal=false
DESKTOP

# ---------------------------------------------------------------------------
# App icon  (AppImage spec: PNG named <AppName>.png in AppDir root)
# ---------------------------------------------------------------------------
echo "==> Copying application icon..."
ICON_SRC="${PROJECT_ROOT}/assets/images/logo.png"
if [ -f "${ICON_SRC}" ]; then
    cp "${ICON_SRC}" "${APPDIR}/${APP_NAME}.png"
else
    echo "WARNING: logo.png not found at ${ICON_SRC}. AppImage will lack an icon."
fi

# ---------------------------------------------------------------------------
# Build the AppImage
# ---------------------------------------------------------------------------
echo "==> Running appimagetool..."
ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${APPIMAGE_OUT}"

echo ""
echo "✅  AppImage created successfully:"
echo "    ${APPIMAGE_OUT}"
echo ""
echo "    Size: $(du -sh "${APPIMAGE_OUT}" | cut -f1)"
echo ""
echo "    Make it executable and run:"
echo "    chmod +x '${APPIMAGE_OUT}' && '${APPIMAGE_OUT}'"
