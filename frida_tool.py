import os
import subprocess
import threading
import time

# --- Configuration ---
FRIDA_SERVER_PATH = "/data/local/tmp"
FRIDA_SERVER_EXECUTABLE = "frida-server-16.4.1-android-arm64"
FRIDA_SCRIPTS = ["EMbypass.js", "3.sslPinning.js", "1.RootBypass.js"]

def run_command(command, shell=False):
    """Runs a command and returns its output."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
            text=True
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error running command: {' '.join(command)}")
            print(f"Stderr: {stderr}")
            return None
        return stdout.strip()
    except FileNotFoundError:
        print(f"Error: Command not found: {command[0]}")
        return None

def start_frida_server():
    """Starts the Frida server on the Android device."""
    print("--- Starting Frida Server ---")
    # Check if the server is already running
    pid = run_command(["adb", "shell", f"pidof {FRIDA_SERVER_EXECUTABLE}"])
    if pid:
        print("Frida server is already running.")
        return True

    print("Starting Frida server in the background...")
    command = f"adb shell 'su -c "cd {FRIDA_SERVER_PATH} && ./{FRIDA_SERVER_EXECUTABLE} &"'"
    # Since this command runs in the background, we don't need to wait for it.
    # We'll just run it and assume it works. A small delay to ensure it starts.
    subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3) # Give the server a moment to start

    # Verify it's running
    pid = run_command(["adb", "shell", f"pidof {FRIDA_SERVER_EXECUTABLE}"])
    if pid:
        print("Frida server started successfully.")
        return True
    else:
        print("Error: Failed to start Frida server.")
        print("Please ensure that the Frida server executable is located at:")
        print(f"{FRIDA_SERVER_PATH}/{FRIDA_SERVER_EXECUTABLE}")
        print("and that your device is properly rooted.")
        return False


def get_packages():
    """Gets a list of all installed packages on the device."""
    print("\n--- Getting list of installed packages ---")
    packages_output = run_command(["adb", "shell", "pm", "list", "packages"])
    if packages_output:
        packages = [line.split(":")[-1] for line in packages_output.splitlines()]
        return sorted(packages)
    return []

def main():
    """Main function to run the tool."""
    if not start_frida_server():
        return

    packages = get_packages()
    if not packages:
        print("Could not retrieve package list. Exiting.")
        return

    print("\n--- Select a package to bypass SSL pinning ---")
    for i, pkg in enumerate(packages):
        print(f"[{i+1}] {pkg}")

    try:
        choice = int(input("\nEnter the number of the package: ")) - 1
        if 0 <= choice < len(packages):
            selected_package = packages[choice]
            print(f"\nYou selected: {selected_package}")

            # Construct and run the Frida command
            frida_command = ["frida"]
            for script in FRIDA_SCRIPTS:
                frida_command.extend(["-l", script])
            frida_command.extend(["-U", "-f", selected_package, "--pause"])

            print("\n--- Starting Frida ---")
            print(f"Command: {' '.join(frida_command)}")
            print("Press Ctrl+C to stop the script.")

            # We use os.system here because frida can be interactive
            os.system(' '.join(frida_command))

        else:
            print("Invalid choice.")
    except (ValueError, IndexError):
        print("Invalid input. Please enter a number from the list.")

if __name__ == "__main__":
    main()
