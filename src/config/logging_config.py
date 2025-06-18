"""
Logging configuration for HR RAG Pipeline.

This module sets up structured logging with file rotation, console output,
and configurable log levels and formats.
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional, Union
import json
from datetime import datetime

def create_log_directory(log_path: str) -> None:
    """
    Create log directory if it doesn't exist.
    
    Args:
        log_path: Path to log file
    """
    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

def get_log_level(level_str: str) -> int:
    """
    Convert string log level to logging constant.
    
    Args:
        level_str: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Logging level constant
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str.upper(), logging.INFO)

def create_file_handler(
    file_path: str,
    max_size_mb: int = 100,
    backup_count: int = 5,
    rotation: str = "size",
    rotation_interval: str = "daily"
) -> logging.Handler:
    """
    Create file handler with rotation.
    
    Args:
        file_path: Path to log file
        max_size_mb: Maximum file size in MB for size rotation
        backup_count: Number of backup files to keep
        rotation: Rotation type ('size' or 'time')
        rotation_interval: Interval for time rotation ('daily', 'weekly', 'monthly')
        
    Returns:
        Configured file handler
    """
    create_log_directory(file_path)
    
    if rotation == "size":
        handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
    elif rotation == "time":
        # Map rotation intervals to when parameter
        interval_map = {
            "daily": "D",
            "weekly": "W0",  # Monday
            "monthly": "midnight"
        }
        when = interval_map.get(rotation_interval, "D")
        
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=file_path,
            when=when,
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
    else:
        # Fallback to basic file handler
        handler = logging.FileHandler(file_path, encoding='utf-8')
    
    return handler

def create_console_handler() -> logging.Handler:
    """
    Create console handler for stdout output.
    
    Returns:
        Configured console handler
    """
    handler = logging.StreamHandler(sys.stdout)
    return handler

class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured JSON logging.
    """
    
    def __init__(
        self,
        include_timestamp: bool = True,
        include_level: bool = True,
        include_module: bool = True,
        include_function: bool = True,
        include_line_number: bool = True,
        include_request_id: bool = True
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_level = include_level
        self.include_module = include_module
        self.include_function = include_function
        self.include_line_number = include_line_number
        self.include_request_id = include_request_id
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        log_data: Dict[str, Any] = {
            "message": record.getMessage(),
        }
        
        if self.include_timestamp:
            log_data["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
        
        if self.include_level:
            log_data["level"] = record.levelname
        
        if self.include_module:
            log_data["module"] = record.module
        
        if self.include_function:
            log_data["function"] = record.funcName
        
        if self.include_line_number:
            log_data["line"] = record.lineno
        
        # Add request ID if available (from context)
        if self.include_request_id and hasattr(record, 'request_id'):
            log_data["request_id"] = getattr(record, 'request_id', None)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        extra_fields: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info', 'message'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_data["extra"] = extra_fields
        
        return json.dumps(log_data, default=str, ensure_ascii=False)

class SimpleFormatter(logging.Formatter):
    """
    Simple text formatter for console output.
    """
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

def configure_logging(
    level: str = "INFO",
    format_type: str = "structured",
    output: str = "both",
    file_path: str = "./logs/hr_rag.log",
    file_max_size_mb: int = 100,
    file_backup_count: int = 5,
    file_rotation: str = "time",
    file_rotation_interval: str = "daily",
    structured_config: Optional[Dict[str, bool]] = None
) -> None:
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ('structured' or 'simple')
        output: Output destination ('file', 'console', 'both')
        file_path: Path to log file
        file_max_size_mb: Maximum file size in MB
        file_backup_count: Number of backup files
        file_rotation: Rotation type ('size' or 'time')
        file_rotation_interval: Interval for time rotation
        structured_config: Configuration for structured logging
    """
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Set log level
    log_level = get_log_level(level)
    root_logger.setLevel(log_level)
    
    # Default structured config
    if structured_config is None:
        structured_config = {
            "include_timestamp": True,
            "include_level": True,
            "include_module": True,
            "include_function": True,
            "include_line_number": True,
            "include_request_id": True,
        }
    
    # Create formatters
    if format_type == "structured":
        formatter = StructuredFormatter(**structured_config)
    else:
        formatter = SimpleFormatter()
    
    # Add file handler
    if output in ["file", "both"]:
        file_handler = create_file_handler(
            file_path=file_path,
            max_size_mb=file_max_size_mb,
            backup_count=file_backup_count,
            rotation=file_rotation,
            rotation_interval=file_rotation_interval
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Add console handler
    if output in ["console", "both"]:
        console_handler = create_console_handler()
        console_handler.setLevel(log_level)
        
        # Use simple formatter for console even if structured is requested
        console_formatter = SimpleFormatter() if format_type == "structured" else formatter
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Disable some noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    
    # Log configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {level}, Format: {format_type}, Output: {output}")

def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

class RequestContextFilter(logging.Filter):
    """
    Filter to add request context to log records.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request context to log record.
        
        Args:
            record: Log record to modify
            
        Returns:
            True to include record, False to exclude
        """
        # Try to get request ID from context (would be set by middleware)
        # This is a placeholder - actual implementation would depend on framework
        if not hasattr(record, 'request_id'):
            setattr(record, 'request_id', getattr(self, '_request_id', None))
        
        return True

def set_request_context(request_id: str) -> None:
    """
    Set request context for logging.
    
    Args:
        request_id: Unique request identifier
    """
    # This would typically be called by middleware
    # Implementation depends on the web framework used
    pass

def setup_logging(settings: Optional[Dict[str, Any]] = None) -> None:
    """
    Setup logging with configuration from settings.
    
    Args:
        settings: Logging configuration settings
    """
    if settings is None:
        settings = {}
    
    configure_logging(
        level=settings.get("level", "INFO"),
        format_type=settings.get("format", "structured"),
        output=settings.get("output", "both"),
        file_path=settings.get("file_path", "./logs/hr_rag.log"),
        file_max_size_mb=settings.get("file_max_size_mb", 100),
        file_backup_count=settings.get("file_backup_count", 5),
        file_rotation=settings.get("file_rotation", "time"),
        file_rotation_interval=settings.get("file_rotation_interval", "daily"),
        structured_config=settings.get("structured_config")
    )

# Export commonly used functions
__all__ = [
    "configure_logging",
    "setup_logging",
    "get_logger",
    "RequestContextFilter",
    "set_request_context",
    "StructuredFormatter",
    "SimpleFormatter",
] 