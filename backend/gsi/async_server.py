"""
CounterTrak Asynchronous GSI Server

An asynchronous implementation of the CS2 Game State Integration server 
using aiohttp for high concurrency handling of multiple game clients.
"""

import asyncio
import logging
import json
import uuid
import os
import sys
from aiohttp import web
from typing import Dict, Optional

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('async_gsi_server.log'),
        logging.StreamHandler()
    ]
)

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Django and set it up
import django
django.setup()

# Now we can import Django models
from apps.matches.models import Match, Round
from apps.stats.models import PlayerRoundState, PlayerWeapon, PlayerMatchStat, Weapon
from apps.accounts.models import SteamAccount

# Import the payload extractor
from gsi.match_processor import MatchProcessor
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
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.app = web.Application()
        self.running = False
        
        # Initialize the match manager
        self.match_manager = MatchManager()
        
        # Set up routes
        self.app.router.add_post('/', self.handle_gsi_payload)
        self.app.router.add_get('/status', self.handle_status)
        
        logging.info(f"GSI Server initialized with address {host}:{port}")
        logging.info(f"Auth token configured: {auth_token}")
    
    async def handle_gsi_payload(self, request: web.Request) -> web.Response:
        """
        Handle incoming GSI payloads from CS2 clients.
        
        Args:
            request: The HTTP request containing the GSI payload
            
        Returns:
            An HTTP response
        """
        try:
            # Read and parse the payload
            payload = await request.json()
            
            # Authenticate the payload
            if not self._authenticate_payload(payload):
                return web.Response(status=401, text="Unauthorized")
            
            # Set running flag if first request
            if not self.running:
                self.running = True
                logging.info("Server is now receiving data")
            
            # Log payload structure for debugging
            if 'provider' in payload and 'player' in payload:
                owner_id = payload['provider'].get('steamid', 'unknown')
                player_id = payload['player'].get('steamid', 'unknown')
                player_name = payload['player'].get('name', 'unknown')

                logging.debug(f"Received payload from client {owner_id}, player data: {player_name} ({player_id})")
            
            # Process the payload through the match manager
            await self.match_manager.process_payload(payload)
            
            # Return 200 OK with a short response body
            return web.Response(status=200, text="OK")
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON payload: {str(e)}")
            return web.Response(status=400, text="Invalid JSON")
        except Exception as e:
            logging.error(f"Unexpected error processing request: {str(e)}")
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
            logging.warning("Payload missing auth token")
            return False
        except Exception as e:
            logging.error(f"Error during authentication: {str(e)}")
            return False
    
    async def start(self):
        """
        Start the GSI server.
        """
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logging.info(f"Server running at http://{self.host}:{self.port}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Keep alive

async def main():
    """
    Main entry point for the server.
    """
    try:
        # Server configuration - hardcoded for now
        HOST = "0.0.0.0"
        PORT = 3000
        AUTH_TOKEN = "S8RL9Z6Y22TYQK45JB4V8PHRJJMD9DS9"  # Match .cfg file
        
        logging.info("Starting CounterTrak Async GSI Server...")
        
        server = GSIServer(HOST, PORT, AUTH_TOKEN)
        await server.start()
        
    except asyncio.CancelledError:
        logging.info("Server shutdown requested")
    except Exception as e:
        logging.error(f"Unexpected error in main: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server shutdown requested via KeyboardInterrupt")
