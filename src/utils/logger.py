import logging
import sys
import os

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
    
    # File handler
    try:
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.abspath(".")
            
        log_file = os.path.join(app_dir, "chess_analyzer.log")
        f_handler = logging.FileHandler(log_file, mode='w')
        f_handler.setLevel(logging.DEBUG)
        
        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)
        
        # Add handlers to the logger
        if not logger.handlers:
            logger.addHandler(c_handler)
            logger.addHandler(f_handler)
            
    except Exception as e:
        # Fallback if file logging fails
        print(f"Failed to setup file logging: {e}")
        if not logger.handlers:
            logger.addHandler(c_handler)

    return logger

# Global logger instance
logger = setup_logging()
