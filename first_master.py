#!/usr/bin/env python3
import subprocess
import time
import os

# Paths
VM_PATH = "/home/ubuntu/comnetsemu/app/Amarisoft.digital.twin"

def run_command(command, background=False, cwd=None):
    """Run a shell command with optional background execution."""
    if background:
        # Start process in background
        process = subprocess.Popen(command, shell=True, cwd=cwd,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Started background command: {command}")
        return process
    else:
        # Run command and wait for completion
        print(f"Running command: {command}")
        subprocess.run(command, shell=True, check=True, cwd=cwd)

def main():
    # Step 0: Run clean.sh
    print("[0/3] Running clean.sh...")
    run_command("sudo bash clean.sh", cwd=VM_PATH)

    # Step 1: Run twin_data_collector.py
    print("[1/3] Running twin_data_collector.py...")
    run_command("sudo python3 twin_data_collector.py", cwd=VM_PATH)

    # Step 2: Run modified.digital_twin_setup.py in background
    print("[2/3] Running modified.digital_twin_setup.py in background...")
    run_command("sudo nohup python3 modified.digital_twin_setup.py > setup.log 2>&1 &", cwd=VM_PATH, background=True)

    # Wait 60 seconds to give it time to start
    print("Waiting 60 seconds for setup to initialize...")
    time.sleep(60)

    print("✅ Steps 0-2 complete. Check setup.log for output of modified.digital_twin_setup.py")

if __name__ == "__main__":
    main()
