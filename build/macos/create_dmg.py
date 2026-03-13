#!/usr/bin/env python3
"""
Create a professional macOS DMG installer with custom styling and instructions.
"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path

def run_command(cmd, check=True, verbose=False):
    """Run shell command and return output."""
    if verbose:
        print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd}")
    return result.stdout.strip()

def create_dmg(pkg_path, output_dmg, app_icon_path):
    """Create a professional DMG with custom styling."""
    
    # Create temporary directory for DMG contents
    temp_dir = tempfile.mkdtemp()
    print(f"Creating DMG in temp directory: {temp_dir}")
    
    try:
        # Copy .pkg to temp directory
        pkg_dest = os.path.join(temp_dir, "FadCat.pkg")
        shutil.copy(pkg_path, pkg_dest)
        print(f"✓ Copied package")
        
        # Create Applications symlink
        apps_link = os.path.join(temp_dir, "Applications")
        try:
            os.symlink("/Applications", apps_link)
            print(f"✓ Created Applications symlink")
        except FileExistsError:
            pass
        
        # Copy icon for volume icon
        if os.path.exists(app_icon_path):
            icon_dest = os.path.join(temp_dir, ".VolumeIcon.icns")
            shutil.copy(app_icon_path, icon_dest)
            print(f"✓ Copied app icon")
        
        # Create attractive README.txt with instructions
        readme_path = os.path.join(temp_dir, "README.txt")
        with open(readme_path, 'w') as f:
            f.write("""
╔════════════════════════════════════════════════════════╗
║           FadCat - Advanced Logcat Viewer              ║
║                                                        ║
║  Installation Instructions:                            ║
║  ───────────────────────────                           ║
║                                                        ║
║  1. Double-click FadCat.pkg                           ║
║  2. Follow the installer prompts                       ║
║  3. The 'fadcat' command will auto-register            ║
║                                                        ║
║  After Installation:                                   ║
║  ──────────────────                                    ║
║  • fadcat              → Launch GUI                    ║
║  • fadcat --cli        → Launch CLI mode               ║
║  • Uninstall: Run uninstall script or:                 ║
║    rm -rf /Applications/FadCat.app                     ║
║    rm -f /usr/local/bin/fadcat                         ║
║                                                        ║
║  Features:                                             ║
║  • Fast logcat filtering with fuzzy search             ║
║  • Real-time log highlighting                          ║
║  • Cross-platform (macOS, Windows, Linux)              ║
║                                                        ║
║  Need help? Visit:                                      ║
║  github.com/anonfaded/FadCat                           ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
""")
        print(f"✓ Created README.txt")
        
        # Create uninstall script
        uninstall_path = os.path.join(temp_dir, "Uninstall FadCat.command")
        with open(uninstall_path, 'w') as f:
            f.write("""#!/bin/bash
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║         Uninstalling FadCat...                         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

rm -rf /Applications/FadCat.app 2>/dev/null
rm -f /usr/local/bin/fadcat 2>/dev/null

echo "✓ FadCat has been uninstalled"
echo ""
echo "Press Enter to close this window..."
read
""")
        os.chmod(uninstall_path, 0o755)
        print(f"✓ Created uninstall script")
        
        # Create DMG - use read-write format first for customization
        print(f"Creating DMG file...")
        temp_dmg = output_dmg.replace('.dmg', '.temp.dmg')
        
        # Create with UDRW (read-write) format
        create_cmd = f'hdiutil create -volname "FadCat Installer" -srcfolder "{temp_dir}" -ov -format UDRW "{temp_dmg}"'
        print(f"  {create_cmd}")
        run_command(create_cmd, check=True, verbose=False)
        
        if not os.path.exists(temp_dmg):
            raise RuntimeError(f"Failed to create temporary DMG: {temp_dmg}")
        
        print(f"✓ Created read-write DMG")
        
        # Attach DMG for customization
        print(f"Customizing DMG appearance...")
        attach_cmd = f'hdiutil attach "{temp_dmg}" -readwrite -noautoopen'
        attach_output = run_command(attach_cmd, check=False, verbose=False)
        
        # Parse mount point
        mount_point = None
        for line in attach_output.split('\n'):
            if "/Volumes/" in line:
                parts = line.split('\t')
                for part in parts:
                    if "/Volumes/" in part:
                        mount_point = part.strip()
                        break
                if mount_point:
                    break
        
        if mount_point and os.path.exists(mount_point):
            print(f"  Mounted at: {mount_point}")
            try:
                # Set volume icon
                icon_file = os.path.join(mount_point, ".VolumeIcon.icns")
                if os.path.exists(icon_file):
                    run_command(f'SetFile -a C "{mount_point}"', check=False, verbose=False)
                    print(f"  ✓ Set volume icon")
                
                # Try to set icon positions using AppleScript
                applescript = f'''tell application "Finder"
  delay 0.5
  set theFolder to POSIX file "{mount_point}"
  set theWindow to (open theFolder)
  set current view of theWindow to icon view
  tell icon view options of theWindow
    set icon size to 64
    set shows item info to false
    set arrangement to not arranged
  end tell
  delay 0.5
  close theWindow
end tell'''
                
                script_file = os.path.join(mount_point, ".setup.applescript")
                with open(script_file, 'w') as f:
                    f.write(applescript)
                
                run_command(f'osascript "{script_file}"', check=False, verbose=False)
                try:
                    os.remove(script_file)
                except:
                    pass
                print(f"  ✓ Configured window appearance")
                
            finally:
                # Detach DMG
                run_command(f'hdiutil detach "{mount_point}"', check=False, verbose=False)
                print(f"  ✓ Detached DMG")
        
        # Convert to compressed format
        print(f"Compressing DMG...")
        convert_cmd = f'hdiutil convert "{temp_dmg}" -format UDZO -imagekey zlib-level=9 -o "{output_dmg}"'
        run_command(convert_cmd, check=True, verbose=False)
        
        # Remove temporary DMG
        if os.path.exists(temp_dmg):
            os.remove(temp_dmg)
        
        if os.path.exists(output_dmg):
            size_mb = os.path.getsize(output_dmg) / (1024 * 1024)
            print(f"✓ Created {output_dmg} ({size_mb:.1f} MB)")
        else:
            raise RuntimeError(f"Final DMG was not created: {output_dmg}")
        
    finally:
        # Cleanup temp directory
        print(f"Cleaning up temporary files...")
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: create_dmg.py <pkg_path> <output_dmg> <app_icon_path>")
        sys.exit(1)
    
    pkg_path = sys.argv[1]
    output_dmg = sys.argv[2]
    app_icon_path = sys.argv[3]
    
    if not os.path.exists(pkg_path):
        print(f"Error: Package not found: {pkg_path}")
        sys.exit(1)
    
    create_dmg(pkg_path, output_dmg, app_icon_path)
