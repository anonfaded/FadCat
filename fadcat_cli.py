#!/usr/bin/env python3
"""
CLI entry point for FadCat command
This allows running 'fadcat' directly from terminal
"""
import sys
import os

# Ensure src can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main entry point for fadcat command"""
    # MCP (Model Context Protocol) server mode
    if '--mcp' in sys.argv:
        try:
            import asyncio
            from src.mcp.server import main as run_mcp
            asyncio.run(run_mcp())
        except ImportError as e:
            print(f"MCP dependencies not installed: {e}", file=sys.stderr)
            print("Run: pip install -r requirements.txt", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"MCP Server error: {e}", file=sys.stderr)
            sys.exit(1)
        return
    
    # Check for CLI flag
    if '--cli' in sys.argv:
        # Remove the --cli flag before passing to CLI app
        sys.argv.remove('--cli')
        from src.cli.cli_app import LogcatCLI
        LogcatCLI().run()
        return
    
    # Default: Launch GUI
    from FadCat import launch_gui
    launch_gui()


if __name__ == '__main__':
    main()
