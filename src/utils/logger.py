"""
Logging utility module for MessageCannon application.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    """Manages logging configuration and provides logger instances."""
    
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls) -> 'Logger':
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize logger with file and console handlers."""
        if Logger._logger is not None:
            return
        
        # Create logs directory
        log_dir = Path.home() / ".messagecannon" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        Logger._logger = logging.getLogger("MessageCannon")
        Logger._logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        Logger._logger.handlers.clear()
        
        # File handler
        log_file = log_dir / f"messagecannon_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        Logger._logger.addHandler(file_handler)
        Logger._logger.addHandler(console_handler)
    
    @staticmethod
    def get_logger() -> logging.Logger:
        """Get the logger instance."""
        if Logger._logger is None:
            Logger()
        return Logger._logger
    
    @staticmethod
    def debug(message: str, *args, **kwargs) -> None:
        """Log debug message."""
        Logger.get_logger().debug(message, *args, **kwargs)
    
    @staticmethod
    def info(message: str, *args, **kwargs) -> None:
        """Log info message."""
        Logger.get_logger().info(message, *args, **kwargs)
    
    @staticmethod
    def warning(message: str, *args, **kwargs) -> None:
        """Log warning message."""
        Logger.get_logger().warning(message, *args, **kwargs)
    
    @staticmethod
    def error(message: str, *args, **kwargs) -> None:
        """Log error message."""
        Logger.get_logger().error(message, *args, **kwargs)
    
    @staticmethod
    def critical(message: str, *args, **kwargs) -> None:
        """Log critical message."""
        Logger.get_logger().critical(message, *args, **kwargs)


# Convenience functions
def get_logger() -> logging.Logger:
    """Get logger instance."""
    return Logger.get_logger()
