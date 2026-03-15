#!/bin/bash
# Build Linux .deb package for FadCat
# Works on BOTH x86_64 (amd64) and ARM64 (arm64) architectures
# Bundles ADB for both architectures in a single package

set -e
cd "$(dirname "$0")/../.."
PROJECT_ROOT="$(pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  FadCat Linux .deb Package Builder${NC}"
echo -e "${BLUE}  Supports: x86_64 + ARM64${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Extract version from src/version.py
VERSION=$(python3 -c "from src.version import __version__; print(__version__)" 2>/dev/null || echo "1.0.0")
AUTHOR=$(python3 -c "from src.version import __author__; print(__author__)" 2>/dev/null || echo "Faded")
EMAIL="${AUTHOR}@fadseclab.com"

echo -e "${GREEN}✓ Version: ${VERSION}"
echo ""

# Build with PyInstaller (use linuxbrew Python for proper fastmcp bundling)
echo -e "${YELLOW}🔨 Building FadCat with PyInstaller...${NC}"
if [ -f "/home/linuxbrew/.linuxbrew/bin/python3" ]; then
    # Use linuxbrew Python which has fastmcp installed
    /home/linuxbrew/.linuxbrew/bin/python3 -m PyInstaller -y build/FadCat-Linux.spec
else
    # Fallback to system PyInstaller
    pyinstaller -y build/FadCat-Linux.spec
fi

if [ ! -d "dist/fadcat" ]; then
    echo -e "${RED}✗ Build failed: dist/fadcat not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ PyInstaller build complete${NC}"
echo ""

# Create DEB structure
echo -e "${YELLOW}📦 Creating .deb package structure...${NC}"
DEB_ROOT="${PROJECT_ROOT}/build/.deb_root"
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/opt/fadcat"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps"

# Copy main application
echo "  Copying application files..."
cp -r dist/fadcat/* "$DEB_ROOT/opt/fadcat/"
chmod +x "$DEB_ROOT/opt/fadcat/fadcat"

# Bundle BOTH ADB architectures
echo "  Bundling ADB for all architectures..."
ADB_DIR="$DEB_ROOT/opt/fadcat/_internal/platform-tools"
mkdir -p "$ADB_DIR/linux_x86_64"
mkdir -p "$ADB_DIR/linux_aarch64"

# Copy x86_64 ADB
if [ -f "build/platform-tools/linux_x86_64/adb" ]; then
    cp "build/platform-tools/linux_x86_64/adb" "$ADB_DIR/linux_x86_64/"
    chmod +x "$ADB_DIR/linux_x86_64/adb"
    echo "    ✓ Added Linux x86_64 ADB"
else
    echo "    ⚠ Missing: Linux x86_64 ADB"
fi

# Copy ARM64 ADB
if [ -f "build/platform-tools/linux_aarch64/adb" ]; then
    cp "build/platform-tools/linux_aarch64/adb" "$ADB_DIR/linux_aarch64/"
    chmod +x "$ADB_DIR/linux_aarch64/adb"
    echo "    ✓ Added Linux ARM64 ADB"
else
    echo "    ⚠ Missing: Linux ARM64 ADB"
fi

# Copy wrapper script
echo "  Installing wrapper script..."
cp "build/linux/fadcat-wrapper" "$DEB_ROOT/usr/bin/fadcat"
chmod +x "$DEB_ROOT/usr/bin/fadcat"

# Calculate installed size
INSTALLED_SIZE=$(du -sk "$DEB_ROOT/opt/fadcat" | cut -f1)

# Create control file (Architecture: all)
echo "  Creating DEBIAN/control..."
cat > "$DEB_ROOT/DEBIAN/control" << EOF
Package: fadcat
Version: ${VERSION}
Architecture: all
Priority: optional
Section: utils
Maintainer: ${AUTHOR} <${EMAIL}>
Installed-Size: ${INSTALLED_SIZE}
Depends: libqt6core6, libqt6gui6, libqt6widgets6, libqt6svg6
Homepage: https://github.com/anonfaded/FadCat
Description: Advanced Android Logcat Viewer
 FadCat is a standalone, cross-platform Android Logcat viewer.
 .
 Features:
  - Works on x86_64 and ARM64 Linux
  - Color-coded logs with tag filtering
  - Real-time search and grep mode
  - Built-in ADB (no external dependencies)
  - Modern PyQt6 GUI
EOF

# Create postinst script
echo "  Creating postinst script..."
cat > "$DEB_ROOT/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
echo "🔧 Configuring FadCat..."
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi
echo "✓ FadCat installed successfully!"
exit 0
POSTINST
chmod +x "$DEB_ROOT/DEBIAN/postinst"

# Create prerm script
echo "  Creating prerm script..."
cat > "$DEB_ROOT/DEBIAN/prerm" << 'PRERM'
#!/bin/bash
set -e

# Only kill fadcat if it's actually running (not this script)
if pgrep -x "fadcat" > /dev/null 2>&1; then
    pkill -x "fadcat" 2>/dev/null || true
fi

exit 0
PRERM
chmod +x "$DEB_ROOT/DEBIAN/prerm"

# Create postrm script
echo "  Creating postrm script..."
cat > "$DEB_ROOT/DEBIAN/postrm" << 'POSTRM'
#!/bin/bash
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
fi
exit 0
POSTRM
chmod +x "$DEB_ROOT/DEBIAN/postrm"

# Create desktop entry
echo "  Creating desktop entry..."
cat > "$DEB_ROOT/usr/share/applications/fadcat.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=FadCat
GenericName=Android Logcat Viewer
Comment=Advanced Android logcat viewer
Exec=fadcat
Icon=fadcat
Terminal=false
Categories=Development;Debugging;
Keywords=android;adb;logcat;debug;
StartupWMClass=fadcat
DESKTOP

# Copy icon (use icon-assets/fadcat.png - official app icon)
echo "  Copying icons..."
if [ -f "icon-assets/fadcat.png" ]; then
    cp "icon-assets/fadcat.png" "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps/fadcat.png"
    echo "    ✓ Using icon-assets/fadcat.png"
elif [ -f "src/icons/fadcat-logo.png" ]; then
    cp "src/icons/fadcat-logo.png" "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps/fadcat.png"
    echo "    ✓ Using fadcat-logo.png (fallback)"
else
    echo "    ⚠️  No icon found"
fi

# Build the .deb
echo ""
echo -e "${YELLOW}📦 Building .deb package...${NC}"
DEB_FILE="${PROJECT_ROOT}/FadCat-v${VERSION}-linux.deb"
rm -f "$DEB_FILE"

dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_FILE"

# Cleanup
rm -rf "$DEB_ROOT"

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  ✅ Build Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  📦 Package: ${BLUE}FadCat-v${VERSION}-linux.deb${NC}"
echo -e "  📍 Location: ${BLUE}${DEB_FILE}${NC}"
echo ""
echo -e "${YELLOW}Installation:${NC}"
echo "  sudo apt install --reinstall ${DEB_FILE}"
echo ""
echo -e "${YELLOW}Uninstallation:${NC}"
echo "  sudo apt remove fadcat"
echo ""
