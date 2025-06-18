"""
Logger configuration for the application.
"""
import os
import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = 'social_media_publisher',
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    Set up a logger with the specified configuration.
    
    Args:
        name: Logger name
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: None)
        console: Whether to log to console (default: True)
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Clear existing handlers
    logger.handlers = []
    
    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Add file handler if log file is specified
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_default_logger() -> logging.Logger:
    """
    Get the default logger for the application.
    
    Returns:
        Default logger
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create log file with current date
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(logs_dir, f'social_media_publisher_{today}.log')
    
    return setup_logger(log_file=log_file)