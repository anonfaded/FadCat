#!/usr/bin/env -S python -u

'''
Copyright 2009, The Android Open Source Project

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

# Script to highlight adb logcat output for console
# Originally written by Jeff Sharkey, http://jsharkey.org/
# Piping detection and popen() added by other Android team members
# Package filtering and output improvements by Jake Wharton, http://jakewharton.com

import argparse
import sys
import re
import subprocess
from subprocess import PIPE
import shutil
import colorama
from pathlib import Path

# Ensure project root is in sys.path for imports to work when run as a script
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.utils.adb_path import get_adb_path
from src.version import __version__

# Initialize colorama to process ANSI escape codes on Windows
colorama.init()

# A sensible version bump reflecting new features.
VERSION = __version__

# FadCat branding (pidcat is internal script)
APP_NAME = "FadCat"


def check_adb_device():
    """Checks for a connected ADB device and prompts for selection if multiple are found."""
    try:
        adb_path = get_adb_path()
        # Use a timeout to prevent the command from hanging indefinitely.
        result = subprocess.run([adb_path, 'devices'], capture_output=True, text=True, check=True, timeout=5)
        lines = result.stdout.strip().splitlines()
        
        # Skip the first line which is just a header
        device_lines = [line for line in lines[1:] if line.strip()]
        
        # Check if we have any authorized devices
        authorized_devices = []
        for line in device_lines:
            parts = line.split()
            if len(parts) >= 2 and 'device' in parts[1] and 'unauthorized' not in parts[1]:
                authorized_devices.append(parts[0])  # The first part is the device serial
                
        if not authorized_devices:
            print("❌ ERROR: No authorized ADB device found. Please connect a device with USB debugging enabled.", file=sys.stderr)
            sys.exit(1)
            
        # If we have one device, or device selection parameters are already provided, we're good (silent mode)
        if len(authorized_devices) == 1 or args.device_serial or args.use_device or args.use_emulator:
            return None  # Device already selected or only one available - no need to select
            
        # If we have multiple devices and no selection made, ask the user
        print(f"📱 Multiple devices found ({len(authorized_devices)}). Please select one:")
        for idx, device in enumerate(authorized_devices):
            print(f"  [{idx + 1}] {device}")
            
        selection = None
        while selection is None:
            try:
                choice = input("Enter device number [1-{}]: ".format(len(authorized_devices)))
                idx = int(choice) - 1
                if 0 <= idx < len(authorized_devices):
                    selection = authorized_devices[idx]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a valid number.")
            except EOFError:
                # Occurs in bundled exec mode when stdin is not available
                # Use the first connected device as fallback
                print(f"⚠️  Interactive device selection not available.", file=sys.stderr)
                print(f"⚠️  Defaulting to first device: {authorized_devices[0]}", file=sys.stderr)
                selection = authorized_devices[0]
                break
                
        print(f"✅ Selected device: {selection}")
        return selection
            
    except RuntimeError as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ ERROR: ADB execution failed: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("❌ ERROR: 'adb devices' command timed out. ADB server may be unresponsive.", file=sys.stderr)
        sys.exit(1)


LOG_LEVELS = 'VDIWEF'
LOG_LEVELS_MAP = dict([(LOG_LEVELS[i], i) for i in range(len(LOG_LEVELS))])
parser = argparse.ArgumentParser(
    description='Filter logcat by package name with colored output.',
    epilog='Example: python pidcat.py com.example.app'
)
parser.add_argument('package', nargs='*', help='Application package name(s)')
parser.add_argument('-w', '--tag-width', metavar='N', dest='tag_width', type=int, default=23, help='Width of log tag')
parser.add_argument('-l', '--min-level', dest='min_level', type=str, choices=LOG_LEVELS+LOG_LEVELS.lower(), default='V', help='Minimum level to be displayed (V, D, I, W, E, F)')
parser.add_argument('--color-gc', dest='color_gc', action='store_true', help='Color garbage collection')
parser.add_argument('--always-display-tags', dest='always_tags', action='store_true',help='Always display the tag name')
parser.add_argument('--current', dest='current_app', action='store_true',help='Filter logcat by current running app')
parser.add_argument('-s', '--serial', dest='device_serial', help='Device serial number (adb -s option)')
parser.add_argument('-d', '--device', dest='use_device', action='store_true', help='Use first device for log input (adb -d option)')
parser.add_argument('-e', '--emulator', dest='use_emulator', action='store_true', help='Use first emulator for log input (adb -e option)')
parser.add_argument('-c', '--clear', dest='clear_logcat', action='store_true', help='Clear the entire log before running')
parser.add_argument('-t', '--tag', dest='tag', action='append', help='Filter output by specified tag(s)')
parser.add_argument('-i', '--ignore-tag', dest='ignored_tag', action='append', help='Filter output by ignoring specified tag(s)')
parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + VERSION, help='Print the version number and exit')
parser.add_argument('-a', '--all', dest='all', action='store_true', default=False, help='Print all log messages')

args = parser.parse_args()
min_level = LOG_LEVELS_MAP[args.min_level.upper()]

package = args.package

selected_device = check_adb_device()

try:
    adb_path = get_adb_path()
    base_adb_command = [adb_path]
except RuntimeError as e:
    print(f"❌ ERROR: {e}", file=sys.stderr)
    sys.exit(1)

if args.device_serial:
  base_adb_command.extend(['-s', args.device_serial])
elif selected_device:
  base_adb_command.extend(['-s', selected_device])
elif args.use_device:
  base_adb_command.append('-d')
elif args.use_emulator:
  base_adb_command.append('-e')

if args.current_app:
  system_dump_command = base_adb_command + ["shell", "dumpsys", "activity", "activities"]
  system_dump_process = subprocess.Popen(system_dump_command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
  system_dump = system_dump_process.communicate()[0]
  running_package_name_match = re.search(".*TaskRecord.*A[= ]([^ ^}]*)", system_dump)
  if running_package_name_match:
      current_package = running_package_name_match.group(1)
      package.append(current_package)

if len(package) == 0:
  args.all = True

catchall_package = list(filter(lambda p: p.find(":") == -1, package))
named_processes = list(filter(lambda p: p.find(":") != -1, package))
named_processes = list(map(lambda p: p if p.find(":") != len(p) - 1 else p[:-1], named_processes))

# Print minimal status header to stderr (not stdout to keep normal output clean)
if args.all:
    print("📊 Showing all logcat messages\n", file=sys.stderr)
elif len(package) > 0:
    pkg_list = ", ".join(package[:3]) + (f" +{len(package)-3} more" if len(package) > 3 else "")
    print(f"📦 Filtering: {pkg_list}\n", file=sys.stderr)

header_size = args.tag_width + 1 + 3 + 1
stdout_isatty = sys.stdout.isatty()

width = -1
try:
  width, _ = shutil.get_terminal_size()
except OSError:
  pass

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
RESET = '\033[0m'

def termcolor(fg=None, bg=None):
  codes = []
  if fg is not None: codes.append('3%d' % fg)
  if bg is not None: codes.append('4%d' % bg)
  return '\033[%sm' % ';'.join(codes) if codes else ''

def colorize(message, fg=None, bg=None):
  return termcolor(fg, bg) + message + RESET if stdout_isatty else message

def indent_wrap(message):
    if width <= 0 or (width - header_size) <= 0:
        return message
    message = message.replace('\t', '    ')
    wrap_area = width - header_size
    return '\n'.join([message[i:i+wrap_area] for i in range(0, len(message), wrap_area)])

LAST_USED = [RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN]
KNOWN_TAGS = {
  'dalvikvm': WHITE, 'Process': WHITE, 'ActivityManager': WHITE, 'ActivityThread': WHITE,
  'AndroidRuntime': CYAN, 'jdwp': WHITE, 'StrictMode': WHITE, 'DEBUG': YELLOW,
}

def allocate_color(tag):
  if tag not in KNOWN_TAGS:
    KNOWN_TAGS[tag] = LAST_USED[0]
  color = KNOWN_TAGS[tag]
  if color in LAST_USED:
    LAST_USED.remove(color)
    LAST_USED.append(color)
  return color

RULES = {re.compile(r'^(StrictMode policy violation)(; ~duration=)(\d+ ms)') : r'%s\1%s\2%s\3%s' % (termcolor(RED), RESET, termcolor(YELLOW), RESET)}
if args.color_gc:
  key = re.compile(r'^(GC_(?:CONCURRENT|FOR_M?ALLOC|EXTERNAL_ALLOC|EXPLICIT) )(freed <?\d+.)(, \d+\% free \d+./\d+., )(paused \d+ms(?:\+\d+ms)?)')
  val = r'\1%s\2%s\3%s\4%s' % (termcolor(GREEN), RESET, termcolor(YELLOW), RESET)
  RULES[key] = val

TAGTYPES = {
  'V': colorize(' V ', fg=WHITE, bg=BLACK), 'D': colorize(' D ', fg=BLACK, bg=BLUE),
  'I': colorize(' I ', fg=BLACK, bg=GREEN), 'W': colorize(' W ', fg=BLACK, bg=YELLOW),
  'E': colorize(' E ', fg=BLACK, bg=RED),   'F': colorize(' F ', fg=BLACK, bg=RED),
}

PID_LINE = re.compile(r'^\w+\s+(\w+)\s+.*?\s([\w|\.|\/]+)$')
PID_START = re.compile(r'^.*: Start proc ([a-zA-Z0-9._:]+) for ([a-z]+ [^:]+): pid=(\d+) uid=(\d+) gids=(.*)$')
PID_START_5_1 = re.compile(r'^.*: Start proc (\d+):([a-zA-Z0-9._:]+)/[a-z0-9]+ for (.*)$')
PID_START_DALVIK = re.compile(r'^E/dalvikvm\(\s*(\d+)\): >>>>> ([a-zA-Z0-9._:]+) \[ userId:0 \| appId:(\d+) \]$')
PID_KILL  = re.compile(r'^Killing (\d+):([a-zA-Z0-9._:]+)/[^:]+: (.*)$')
PID_LEAVE = re.compile(r'^No longer want ([a-zA-Z0-9._:]+) \(pid (\d+)\): .*$')
PID_DEATH = re.compile(r'^Process ([a-zA-Z0-9._:]+) \(pid (\d+)\) has died.?$')
LOG_LINE  = re.compile(r'^([A-Z])/(.+?)\( *(\d+)\): (.*?)$')
BUG_LINE  = re.compile(r'.*nativeGetEnabledTags.*')
BACKTRACE_LINE = re.compile(r'^#(.*?)pc\s(.*?)$')

adb_command = base_adb_command[:]
adb_command.append('logcat')
adb_command.extend(['-v', 'brief'])

if args.clear_logcat:
  print("Clearing logcat buffer (this may fail on some Android versions)...")
  try:
    subprocess.run(list(adb_command) + ['-c'], check=True, capture_output=True)
    print("Buffer cleared successfully.")
  except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
    print("Warning: Could not clear log buffer. This is common on newer Android versions.")

pids = set()
last_tag = None
app_pid = None

def match_packages(token):
  if not package: return True
  if token in named_processes: return True
  index = token.find(':')
  return (token in catchall_package) if index == -1 else (token[:index] in catchall_package)

def parse_death(tag, message):
  if tag != 'ActivityManager': return None, None
  for pattern in [PID_KILL, PID_LEAVE, PID_DEATH]:
    m = pattern.match(message)
    if m:
      pid = m.group(1) if pattern != PID_LEAVE else m.group(2)
      pname = m.group(2) if pattern != PID_LEAVE else m.group(1)
      if match_packages(pname) and pid in pids: return pid, pname
  return None, None

def parse_start_proc(line):
  patterns = [PID_START_5_1, PID_START, PID_START_DALVIK]
  for pattern in patterns:
    start = pattern.match(line)
    if start:
      if pattern == PID_START_5_1: return start.group(2), start.group(3), start.group(1), '', ''
      if pattern == PID_START: return start.groups()
      if pattern == PID_START_DALVIK: return start.group(2), '', start.group(1), start.group(3), ''
  return None

def tag_in_tags_regex(tag, tags):
  return any(re.match(r'^' + t + r'$', tag, re.IGNORECASE) for t in map(str.strip, tags))

# Initialize ADB connection - always run the actual adb logcat subprocess
adb = subprocess.Popen(adb_command, stdin=PIPE, stdout=PIPE, text=True)

if not args.all:
    ps_command = base_adb_command + ['shell', 'ps']
    try:
        ps_output = subprocess.check_output(ps_command, universal_newlines=True)
        for line in ps_output.splitlines():
            pid_match = PID_LINE.match(line)
            if pid_match:
                pid, proc = pid_match.groups()
                if match_packages(proc):
                    pids.add(pid)
        
        # Inform user if app is not currently running
        if not pids:
            print(f"⏳ Waiting for app to start... (will capture logs once '{', '.join(package)}' launches)\n", file=sys.stderr)
    except FileNotFoundError:
        print("❌ ERROR: Could not find a running ADB process. Please check the connection.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass

try:
    while adb and adb.poll() is None:
        try:
            if hasattr(adb, 'stdout') and adb.stdout:
                line = adb.stdout.readline()
            elif not sys.stdin.isatty():
                line = sys.stdin.readline()
            else:
                # No valid input source
                break
                
            if not line:  # End of file
                break
                
            # Ensure it's a string (should be with text=True)
            line = line.strip()
            if not line:
                continue
                
            if BUG_LINE.match(line):
                continue
                
            log_line = LOG_LINE.match(line)
            if not log_line:
                continue

            level, tag, owner, message = log_line.groups()
            tag = tag.strip()
            
            start = parse_start_proc(line)
            if start:
              line_package, target, line_pid, line_uid, line_gids = start
              if match_packages(line_package) and line_pid not in pids:
                pids.add(line_pid)
                app_pid = line_pid
                linebuf  = '\n' + colorize(' ' * (header_size - 1), bg=WHITE)
                linebuf += indent_wrap(' Process %s created for %s\n' % (line_package, target))
                linebuf += colorize(' ' * (header_size - 1), bg=WHITE)
                linebuf += ' PID: %s   UID: %s   GIDs: %s' % (line_pid, line_uid, line_gids)
                linebuf += '\n'
                print(linebuf)
                last_tag = None

            dead_pid, dead_pname = parse_death(tag, message)
            if dead_pid and dead_pid in pids:
              pids.remove(dead_pid)
              linebuf  = '\n' + colorize(' ' * (header_size - 1), bg=RED)
              linebuf += ' Process %s (PID: %s) ended' % (dead_pname, dead_pid)
              linebuf += '\n'
              print(linebuf)
              last_tag = None

            if tag == 'DEBUG' and BACKTRACE_LINE.match(message.lstrip()):
              message = message.lstrip()
              owner = app_pid

            # Filter by PID if we have collected any, otherwise use package name matching
            if not args.all:
              if pids and owner not in pids:
                # We have PIDs collected, so skip if this PID isn't one we care about
                continue
              elif not pids and not match_packages(tag):
                # No PIDs collected yet, filter by package name in the tag
                continue
            if level in LOG_LEVELS_MAP and LOG_LEVELS_MAP[level] < min_level: continue
            if args.ignored_tag and tag_in_tags_regex(tag, args.ignored_tag): continue
            if args.tag and not tag_in_tags_regex(tag, args.tag): continue

            linebuf = ''
            if args.tag_width > 0:
              if tag != last_tag or args.always_tags:
                last_tag = tag
                color = allocate_color(tag)
                if len(tag) < args.tag_width:
                  tag = tag.rjust(args.tag_width)
                linebuf += colorize(tag, fg=color)
              else:
                linebuf += ' ' * args.tag_width
              linebuf += ' '

            linebuf += TAGTYPES.get(level, ' ' + level + ' ')
            linebuf += ' '

            for matcher, replace in RULES.items():
              message = matcher.sub(replace, message)

            linebuf += indent_wrap(message)
            print(linebuf)

        except KeyboardInterrupt:
            print(f"\n--- {APP_NAME} stopped. ---")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
finally:
    # De-initialize colorama to restore original terminal settings.
    colorama.deinit()
