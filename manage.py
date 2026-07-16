#!/usr/bin/env python3
import sys
import subprocess
import os
from pathlib import Path

def get_python_exe():
    """Returns the path to the virtual environment's Python, or system python if not found."""
    venv_python = Path(__file__).parent / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable

def run_command(cmd, env=None):
    """Run a shell command and wait for it."""
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with exit code {e.returncode}")
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

def main():
    if len(sys.argv) < 2:
        print("\nAI Bot Management Script")
        print("Usage:")
        print("  python manage.py run dashboard    # Start the FastAPI dashboard")
        print("  python manage.py run bot.py       # Start the NEPSE TMS bot directly")
        print("  python manage.py run crypto       # Start the Crypto tracker directly")
        print("")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    python_exe = get_python_exe()

    if command == "run":
        if not args:
            print("[ERROR] Please specify what to run (dashboard, bot.py, or crypto).")
            sys.exit(1)
        
        target = args[0]
        
        if target == "dashboard":
            print("[INFO] Starting FastAPI Dashboard on port 8888...")
            run_command([python_exe, "app.py"] + args[1:])
            
        elif target == "bot.py" or target == "nepse":
            print("[INFO] Starting NEPSE TMS Bot...")
            env = os.environ.copy()
            env["HEADLESS"] = "false"
            run_command([python_exe, "bot.py"] + args[1:], env=env)
            
        elif target == "crypto" or target == "crypto_tracker.py":
            print("[INFO] Starting Crypto Tracker...")
            run_command([python_exe, "crypto_tracker.py"] + args[1:])
            
        else:
            # Try to run whatever the user specified if it's a file
            if os.path.exists(target):
                print(f"[INFO] Running {target}...")
                run_command([python_exe, target])
            else:
                print(f"[ERROR] Unknown target: {target}")
                sys.exit(1)
                
    else:
        print(f"[ERROR] Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
