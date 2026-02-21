# FadCat

FadCat is a standalone, cross-platform Android Logcat viewer and utility tool. It provides both a fast CLI and a feature-rich GUI for filtering, searching, and managing Android logs. 

*This project is an enhanced fork and standalone wrapper of the original [pidcat](https://github.com/JakeWharton/pidcat) by Jake Wharton.*

## Features

- **Cross-Platform**: Works on Windows, macOS, and Linux.
- **Dual Modes**: Choose between a fast CLI or a modern GUI (PyQt6).
- **Color-Coded Logs**: Easy-to-read logcat output with color-coded tags and log levels.
- **Smart Filtering**: Automatically find an app's Process ID (PID) and show only relevant logs.
- **Advanced Search**: Real-time search, case-insensitive matching, and a powerful "Grep Mode" to filter logs dynamically.
- **Emulator Launcher**: Includes a utility to quickly launch Android emulators.
- **Standalone**: Can be packaged into a single executable with no external dependencies.

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/anonfaded/FadCat.git
   cd FadCat
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

### Pre-built Binaries

Download the latest release for your operating system from the [Releases](https://github.com/anonfaded/FadCat/releases) page. No installation required!

## Usage

Run the application:

```bash
python main.py
```

You will be prompted to choose between CLI and GUI mode.

To launch directly into GUI mode:

```bash
python main.py gui
```

<details>
<summary><b>Building from Source</b></summary>

To build standalone executables using PyInstaller:

```bash
pip install pyinstaller
pyinstaller FadCat.spec
```

The executables (`FadCat-CLI` and `FadCat-GUI`) will be located in the `dist` directory.

</details>

## License

This project is licensed under the MIT License.
