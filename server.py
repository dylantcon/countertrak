from http.server import BaseHTTPRequestHandler, HTTPServer
from operator import attrgetter
from threading import Thread
import json
import logging
import payloadextractor

from datetime import datetime

# Configure logging with both file and console output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gsi_server.log'),
        logging.StreamHandler()
    ]
)

class GSIServer(HTTPServer):
    def __init__(self, server_address, auth_token):
        super().__init__(server_address, RequestHandler)
        self.auth_token = auth_token
        self.running = False
        self.extractor = payloadextractor.PayloadExtractor()
        logging.info(f"Server initialized with address {server_address}")
        logging.info(f"Auth token configured: {auth_token}")

    def start_server(self):
        try:
            thread = Thread(target=self.serve_forever)
            thread.start()
            first_time = True
            while not self.running:
                if first_time:
                    logging.info("CS2 GSI Server starting...")
                first_time = False
            logging.info("Server is now running and receiving data")
        except Exception as e:
            logging.error(f"Could not start server: {str(e)}")
            raise

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers["Content-Length"])
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)

            if not self.authenticate_payload(payload):
                return False

            if not self.server.running:
                self.server.running = True
                logging.info( "Server now running" )

            self.server.extractor.monitor_state_changes( payload )

        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON payload: {str(e)}")
            return False
        except UnboundLocalError:
            return False
        except KeyboardInterrupt:
            return False
        except Exception as e:
            logging.error(f"Unexpected error processing POST: {str(e)}")
            return False

    def authenticate_payload(self, payload):
        try:
            if "auth" in payload and "token" in payload["auth"]:
                is_valid = payload["auth"]["token"] == self.server.auth_token
                return is_valid
            logging.warning("Payload missing auth token")
            return False
        except Exception as e:
            logging.error(f"Error during authentication: {str(e)}")
            return False

def main():
    try:
        # Server configuration
        HOST = "127.0.0.1"
        PORT = 3000
        AUTH_TOKEN = "S8RL9Z6Y22TYQK45JB4V8PHRJJMD9DS9"  # Match your .cfg file, doesn't have
							 # to be specially hashed or anything
        logging.info("Starting CS2 GSI Server...")
        
        server = GSIServer((HOST, PORT), AUTH_TOKEN)
        logging.info(f"Server listening on {HOST}:{PORT}")

        server.start_server()
        logging.info("Server started successfully. Waiting for CS2 GSI updates...")

        # Keep main thread alive while handling KeyboardInterrupt gracefully
        try:
            while True:
                pass
        except KeyboardInterrupt:
            logging.info("Server shutdown requested via KeyboardInterrupt")
            server.server_close()
            logging.info("Server has completed shutdown")
            exit(0)

    except Exception as e:
        logging.error(f"Unexpected error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
