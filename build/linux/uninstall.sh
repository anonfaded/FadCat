#!/bin/bash
# FadCat Uninstaller for Linux

echo "🗑️  FadCat Uninstaller"
echo "===================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   echo "⚠️  This uninstaller requires sudo privileges"
   sudo bash "$0"
   exit $?
fi

echo "Removing FadCat package..."

# Remove .deb package
if dpkg -l | grep -q "^ii  fadcat"; then
    apt-get remove -y fadcat
    echo "✓ Removed fadcat package"
else
    echo "⚠️  FadCat package not found"
fi

# Remove settings (optional)
if [ -d "$HOME/.config/FadCat" ]; then
    read -p "Remove settings? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/.config/FadCat"
        echo "✓ Removed settings"
    fi
fi

echo ""
echo "✅ FadCat has been uninstalled successfully!"
