<div align="center">

<img src="icon-assets/fadcat.png" alt="FadCat Logo" width="120">

# `>_` FadCat

FadCat is a lightweight, feature-rich, cross‑platform Android logcat replacement for Android Studio, without the bloat. It bundles ADB for supported architectures and runs in GUI, CLI, or MCP server mode.

[![GitHub all releases](https://img.shields.io/github/downloads/anonfaded/FadCat/total?label=Downloads&logo=github)](https://github.com/anonfaded/FadCat/releases/)
[![Patreon](https://img.shields.io/badge/Patreon-Support-orange?logo=patreon&label=Patreon)](https://www.patreon.com/cw/Fadedx/shop)
[![Discord](https://img.shields.io/discord/1263384048194027520?label=Join%20Us%20on%20Discord&logo=discord)](https://discord.gg/kvAZvdkuuN)

<p align="center">
        <img src="https://raw.githubusercontent.com/bornmay/bornmay/Update/svg/Bottom.svg" alt="Github Stats" />
</p>

</div>

> [!Tip]
> This project is part of the [FadSec Lab suite](https://github.com/fadsec-lab). <br> Discover our focus on ad-free, privacy-first applications and stay updated on future releases!

FadCat also ships **specialized FadCam media tools** to browse and pull FadCam media for backups.  
FadCam repository: [FadCam](https://github.com/anonfaded/FadCam)

| ⭐ |<img src="https://github.com/user-attachments/assets/c730eda3-5887-458d-8df1-971a74807b73" style="width: 100px; height: auto;" > | *From the FadSec-Lab suite:* <br> Also, check out our Desktop app/file/folder locker: [FadCrypt](https://github.com/anonfaded/FadCrypt) |
|--|-------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------|

## `>_` Features
- **Logcat sessions**: multi‑device capture with dedicated tabs per device/session
- **Bundled ADB**: architecture‑aware selection without relying on system ADB
- **MCP server**: AI assistants can inspect devices, logs, processes, and media safely
- **FadCam integration**: deep integration to browse and pull FadCam media for backups
- **Cross‑platform utility**: macOS, Linux, and Windows

## `>_` What FadCat Is For
FadCat is designed for fast daily Android debugging: logcat exploration, device inspection, and structured AI workflows via MCP.  
It is also a **specialized companion for FadCam**, built to browse and manage FadCam media and pull backups to your PC.

## `>_` Modes

### `>_` GUI (default)
```bash
fadcat
```

### `>_` CLI
```bash
fadcat --cli
```

### `>_` MCP Server (stdio)
```bash
fadcat --mcp
```

## `>_` MCP Overview
FadCat exposes a FastMCP server so AI assistants can use FadCat’s MCP tools.

**Core MCP capabilities**
- Device discovery and system info
- Logcat streaming and search
- App process inspection
- FadCam media browsing and selective pulls

**Roadmap direction**
FadCat MCP is evolving toward more autonomous Android workflows. Planned areas include:
- Device automation and capture flows (e.g., integration with open‑source tools like scrcpy)
- APK‑level inspection and reverse‑engineering helpers
- Richer device diagnostics and automated debugging routines

## `>_` MCP Setup (IDE)
**Recommended: OpenCode (Free)**
1. Run: `opencode mcp add`
2. Use:
   - Name: `fadcat`
   - Type: `local`
   - Command: `fadcat`
   - Args: `--mcp`

**Manual Config (Other AI Tools)**
Add one of the following MCP configs in your IDE settings:

**Installed (recommended)**
```json
{
  "fadcat": {
    "type": "stdio",
    "command": "fadcat",
    "args": ["--mcp"],
    "env": {"PYTHONUNBUFFERED": "1"}
  }
}
```

<details>
<summary>Local Dev (run from source)</summary>

```json
{
  "fadcat": {
    "type": "stdio",
    "command": "/opt/homebrew/bin/python3",
    "args": ["-m", "src.mcp"],
    "env": {
      "PYTHONUNBUFFERED": "1",
      "PYTHONPATH": "/path/to/FadCat"
    }
  }
}
```

Notes:
- Replace `command` with your Python path from `which python3`.
- Replace `PYTHONPATH` with the path where you cloned the FadCat repo.
</details>

On macOS, the CLI command is registered on first launch.

## `>_` MCP Prompt Examples

### `>_` FadCam MCP
- `Browse FadCam beta camera recordings in internal storage.`
- `Browse FadCam Pro+ recordings on the SD card.`
- `Browse FadCam media and tell me total videos and space used.`
- `Browse the forensic gallery, then pull the latest 5 forensic snapshots.`
- `Pull this exact file: FadCam_YYYYMMDD_HHMMSS.mp4`

### `>_` General MCP
- `Summarize the latest logcat warnings and errors.`
- `Analyze app crash logs and suggest the root cause.`
- `List connected devices and show device details.`
- `Show system info and storage stats for the selected device.`

## `>_` 📱 Screenshots

<div align="center">
    <br><br>
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
    <img src="icon-assets/fadcat.png" style="width: 200px; height: auto;" >
 <br>
</div>

## `>_` ⬇️ Download

Download the latest release from the [releases page](https://github.com/anonfaded/FadCat/releases).

[<img src="https://raw.githubusercontent.com/vadret/android/master/assets/get-github.png" alt="Get it on GitHub" height="70">](https://github.com/anonfaded/FadCat/releases)

## `>_` Join Community
Join our [Discord server](https://discord.gg/kvAZvdkuuN) to share ideas, seek help, or connect with other users. Your feedback and contributions are welcome!

[![Discord](https://img.shields.io/discord/1263384048194027520?label=Join%20Us%20on%20Discord&logo=discord)](https://discord.gg/kvAZvdkuuN)

## `>_` Support & Shop

Support development via Patreon.

[![Patreon](https://img.shields.io/badge/Patreon-Support-orange?logo=patreon&label=Patreon)](https://www.patreon.com/cw/Fadedx/shop)

<details>
<summary>Contributing and Requirements</summary>

**Contributing**
- Open an issue first to discuss the feature or fix.
- Fork the repo and create a feature branch.
- Commit your changes with a clear message.
- Open a pull request and link the related issue.

**Requirements**
- Python 3.8+ (built and tested on Python 3.14)
- Dependencies in `requirements.txt`

**Dev quick start**
```bash
pip3 install -r requirements.txt
python3 FadCat.py
```
</details>

## `>_` License
Apache 2.0
