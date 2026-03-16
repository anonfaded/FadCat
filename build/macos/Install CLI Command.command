#!/bin/bash
# FadCat CLI Installer for macOS

set -e

APP_BIN="/Applications/FadCat.app/Contents/MacOS/FadCat"
CLI_DIR="$HOME/.local/bin"
CLI_PATH="$CLI_DIR/fadcat"

if [ ! -x "$APP_BIN" ]; then
    echo "❌ FadCat.app not found in /Applications."
    echo "   Please drag FadCat.app to /Applications first."
    exit 1
fi

mkdir -p "$CLI_DIR"
cat > "$CLI_PATH" <<'EOF'
#!/bin/bash
exec "/Applications/FadCat.app/Contents/MacOS/FadCat" "$@"
EOF
chmod 755 "$CLI_PATH"

for rc in "$HOME/.zprofile" "$HOME/.bash_profile"; do
    if [ -f "$rc" ]; then
        if ! grep -q '\.local/bin' "$rc"; then
            echo '' >> "$rc"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
        fi
    fi
done

echo "✅ Installed fadcat to $CLI_PATH"
echo "   Restart your terminal or run: source ~/.zprofile"
