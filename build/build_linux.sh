#!/bin/bash
# ============================================================
#  MessageCannon Pro — Linux Build  (.deb + portable binary)
#  Run from project root:  bash build/build_linux.sh
# ============================================================
set -e
cd "$(dirname "$0")/.."

APP_NAME="messagecannon-pro"
DISPLAY_NAME="MessageCannon Pro"
VERSION="1.0.0"
ARCH="amd64"
MAINTAINER="Muhammad Faraz <farazgoal@gmail.com>"

echo "============================================================"
echo "  MessageCannon Pro — Linux Build"
echo "  Step 1: PyInstaller  →  standalone binary"
echo "  Step 2: dpkg-deb     →  .deb package"
echo "============================================================"
echo

PYTHON="${PYTHON:-python3}"
"$PYTHON" -m pip install pyinstaller pillow --quiet

# ----- Step 1: Build binary -----
echo "[1/2] Building binary with PyInstaller..."
"$PYTHON" -m PyInstaller --noconfirm MessageCannon_Pro_linux.spec

BINARY="dist/${APP_NAME}"
if [ ! -f "$BINARY" ]; then
    echo "ERROR: PyInstaller failed — '${BINARY}' not found."
    exit 1
fi
chmod +x "$BINARY"
echo "      Binary OK: ${BINARY}"
echo

# ----- Step 2: Build .deb -----
echo "[2/2] Building .deb package..."

DEB_ROOT="dist/deb_staging/${APP_NAME}_${VERSION}_${ARCH}"
rm -rf "dist/deb_staging"

# Filesystem layout inside the .deb
mkdir -p "${DEB_ROOT}/usr/local/bin"
mkdir -p "${DEB_ROOT}/usr/share/applications"
mkdir -p "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${DEB_ROOT}/usr/share/doc/${APP_NAME}"
mkdir -p "${DEB_ROOT}/DEBIAN"

# Binary
cp "$BINARY" "${DEB_ROOT}/usr/local/bin/${APP_NAME}"

# Icon (PNG)
ICON_SRC="src/assets/icons/app.png"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"
fi

# .desktop launcher
cat > "${DEB_ROOT}/usr/share/applications/${APP_NAME}.desktop" <<DESKTOP
[Desktop Entry]
Name=${DISPLAY_NAME}
Comment=Bulk WhatsApp and Email messaging for businesses
Exec=/usr/local/bin/${APP_NAME}
Icon=${APP_NAME}
Terminal=false
Type=Application
Categories=Office;Network;
Keywords=whatsapp;bulk;messaging;email;campaign;
DESKTOP

# Docs
cp README.md "${DEB_ROOT}/usr/share/doc/${APP_NAME}/"
cp LICENSE   "${DEB_ROOT}/usr/share/doc/${APP_NAME}/"
gzip -9 < docs/user_guide.md > "${DEB_ROOT}/usr/share/doc/${APP_NAME}/user_guide.md.gz" 2>/dev/null || \
    cp docs/user_guide.md "${DEB_ROOT}/usr/share/doc/${APP_NAME}/"

# DEBIAN control file
INSTALLED_SIZE=$(du -sk "${DEB_ROOT}/usr" | cut -f1)
cat > "${DEB_ROOT}/DEBIAN/control" <<CONTROL
Package: ${APP_NAME}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: ${MAINTAINER}
Description: ${DISPLAY_NAME} — Bulk messaging for businesses
 Professional WhatsApp and Email bulk messaging desktop app.
 Send personalized campaigns, track delivery rates, and manage
 contacts — all from a local GUI with no cloud dependency.
Homepage: https://muhammad-faraz-dev.netlify.app
CONTROL

# DEBIAN postinst to update icon cache & desktop DB
cat > "${DEB_ROOT}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
fi
POSTINST
chmod 755 "${DEB_ROOT}/DEBIAN/postinst"

# Build .deb
DEB_OUT="dist/${APP_NAME}_${VERSION}_${ARCH}.deb"
if command -v dpkg-deb &>/dev/null; then
    dpkg-deb --build "${DEB_ROOT}" "$DEB_OUT"
    if [ -f "$DEB_OUT" ]; then
        SIZE=$(du -sh "$DEB_OUT" | cut -f1)
        echo "      .deb OK: ${DEB_OUT}  (${SIZE})"
    fi
else
    echo "  WARNING: dpkg-deb not found. Skipping .deb creation."
    echo "  Install with: sudo apt install dpkg"
fi

rm -rf "dist/deb_staging"

echo
echo "============================================================"
echo "  Build complete. Output in dist/:"
echo "    ${APP_NAME}                         (portable binary)"
echo "    ${APP_NAME}_${VERSION}_${ARCH}.deb  (install with dpkg)"
echo "============================================================"
echo
echo "  Install .deb:"
echo "    sudo dpkg -i dist/${APP_NAME}_${VERSION}_${ARCH}.deb"
echo
echo "  Run portable:"
echo "    ./dist/${APP_NAME}"
