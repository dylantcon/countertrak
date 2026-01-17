"""
CounterTrak Asynchronous GSI Server

Handles HTTP POST requests from CS2 Game State Integration.
"""
import time
import os
import asyncio
import json
import sys
import django
from aiohttp import web
from typing import Dict, Optional, Set, Tuple
from django.db import connection
from asgiref.sync import sync_to_async

# add the parent directory to sys.path to enable imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from gsi.logging_service import gsi_logger as logger, payload_logger, log_to_file
from gsi.match_manager import MatchManager

# Configure Django for async database operations
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'countertrak.settings')
django.setup()

# Import after Django setup
from apps.accounts.models import SteamAccount

class TokenCache:
    """
    Manages a cache of valid authentication tokens for improved performance.
    
    This cache reduces database load by storing valid auth tokens in memory
    and providing methods to update/refresh the cache when tokens change.
    """
    
    def __init__(self):
        # Dictionary mapping auth tokens to steam_ids
        self.tokens = {}
        # Last refresh timestamp
        self.last_refresh = 0
        # Refresh interval in seconds (10 minutes)
        self.refresh_interval = 600
        # Initialization flag
        self.initialized = False
        # Lock for thread-safe cache updates
        self.lock = asyncio.Lock()
        
        logger.info("Token cache initialized")
    
    async def initialize(self):
        """Load all valid tokens from the database on server startup."""
        async with self.lock:
            if self.initialized:
                return
                
            try:
                # Query all Steam accounts with valid tokens
                tokens = await self._get_all_tokens()
                
                # Store in the cache
                self.tokens = tokens
                self.last_refresh = time.time()
                self.initialized = True
                
                logger.info(f"Token cache initialized with {len(self.tokens)} tokens")
            except Exception as e:
                logger.error(f"Error initializing token cache: {str(e)}")
                # Initialize with empty dict to avoid repeated failures
                self.tokens = {}
                self.initialized = True
    
    async def is_valid_token(self, token: str) -> bool:
        """
        Check if a token is valid using the cache.
        
        Args:
            token: The auth token to validate
            
        Returns:
            True if the token is valid, False otherwise
        """
        # Initialize cache if needed
        if not self.initialized:
            await self.initialize()
        
        # Check if token exists in cache
        if token in self.tokens:
            return True
        
        # If cache might be outdated, refresh and check again
        if time.time() - self.last_refresh > self.refresh_interval:
            await self.refresh()
            return token in self.tokens
            
        return False

    async def get_steam_id(self, token: str) -> Optional[str]:
        """
        Get the steam_id associated with a token.
        
        Args:
            token: The auth token
            
        Returns:
            The steam_id or None if token is invalid
        """
        # Initialize cache if needed
        if not self.initialized:
            await self.initialize()
            
        # Return steam_id from cache
        return self.tokens.get(token)
    
    async def refresh(self):
        """Refresh the token cache from the database."""
        async with self.lock:
            try:
                # Query all Steam accounts with valid tokens
                tokens = await self._get_all_tokens()
                
                # Update the cache
                self.tokens = tokens
                self.last_refresh = time.time()
                
                logger.info(f"Token cache refreshed with {len(self.tokens)} tokens")
            except Exception as e:
                logger.error(f"Error refreshing token cache: {str(e)}")
    
    async def register_legacy_token(self, token: str):
        """
        Register a legacy fallback token for migration purposes.
        
        Args:
            token: The legacy token to accept
        """
        if token and token not in self.tokens:
            async with self.lock:
                self.tokens[token] = "LEGACY_TOKEN"
                logger.warning("Legacy fallback token registered - this should be phased out")
    
    @sync_to_async
    def _get_all_tokens(self) -> Dict[str, str]:
        """
        Synchronous method to get all valid tokens from the database.
        
        Returns:
            Dictionary mapping auth tokens to steam_ids
        """
        # Use a raw SQL query for efficiency
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT auth_token, steam_id FROM accounts_steamaccount WHERE auth_token IS NOT NULL"
            )
            # Create dictionary mapping token -> steam_id
            return {row[0]: row[1] for row in cursor.fetchall()}

class GSIServer:
    """
    Asynchronous Game State Integration server for CS2.
    Receives payloads from multiple CS2 clients and routes them
    to the appropriate match processors.
    """
    
    def __init__(self, host: str, port: int):
        """
        Initialize the GSI server.
        
        Args:
            host: The host address to bind to
            port: The port to listen on
        """
        init_start = time.time()
        self.host = host
        self.port = port
        self.app = web.Application()
        self.running = False
        
        # Initialize the token cache
        self.token_cache = TokenCache()
        
        # Initialize the match manager
        self.match_manager = MatchManager()
        
        # Set up routes
        self.app.router.add_post('/', self.handle_gsi_payload)
        self.app.router.add_get('/status', self.handle_status)
        
        init_time = time.time() - init_start
        logger.info(f"GSI Server initialized with address {host}:{port} in {init_time:.3f}s")
    
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
            auth_result = await self._authenticate_payload(payload)
            
            if not auth_result[0]:
                logger.warning(f"Unauthorized payload received from {client_ip}")
                return web.Response(status=401, text="Unauthorized")
            
            # Get steam_id if available (from token cache)
            steam_id = auth_result[1]
            
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
            await self.match_manager.route_payload(payload)
            
            # Log http access info
            logger.info(f"{client_ip} - POST / HTTP/1.1 200 OK")
            
            # Return 200 ok with a short response body
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
            "token_cache": {
                "initialized": self.token_cache.initialized,
                "token_count": len(self.token_cache.tokens),
                "last_refresh": self.token_cache.last_refresh,
                "cache_age": time.time() - self.token_cache.last_refresh if self.token_cache.last_refresh > 0 else 0
            },
            "uptime": "N/A"  # You could implement uptime tracking if desired
        }
        return web.json_response(status)
    
    async def _authenticate_payload(self, payload: Dict) -> Tuple[bool, Optional[str]]:
        """
        Authenticate the payload using the token cache.
        
        Args:
            payload: The GSI payload
            
        Returns:
            Tuple of (is_valid, steam_id)
        """
        try:
            if "auth" in payload and "token" in payload["auth"]:
                token = payload["auth"]["token"]
                
                # Validate against token cache
                if await self.token_cache.is_valid_token(token):
                    # Get associated steam_id if available
                    steam_id = await self.token_cache.get_steam_id(token)
                    return True, steam_id
                
                logger.warning(f"Invalid auth token: {token}")
                return False, None
                
            logger.warning("Payload missing auth token")
            return False, None
        except Exception as e:
            logger.error(f"Error during authentication: {str(e)}")
            return False, None
    
    async def start(self):
        """
        Start the GSI server.
        """
        start_time = time.time()
        
        # Initialize the token cache
        await self.token_cache.initialize()
        
        # Set up the aiohttp server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Server startup completed in {time.time() - start_time:.3f}s")
        logger.info(f"Server running at http://{self.host}:{self.port}")
        
        # Start a periodic token cache refresh task
        asyncio.create_task(self._periodic_cache_refresh())
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # keep alive

    async def _periodic_cache_refresh(self):
        """Periodically refresh the token cache."""
        while True:
            await asyncio.sleep(self.token_cache.refresh_interval)
            await self.token_cache.refresh()

async def main():
    """Main entry point for the server."""
    try:
        main_start = time.time()
        logger.info("Starting CounterTrak Async GSI Server...")
        
        # Server configuration
        HOST = os.getenv('GSI_HOST', "0.0.0.0")
        PORT = int(os.getenv('GSI_PORT', 3000))
        
        # Create GSI server with no hardcoded auth token
        server = GSIServer(HOST, PORT)
        
        # Handle legacy token for migration period
        legacy_token = os.getenv('GSI_LEGACY_TOKEN')
        if legacy_token:
            logger.warning("Legacy fallback token configured - this should be phased out")
            await server.token_cache.register_legacy_token(legacy_token)
        
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
