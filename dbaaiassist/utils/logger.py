import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

class AppLogger:
    """
    A utility class for application logging.
    Provides logging to both console and file with different log levels.
    """
    
    def __init__(self, name="dbaaiassist", log_level=logging.DEBUG):
        """
        Initialize the logger with the given name and log level.
        
        Args:
            name: The name of the logger
            log_level: The minimum log level to record
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False
        
        # Create logs directory if it doesn't exist
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Create a unique log file name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{name}_{timestamp}.log"
        
        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        # Create formatter and add to handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def debug(self, message):
        """Log a debug message."""
        self.logger.debug(message)
    
    def info(self, message):
        """Log an info message."""
        self.logger.info(message)
    
    def warning(self, message):
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message, exc_info=False):
        """
        Log an error message, optionally with exception info.
        
        Args:
            message: The error message
            exc_info: Whether to include exception info
        """
        self.logger.error(message, exc_info=exc_info)
    
    def exception(self, message):
        """
        Log an exception message with traceback.
        
        Args:
            message: The exception message
        """
        self.logger.exception(message)
    
    def critical(self, message):
        """Log a critical message."""
        self.logger.critical(message)
    
    @staticmethod
    def get_logger(name="dbaaiassist", log_level=logging.DEBUG):
        """
        Get a logger instance.
        
        Args:
            name: The name of the logger
            log_level: The minimum log level to record
            
        Returns:
            An AppLogger instance
        """
        return AppLogger(name, log_level)


# Default logger instance
app_logger = AppLogger.get_logger()

def get_logger(name="dbaaiassist", log_level=logging.DEBUG):
    """
    Get a logger instance.
    
    Args:
        name: The name of the logger
        log_level: The minimum log level to record
        
    Returns:
        An AppLogger instance
    """
    return AppLogger.get_logger(name, log_level)

def log_exception(func):
    """
    A decorator to log exceptions in functions.
    
    Args:
        func: The function to decorate
        
    Returns:
        The decorated function
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            app_logger.error(f"Exception in {func.__name__}: {str(e)}")
            app_logger.error(traceback.format_exc())
            raise
    return wrapper