"""
Centralized logging service for CounterTrak
"""
import logging
import os
import sys
from datetime import datetime

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('countertrak.log')
    ]
)

# Create named loggers for different components
gsi_logger = logging.getLogger('gsi')
match_manager_logger = logging.getLogger('match_manager')
match_processor_logger = logging.getLogger('match_processor')
payload_logger = logging.getLogger('payload')

# Make sure all loggers propagate to the root logger
for logger in [gsi_logger, match_manager_logger, match_processor_logger, payload_logger]:
    logger.propagate = True
    
def log_to_file(message, level=logging.INFO, logger_name='gsi'):
    """
    Write a log message to a file regardless of logger configuration
    This ensures we capture logs even if something is wrong with the logger
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('debug.log', 'a') as f:
        f.write(f"{timestamp} - {logger_name} - {level} - {message}\n")

# Export the loggers for use in other modules
__all__ = ['gsi_logger', 'match_manager_logger', 'match_processor_logger', 
           'payload_logger', 'log_to_file']
