import os
import subprocess
import platform
import sys

# Constants
OS_TYPE = platform.system()
AVD_NAME = "Medium_Phone_API_36.1"

# OS-specific paths and commands
if OS_TYPE == "Windows":
    AVD_HOME = r"D:\Android\avd"
    EMULATOR_DIR = r"D:\Android\Sdk\emulator"
    EMULATOR_CMD = "emulator.exe"
elif OS_TYPE == "Linux":
    # Default paths; adjust if needed
    AVD_HOME = os.path.expanduser("~/.android/avd")
    EMULATOR_DIR = os.path.expanduser("~/Android-Sdk/emulator")
    EMULATOR_CMD = "./emulator"
elif OS_TYPE == "Darwin":
    # macOS paths
    AVD_HOME = os.path.expanduser("~/.android/avd")
    EMULATOR_DIR = os.path.expanduser("~/Library/Android/sdk/emulator")
    EMULATOR_CMD = "./emulator"
else:
    raise OSError(f"Unsupported OS: {OS_TYPE}")

class EmulatorLauncher:
    def __init__(self):
        self.avd_home = AVD_HOME
        self.emulator_dir = EMULATOR_DIR
        self.avd_name = AVD_NAME

    def set_environment(self):
        os.environ["ANDROID_AVD_HOME"] = self.avd_home
        print(f"Set ANDROID_AVD_HOME to {self.avd_home}")

    def launch_emulator(self):
        try:
            os.chdir(self.emulator_dir)
            print(f"Changed to directory: {self.emulator_dir}")
            subprocess.run([EMULATOR_CMD, "-avd", self.avd_name], check=False)
        except FileNotFoundError:
            print(f"Error: Emulator not found at {self.emulator_dir}. Please check paths.")
        except OSError as e:
            print(f"OS error: {e}")
        except subprocess.SubprocessError as e:
            print(f"Subprocess error: {e}")

    def run(self):
        while True:
            try:
                self.set_environment()
                self.launch_emulator()
                break  # Exit on success
            except KeyboardInterrupt:
                print("\n\n⚠️  Ctrl+C detected!")
                confirm = input("Do you want to exit? (y/n): ").strip().lower()
                if confirm == 'y':
                    print("Exiting...")
                    sys.exit(0)
                else:
                    print("Restarting process...\n")
                    continue

if __name__ == "__main__":
    launcher = EmulatorLauncher()
    launcher.run()
