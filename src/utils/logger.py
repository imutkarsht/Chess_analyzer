import logging
import sys

def setup_logging():
    """
    Configures the global logging setup.
    """
    # Create a custom logger
    logger = logging.getLogger("ChessAnalyzer")
    logger.setLevel(logging.DEBUG)

    # Create handlers
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.DEBUG)

    # Create formatters and add it to handlers
    c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)

    # Add handlers to the logger
    if not logger.handlers:
        logger.addHandler(c_handler)

    return logger

# Global logger instance
logger = setup_logging()
