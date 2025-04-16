"""
CounterTrak Server Runner - Runs Both Django and GSI server
Uses threading to properly handle subprocess output streams
"""
import os
import sys
import subprocess
import signal
import time
import threading
import socket
import psutil

# Get the absolute path to the script directory (backend folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def stream_output(process, prefix):
    """
    Stream output from a subprocess with a prefix label.
    This function runs in its own thread to prevent blocking.
    
    Args:
        process: The subprocess.Popen instance to read from
        prefix: The label to add to each line (e.g., "Django" or "GSI")
    """
    for line in iter(process.stdout.readline, ''):
        if line:
            # Print with the prefix and ensure immediate flushing
            print(f"[{prefix}] {line}", end="", flush=True)

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def terminate_process_and_children(process):
    """Terminate a process and all its children recursively"""
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        
        # First send SIGTERM to parent
        process.terminate()
        
        # Then terminate children
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
                
        # Wait for parent process to terminate (with timeout)
        process.wait(timeout=3)
        
        # If still running, kill it forcefully
        if process.poll() is None:
            process.kill()
            
        # Kill any remaining children forcefully
        for child in children:
            try:
                if psutil.Process(child.pid).is_running():
                    child.kill()
            except psutil.NoSuchProcess:
                pass
                
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"Error terminating process: {e}")

def run_both_servers():
    """Run both Django and GSI servers with thread-based output handling"""
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
        
    # Check if ports are already in use
    if is_port_in_use(8000):
        print("Error: Port 8000 is already in use. Django server cannot start.")
        return
        
    if is_port_in_use(3000):
        print("Error: Port 3000 is already in use. GSI server cannot start.")
        return

    # Set up environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # Critical! Ensure unbuffered output
    
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

    # Start GSI server
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

    # Flag to track shutdown state
    is_shutting_down = False

    # Function to handle graceful shutdown
    def signal_handler(sig, frame):
        nonlocal is_shutting_down
        if is_shutting_down:
            print("\nForcing immediate exit...")
            os._exit(1)  # Emergency exit if CTRL+C pressed twice
            
        is_shutting_down = True
        print("\nShutting down servers (press CTRL+C again to force)...")
        
        # Terminate processes with all their children
        terminate_process_and_children(gsi_process)
        terminate_process_and_children(django_process)
        
        # Verify ports are released
        time.sleep(1)  # Give some time for ports to be released
        
        if is_port_in_use(8000):
            print("Warning: Port 8000 is still in use!")
        
        if is_port_in_use(3000):
            print("Warning: Port 3000 is still in use!")
            
        print("All servers terminated.")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and start output streaming threads
    django_thread = threading.Thread(
        target=stream_output, 
        args=(django_process, "Django"),
        daemon=True
    )
    
    gsi_thread = threading.Thread(
        target=stream_output, 
        args=(gsi_process, "GSI"),
        daemon=True
    )
    
    django_thread.start()
    gsi_thread.start()

    # Monitor processes and handle process termination
    try:
        while True:
            # Check if either process has terminated
            if django_process.poll() is not None:
                print(f"Django server stopped unexpectedly with code {django_process.returncode}")
                terminate_process_and_children(gsi_process)
                break

            if gsi_process.poll() is not None:
                print(f"GSI server stopped unexpectedly with code {gsi_process.returncode}")
                terminate_process_and_children(django_process)
                break

            # Sleep to reduce CPU usage
            time.sleep(0.5)
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        # Ensure processes are terminated even if there's an exception
        if not is_shutting_down:
            terminate_process_and_children(django_process)
            terminate_process_and_children(gsi_process)
            
            # Verify ports are released
            time.sleep(1)
            if is_port_in_use(8000) or is_port_in_use(3000):
                print("Warning: Some ports are still in use after server termination!")
            else:
                print("All servers terminated and ports released.")

if __name__ == "__main__":
    # Set the Python path to include the backend directory
    sys.path.insert(0, SCRIPT_DIR)

    # Set working directory to script directory
    os.chdir(SCRIPT_DIR)

    run_both_servers()
