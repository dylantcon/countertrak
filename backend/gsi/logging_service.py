"""
Centralized logging service for CounterTrak with color support
"""
import logging
import os
import sys
from datetime import datetime
import colorlog

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

# Color definitions
COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}

def get_colored_logger(name, highlight_color=None):
    """
    Get a logger with colored output.
    
    Args:
        name: The name of the logger
        highlight_color: Optional color to highlight all logs (e.g., 'light_red')
        
    Returns:
        A configured logger with colored output
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist
    if logger.handlers:
        return logger
    
    # Create color formatter
    formatter_colors = COLORS.copy()
    if highlight_color:
        # Override all colors with the highlight color if specified
        for level in formatter_colors:
            formatter_colors[level] = highlight_color
    
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        log_colors=formatter_colors,
        secondary_log_colors={},
        style='%'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Create file handler with standard formatter (no colors)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler('countertrak.log')
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False  # Prevent duplicate logs in parent loggers
    
    return logger

# Create a special highlight logger (light red)
highlight_logger = get_colored_logger('highlight', 'light_red')

def log_to_file(message, level=logging.INFO, logger_name='gsi'):
    """
    Write a log message to a file regardless of logger configuration
    This ensures we capture logs even if something is wrong with the logger
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('debug.log', 'a') as f:
        f.write(f"{timestamp} - {logger_name} - {level} - {message}\n")

# Export the loggers and functions for use in other modules
__all__ = [
    'gsi_logger', 'match_manager_logger', 'match_processor_logger', 
    'payload_logger', 'highlight_logger', 'get_colored_logger', 'log_to_file'
]
