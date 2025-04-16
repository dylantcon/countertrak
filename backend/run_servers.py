"""
CounterTrak Server Runner - Runs Both Django and GSI server
Fixed to properly capture all subprocess output
"""
import os
import sys
import subprocess
import signal
import time
import shlex

# Get the absolute path to the script directory (backend folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_both_servers():
    """Run both Django and GSI servers with fixed output handling"""
    print("Starting CounterTrak servers...")

    # Verify .env file existence
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        print(f"Found .env file at: {env_path}")
    else:
        print(f"WARNING: .env file not found at: {env_path}")

    # Use absolute paths for everything
    manage_py = os.path.join(SCRIPT_DIR, "manage.py")
    gsi_server = os.path.join(SCRIPT_DIR, "gsi", "async_server.py")

    # Verify files exist before attempting to run them
    if not os.path.exists(manage_py):
        print(f"Error: Django manage.py not found at {manage_py}")
        return

    if not os.path.exists(gsi_server):
        print(f"Error: GSI server not found at {gsi_server}")
        return

    # Set up environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # Critical! Ensure unbuffered output
    
    # This is the key change - run GSI server with shell=True to preserve logging
    # Start Django server
    django_cmd = f"{sys.executable} {manage_py} runserver 0.0.0.0:8000"
    django_process = subprocess.Popen(
        django_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        bufsize=1,
        cwd=SCRIPT_DIR,
        env=env
    )
    print(f"Django server started with PID {django_process.pid}")

    # Start GSI server with shell=True
    gsi_cmd = f"{sys.executable} -u {gsi_server}"  # Force Python unbuffered mode
    gsi_process = subprocess.Popen(
        gsi_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        bufsize=1,
        cwd=SCRIPT_DIR,
        env=env
    )
    print(f"GSI server started with PID {gsi_process.pid}")

    # Function to handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down servers...")
        gsi_process.terminate()
        django_process.terminate()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Process and display output more aggressively
    try:
        while True:
            # Process Django output
            django_line = django_process.stdout.readline()
            if django_line:
                print(f"[Django] {django_line}", end="", flush=True)

            # Process GSI output
            gsi_line = gsi_process.stdout.readline()
            if gsi_line:
                print(f"[GSI] {gsi_line}", end="", flush=True)

            # Check if either process has terminated
            if django_process.poll() is not None:
                print(f"Django server stopped unexpectedly with code {django_process.returncode}")
                break

            if gsi_process.poll() is not None:
                print(f"GSI server stopped unexpectedly with code {gsi_process.returncode}")
                break

            # Short sleep to reduce CPU usage
            time.sleep(0.05)
    finally:
        gsi_process.terminate()
        django_process.terminate()

if __name__ == "__main__":
    # Set the Python path to include the backend directory
    sys.path.insert(0, SCRIPT_DIR)

    # Set working directory to script directory
    os.chdir(SCRIPT_DIR)

    run_both_servers()
