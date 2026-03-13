#!/bin/bash
# FadCat Uninstaller for macOS

echo "🗑️  FadCat Uninstaller"
echo "===================="
echo ""

# Check if app is running
if pgrep -xq "FadCat"; then
    echo "⚠️  FadCat is currently running. Please close it first."
    exit 1
fi

echo "Removing FadCat..."

# Remove app
if [ -d "/Applications/FadCat.app" ]; then
    rm -rf /Applications/FadCat.app
    echo "✓ Removed /Applications/FadCat.app"
fi

# Remove command
if [ -f "/usr/local/bin/fadcat" ]; then
    rm -f /usr/local/bin/fadcat
    echo "✓ Removed /usr/local/bin/fadcat"
fi

# Remove settings (optional)
if [ -d "$HOME/Library/Application Support/FadCat" ]; then
    read -p "Remove settings? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/Library/Application Support/FadCat"
        echo "✓ Removed settings"
    fi
fi

echo ""
echo "✅ FadCat has been uninstalled successfully!"
