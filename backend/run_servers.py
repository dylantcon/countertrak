"""
CounterTrak Server Runner - Runs Both Django and GSI server (async_server.py)
Run via: python ./async_server.py
"""
import os
import sys
import subprocess
import signal
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')

def run_both_servers():
    """Run both Django and GSI servers"""
    print("Starting CounterTrak servers...")
    
    # Start Django server
    django_cmd = [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"]
    django_process = subprocess.Popen(
        django_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print(f"Django server started with PID {django_process.pid}")
    time.sleep(2)
    
    # Start GSI server
    gsi_cmd = [sys.executable, "gsi/async_server.py"]
    gsi_process = subprocess.Popen(
        gsi_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
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
    
    # Print output from both processes
    try:
        while True:
            django_line = django_process.stdout.readline()
            if django_line:
                print(f"[Django] {django_line}", end="")
            
            gsi_line = gsi_process.stdout.readline()
            if gsi_line:
                print(f"[GSI] {gsi_line}", end="")
            
            # Check if either process has terminated
            if django_process.poll() is not None:
                print(f"Django server stopped unexpectedly with code {django_process.returncode}")
                break
            
            if gsi_process.poll() is not None:
                print(f"GSI server stopped unexpectedly with code {gsi_process.returncode}")
                break
            
            time.sleep(0.1)
    finally:
        django_process.terminate()
        gsi_process.terminate()

if __name__ == "__main__":
    run_both_servers()
