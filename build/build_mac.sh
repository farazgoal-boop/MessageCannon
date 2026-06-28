#!/bin/bash
# ============================================================
#  MessageCannon Pro — macOS Build  (.app + .dmg)
#  Run from project root:  bash build/build_mac.sh
# ============================================================
set -e
cd "$(dirname "$0")/.."

APP_NAME="MessageCannon Pro"
DMG_NAME="MessageCannonPro-Mac"
VERSION="1.0.0"

echo "============================================================"
echo "  MessageCannon Pro — macOS Build"
echo "  Step 1: PyInstaller  →  .app bundle"
echo "  Step 2: hdiutil      →  .dmg"
echo "============================================================"
echo

# ----- Python / venv -----
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m pip install pyinstaller pillow --quiet

# ----- Step 1: Build .app -----
echo "[1/2] Building .app bundle..."
"$PYTHON" -m PyInstaller --noconfirm MessageCannon_Pro_mac.spec

APP_BUNDLE="dist/${APP_NAME}.app"
if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: PyInstaller failed — '${APP_BUNDLE}' not found."
    exit 1
fi
echo "      .app OK: ${APP_BUNDLE}"
echo

# ----- Step 2: Create .dmg -----
echo "[2/2] Creating .dmg..."
DMG_OUT="dist/${DMG_NAME}-${VERSION}.dmg"
STAGING="dist/dmg_staging"

rm -rf "$STAGING" "$DMG_OUT"
mkdir -p "$STAGING"
cp -r "$APP_BUNDLE" "$STAGING/"

# Symlink Applications so the DMG shows a drag-to-install UX
ln -s /Applications "$STAGING/Applications"

hdiutil create \
    -volname "${APP_NAME} ${VERSION}" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG_OUT"

rm -rf "$STAGING"

if [ -f "$DMG_OUT" ]; then
    SIZE=$(du -sh "$DMG_OUT" | cut -f1)
    echo "      .dmg OK: ${DMG_OUT}  (${SIZE})"
else
    echo "ERROR: .dmg creation failed."
    exit 1
fi

echo
echo "============================================================"
echo "  Build complete. Output:"
echo "    dist/${APP_NAME}.app        (run directly)"
echo "    dist/${DMG_NAME}-${VERSION}.dmg  (distribute to users)"
echo "============================================================"
echo
echo "  To notarize (Apple distribution):"
echo "    xcrun notarytool submit dist/${DMG_NAME}-${VERSION}.dmg \\"
echo "      --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID --wait"
