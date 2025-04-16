#!/usr/bin/env python
"""
CounterTrak Debug Runner - Runs servers in the same process for better logging
"""
import os
import sys
import asyncio
import threading
import time
import signal

# Get the absolute path to the script directory (backend folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
os.chdir(SCRIPT_DIR)

# Configure Python environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')
os.environ["PYTHONUNBUFFERED"] = "1"

def run_django_server():
    """Run Django development server"""
    print("Starting Django server...")
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])

def run_gsi_server():
    """Run GSI server"""
    print("Starting GSI server...")
    asyncio.run(run_gsi_async())

async def run_gsi_async():
    """Run the GSI server using asyncio"""
    from gsi.async_server import main
    await main()

def main():
    """Run both servers in separate threads"""
    print("Starting CounterTrak Debug Server...")
    
    # Start Django in a separate thread
    django_thread = threading.Thread(target=run_django_server)
    django_thread.daemon = True
    django_thread.start()
    
    # Run GSI server in the main thread
    try:
        run_gsi_server()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        sys.exit(0)

if __name__ == "__main__":
    main()
