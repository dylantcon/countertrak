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
import atexit

# Get the absolute path to the script directory (backend folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Global tracking of processes for cleanup
PROCESSES = []
SHUTTING_DOWN = False
STARTUP_TIMEOUT = 15  # seconds to wait for servers to start
SHUTDOWN_TIMEOUT = 5  # seconds to wait for processes to terminate

DJANGO_PORT = 8000      # configure for .env later
GSI_PORT = 3000         # configure for .env later

def stream_output(process, prefix):
    """
    Stream output from a subprocess with a prefix label.
    This function runs in its own thread to prevent blocking.
    
    Args:
        process: The subprocess.Popen instance to read from
        prefix: The label to add to each line (e.g., "Django" or "GSI")
    """
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                # Print with the prefix and ensure immediate flushing
                print(f"[{prefix}] {line}", end="", flush=True)
    except (IOError, ValueError) as e:
        # Handle pipe errors when process terminates
        print(f"[{prefix}] Output stream closed: {e}", flush=True)

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_processes_by_name(name_pattern):
    """Kill all processes matching a name pattern"""
    killed_count = 0
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if the process matches our target
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if name_pattern in cmdline:
                    print(f"Killing process: {proc.info['pid']} - {cmdline}")
                    psutil.Process(proc.info['pid']).terminate()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Error killing processes: {e}")
    
    return killed_count

def wait_for_port(port, timeout=STARTUP_TIMEOUT):
    """Wait for a port to become active with timeout"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.1)
    return False

def terminate_process_tree(parent_pid):
    """Terminate a process and all its children recursively"""
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
        
        # First send SIGTERM to parent and children
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        parent.terminate()
        
        # Wait for processes to terminate (with timeout)
        gone, alive = psutil.wait_procs(children + [parent], timeout=SHUTDOWN_TIMEOUT)
        
        # If any processes are still alive, send SIGKILL
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        
        return len(gone)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"Error terminating process tree: {e}")
        return 0

def cleanup_all_processes():
    """Clean up all processes at exit"""
    global SHUTTING_DOWN, PROCESSES
    
    if SHUTTING_DOWN:
        return
        
    SHUTTING_DOWN = True
    print("\nCleaning up all server processes...")
    
    # Terminate tracked processes first
    for process in PROCESSES:
        if process and process.poll() is None:  # If process exists and is running
            terminate_process_tree(process.pid)
    
    # Fallback: kill any remaining Django/GSI processes
    killed = kill_processes_by_name('manage.py runserver')
    killed += kill_processes_by_name('gsi/async_server.py')
    
    # Verify ports are released
    time.sleep(1)  # Brief wait for port release
    django_port_free = not is_port_in_use(DJANGO_PORT)
    gsi_port_free = not is_port_in_use(GSI_PORT)
    
    if not django_port_free or not gsi_port_free:
        print("Warning: Some ports are still in use after cleanup!")
        # Force kill any process using these ports as last resort
        if not django_port_free:
            kill_port_process(DJANGO_PORT)
        if not gsi_port_free:
            kill_port_process(GSI_PORT)
    else:
        print("All server ports have been released.")
    
    print(f"Cleanup complete. Killed {killed} additional processes.")

def kill_port_process(port):
    """Forcibly kill any process using a specific port"""
    try:
        # Find process using the port
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == 'LISTEN':
                process = psutil.Process(conn.pid)
                print(f"Force killing process {process.pid} using port {port}")
                process.kill()
                return True
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"Error killing process on port {port}: {e}")
    return False

def run_both_servers():
    """Run both Django and GSI servers with thread-based output handling"""
    global PROCESSES
    
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
        return False

    if not os.path.exists(gsi_server):
        print(f"Error: GSI server not found at {gsi_server}")
        return False
        
    # Check if ports are already in use
    if is_port_in_use(DJANGO_PORT):
        print(f"Error: Port {DJANGO_PORT} is already in use. Django server cannot start.")
        print(f"Attempting to kill the process using port {DJANGO_PORT}...")
        if kill_port_process(DJANGO_PORT):
            print(f"Successfully freed port {DJANGO_PORT}.")
            time.sleep(1)  # Wait for port to fully release
        else:
            print(f"Failed to free port {DJANGO_PORT}. Please stop the process manually.")
            return False
        
    if is_port_in_use(GSI_PORT):
        print(f"Error: Port {GSI_PORT} is already in use. GSI server cannot start.")
        print(f"Attempting to kill the process using port {GSI_PORT}...")
        if kill_port_process(GSI_PORT):
            print(f"Successfully freed port {GSI_PORT}.")
            time.sleep(1)  # Wait for port to fully release
        else:
            print(f"Failed to free port {GSI_PORT}. Please stop the process manually.")
            return False

    # Set up environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # Critical! Ensure unbuffered output
    
    try:
        # Start Django server
        django_cmd = f"{sys.executable} {manage_py} runserver 0.0.0.0:{DJANGO_PORT}"
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
        PROCESSES.append(django_process)
        print(f"Django server starting with PID {django_process.pid}")

        # Wait for Django server to be ready
        if not wait_for_port(DJANGO_PORT):
            print("Error: Django server failed to start within the timeout period")
            cleanup_all_processes()
            return False

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
        PROCESSES.append(gsi_process)
        print(f"GSI server starting with PID {gsi_process.pid}")

        # Wait for GSI server to be ready
        if not wait_for_port(GSI_PORT):
            print("Error: GSI server failed to start within the timeout period")
            cleanup_all_processes()
            return False

        # Function to handle graceful shutdown
        def signal_handler(sig, frame):
            print("\nShutdown signal received...")
            cleanup_all_processes()
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
                django_status = django_process.poll()
                gsi_status = gsi_process.poll()
                
                if django_status is not None:
                    print(f"Django server stopped with code {django_status}")
                    if not SHUTTING_DOWN:
                        cleanup_all_processes()
                    return False

                if gsi_status is not None:
                    print(f"GSI server stopped with code {gsi_status}")
                    if not SHUTTING_DOWN:
                        cleanup_all_processes()
                    return False

                # Periodically verify servers are still responding
                django_alive = is_port_in_use(DJANGO_PORT)
                gsi_alive = is_port_in_use(GSI_PORT)
                
                if not django_alive and django_status is None:
                    print("Warning: Django server port is not responding but process is running")
                    # Attempt to restart if needed
                
                if not gsi_alive and gsi_status is None:
                    print("Warning: GSI server port is not responding but process is running")
                    # Attempt to restart if needed

                # Sleep to reduce CPU usage
                time.sleep(2)
                
        except Exception as e:
            print(f"Error in main monitoring loop: {e}")
            if not SHUTTING_DOWN:
                cleanup_all_processes()
            return False
            
    except Exception as e:
        print(f"Error starting servers: {e}")
        if not SHUTTING_DOWN:
            cleanup_all_processes()
        return False

# Register cleanup at exit
atexit.register(cleanup_all_processes)

if __name__ == "__main__":
    # Set the Python path to include the backend directory
    sys.path.insert(0, SCRIPT_DIR)

    # Set working directory to script directory
    os.chdir(SCRIPT_DIR)

    # Start the servers
    success = run_both_servers()
    
    # If servers didn't start successfully, make sure we exit with error code
    if not success and not SHUTTING_DOWN:
        cleanup_all_processes()
        sys.exit(1)
