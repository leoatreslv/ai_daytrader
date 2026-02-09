import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file="trading_system.log", level=logging.INFO):
    """
    Setup a logger that writes to a file and the console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if handlers are already added to avoid duplicates
    if not logger.handlers:
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # File Handler (Rotating)
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    return logger
