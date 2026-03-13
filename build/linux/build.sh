#!/bin/bash
# Build Linux .deb package (auto-registers fadcat command)

set -e
cd "$(dirname "$0")/../.."

# Extract version from src/version.py
VERSION=$(python3 -c "from src.version import __version__, __company__, __author__; print(__version__)" 2>/dev/null || echo "1.0.0")
COMPANY=$(python3 -c "from src.version import __company__; print(__company__)" 2>/dev/null || echo "FadSec Lab")
AUTHOR=$(python3 -c "from src.version import __author__; print(__author__)" 2>/dev/null || echo "Faded")

echo "🔨 Building FadCat v${VERSION}..."
pyinstaller -y build/FadCat-Linux.spec

echo "📦 Creating .deb package..."

# Create DEB structure
DEB_ROOT="/tmp/fadcat-deb"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps"

# Copy executable
cp dist/fadcat "$DEB_ROOT/usr/bin/fadcat"
chmod +x "$DEB_ROOT/usr/bin/fadcat"

# Control file (using version from src/version.py)
cat > "$DEB_ROOT/DEBIAN/control" << EOF
Package: fadcat
Version: ${VERSION}
Architecture: amd64
Maintainer: ${AUTHOR} <${AUTHOR}@fadseclab.com>
Description: Advanced Android logcat viewer with fuzzy search
 FadCat provides powerful logcat filtering, searching, and real-time highlighting.
EOF

# Desktop entry
cat > "$DEB_ROOT/usr/share/applications/fadcat.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=FadCat
Comment=Android logcat viewer
Exec=fadcat
Terminal=false
Categories=Development;
Icon=fadcat
EOF

# Copy icon
cp icon-assets/fadcat.ico "$DEB_ROOT/usr/share/icons/hicolor/128x128/apps/fadcat.png" 2>/dev/null || true

# Build DEB
dpkg-deb --build "$DEB_ROOT" FadCat.deb
echo "✅ Created FadCat.deb v${VERSION}"

rm -rf "$DEB_ROOT"

echo "✓ Created FadCat.deb"
echo "Users: sudo apt install ./FadCat.deb - fadcat command will work automatically"
