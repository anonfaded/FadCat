#!/bin/bash
# Build macOS .dmg installer with create-dmg (professional branding)

set -e
cd "$(dirname "$0")/../.."

# Extract version from src/version.py
VERSION=$(python3 -c "from src.version import __version__; print(__version__)" 2>/dev/null || echo "1.0.0")

echo "🔨 Building FadCat v${VERSION}..."
export PYINSTALLER_CONFIG_DIR="$(pwd)/dist/.pyinstaller"
rm -rf "$PYINSTALLER_CONFIG_DIR" 2>/dev/null
pyinstaller -y build/FadCat-macOS.spec

if [ ! -d "dist/FadCat.app" ]; then
    echo "❌ Error: FadCat.app not found in dist/"
    exit 1
fi

echo "📦 Creating professional DMG with create-dmg..."
cd dist

# Use create-dmg to create a beautiful DMG (skip code signing for faster build)
TMPDIR=/tmp create-dmg "FadCat.app" --overwrite --no-code-sign 2>&1 || true

# Rename the created DMG to our standard name with version and platform
DMG_FILE=$(ls -t *.dmg 2>/dev/null | head -1)
if [ -n "$DMG_FILE" ]; then
    mv "$DMG_FILE" "FadCat-v${VERSION}-macOS.dmg"
    SIZE=$(du -h "FadCat-v${VERSION}-macOS.dmg" | awk '{print $1}')
    FULL_DMG_PATH="$(pwd)/FadCat-v${VERSION}-macOS.dmg"

    # Clean up: remove the app since it's now packaged in the DMG
    rm -rf FadCat.app 2>/dev/null

    echo ""
    echo "\033[1;32m✔ Created \"FadCat ${VERSION}.dmg\"\033[0m"
    echo ""
    echo "✅ Professional FadCat installer created!"
    echo "   📁 $FULL_DMG_PATH ($SIZE)"
    echo "   📦 Version: ${VERSION}"
    echo ""
    echo "Installation:"
    echo "   open \"$FULL_DMG_PATH\""
    echo "   # Drag FadCat.app to /Applications/"
    echo "   # (Optional) Run Install CLI Command.command for CLI without launching"
    echo ""
    echo "Uninstallation:"
    echo "   rm -rf /Applications/FadCat.app"
    echo ""
    echo "Architecture Support:"
    echo "   ✓ macOS x86_64 (Intel)"
    echo "   ✓ macOS ARM64 (Apple Silicon)"
else
    echo "❌ Error: DMG creation failed"
    exit 1
fi

cd ..
