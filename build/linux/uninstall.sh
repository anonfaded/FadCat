#!/bin/bash
# FadCat Uninstaller for Linux

echo "🗑️  FadCat Uninstaller"
echo "===================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo "⚠️  This uninstaller requires sudo privileges"
   exec sudo bash "$0" "$@"
fi

echo "Removing FadCat package..."

# Remove .deb package
if dpkg -l | grep -q "^ii  fadcat"; then
    apt-get remove -y --purge fadcat
    echo "✓ Removed fadcat package"
else
    echo "⚠️  FadCat package not found (may already be removed)"
fi

# Clean up any leftover files
rm -rf /opt/fadcat
rm -f /usr/bin/fadcat
rm -f /usr/share/applications/fadcat.desktop
rm -f /usr/share/icons/hicolor/*/apps/fadcat.png

# Update caches
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi

echo ""

# Ask about settings
if [ -d "$HOME/.config/FadCat" ]; then
    read -p "Remove user settings? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/.config/FadCat"
        echo "✓ Removed user settings"
    else
        echo "⚠️  Settings preserved at: $HOME/.config/FadCat"
    fi
fi

echo ""
echo "✅ FadCat has been uninstalled successfully!"
