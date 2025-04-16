"""
CounterTrak Asynchronous GSI Server

Handles HTTP POST requests from CS2 Game State Integration.
"""
import time
import os
import asyncio
import json
import sys
from aiohttp import web
from typing import Dict, Optional

# Add the parent directory to sys.path to enable imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from gsi.logging_service import gsi_logger as logger, payload_logger, log_to_file
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')
import django
from gsi.match_manager import MatchManager

class GSIServer:
    """
    Asynchronous Game State Integration server for CS2.
    Receives payloads from multiple CS2 clients and routes them
    to the appropriate match processors.
    """
    
    def __init__(self, host: str, port: int, auth_token: str):
        """
        Initialize the GSI server.
        
        Args:
            host: The host address to bind to
            port: The port to listen on
            auth_token: The auth token to validate GSI payloads
        """
        init_start = time.time()
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.app = web.Application()
        self.running = False
        
        # Initialize the match manager - per original architecture
        self.match_manager = MatchManager()
        
        # Set up routes
        self.app.router.add_post('/', self.handle_gsi_payload)
        self.app.router.add_get('/status', self.handle_status)
        
        init_time = time.time() - init_start
        logger.info(f"GSI Server initialized with address {host}:{port} in {init_time:.3f}s")
        logger.info(f"Auth token configured: {auth_token}")
    
    async def handle_gsi_payload(self, request: web.Request) -> web.Response:
        """
        Handle incoming GSI payloads from CS2 clients.
        
        Args:
            request: The HTTP request containing the GSI payload
            
        Returns:
            An HTTP response
        """
        try:
            # Log the request details
            client_ip = request.remote
            
            # Read and parse the payload
            payload_start = time.time()
            payload = await request.json()
            
            # Authenticate the payload
            if not self._authenticate_payload(payload):
                logger.warning(f"Unauthorized payload received from {client_ip}")
                return web.Response(status=401, text="Unauthorized")
            
            # Log basic payload info for debugging
            if 'provider' in payload and 'player' in payload:
                owner_id = payload['provider'].get('steamid', 'unknown')
                player_id = payload['player'].get('steamid', 'unknown')
                player_name = payload['player'].get('name', 'unknown')
                activity = payload['player'].get('activity', 'unknown')
            
            # Set running flag if first request
            if not self.running:
                self.running = True
                logger.info("Server is now receiving data")
            
            # Process the payload through the match manager
            process_start = time.time()
            await self.match_manager.process_payload(payload)
            
            # Log HTTP access info
            logger.info(f"{client_ip} - POST / HTTP/1.1 200 OK")
            
            # Return 200 OK with a short response body
            return web.Response(status=200, text="OK")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON payload: {str(e)}")
            return web.Response(status=400, text="Invalid JSON")
        except Exception as e:
            logger.error(f"Unexpected error processing request: {str(e)}")
            return web.Response(status=500, text="Internal Server Error")
    
    async def handle_status(self, request: web.Request) -> web.Response:
        """
        Handle status requests to check if server is running.
        
        Args:
            request: The HTTP request
            
        Returns:
            An HTTP response with server status
        """
        status = {
            "running": self.running,
            "active_matches": self.match_manager.get_active_match_count(),
            "uptime": "N/A"  # TODO: Implement uptime tracking
        }
        return web.json_response(status)
    
    def _authenticate_payload(self, payload: Dict) -> bool:
        """
        Authenticate the payload using the auth token.
        
        Args:
            payload: The GSI payload
            
        Returns:
            True if payload is authenticated, False otherwise
        """
        try:
            if "auth" in payload and "token" in payload["auth"]:
                is_valid = payload["auth"]["token"] == self.auth_token
                return is_valid
            logger.warning("Payload missing auth token")
            return False
        except Exception as e:
            logger.error(f"Error during authentication: {str(e)}")
            return False
    
    async def start(self):
        """
        Start the GSI server.
        """
        start_time = time.time()
        
        # Set up the AIOHTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Server startup completed in {time.time() - start_time:.3f}s")
        logger.info(f"Server running at http://{self.host}:{self.port}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Keep alive

async def main():
    """
    Main entry point for the server.
    """
    try:
        main_start = time.time()
        logger.info("Starting CounterTrak Async GSI Server...")
        
        # Server configuration - hardcoded for now
        HOST = "0.0.0.0"
        PORT = 3000
        AUTH_TOKEN = "S8RL9Z6Y22TYQK45JB4V8PHRJJMD9DS9"  # Match .cfg file
        
        server = GSIServer(HOST, PORT, AUTH_TOKEN)
        await server.start()
        
    except asyncio.CancelledError:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        script_start = time.time()
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via KeyboardInterrupt")
    finally:
        logger.info(f"Total script execution time: {time.time() - script_start:.3f}s")
