#!/bin/bash
# Build macOS .dmg installer with create-dmg (professional branding)

set -e
cd "$(dirname "$0")/../.."

# Extract version from src/version.py
VERSION=$(python3 -c "from src.version import __version__; print(__version__)" 2>/dev/null || echo "1.0.0")

echo "🔨 Building FadCat v${VERSION}..."
pyinstaller -y build/FadCat-macOS.spec

if [ ! -d "dist/FadCat.app" ]; then
    echo "❌ Error: FadCat.app not found in dist/"
    exit 1
fi

echo "📦 Creating professional DMG with create-dmg..."
cd dist

# Use create-dmg to create a beautiful DMG (skip code signing for faster build)
# create-dmg uses version from app's CFBundleShortVersionString
npx create-dmg FadCat.app --overwrite --no-code-sign 2>&1 || true

# Rename the created DMG to our standard name
DMG_FILE=$(ls -t FadCat*.dmg 2>/dev/null | head -1)
if [ -n "$DMG_FILE" ]; then
    mv "$DMG_FILE" FadCat-Installer.dmg
    SIZE=$(du -h FadCat-Installer.dmg | awk '{print $1}')
    
    # Clean up: remove the app since it's now packaged in the DMG
    rm -rf FadCat.app 2>/dev/null
    
    echo ""
    echo "✅ Professional FadCat installer created!"
    echo "   📁 FadCat-Installer.dmg ($SIZE)"
    echo "   📦 Version: ${VERSION}"
    echo ""
    echo "Features:"
    echo "   • Beautiful drag-and-drop interface"
    echo "   • Professional icon and branding"
    echo "   • macOS standard appearance"
    echo "   • Ready to distribute"
else
    echo "❌ Error: DMG creation failed"
    exit 1
fi

cd ..
