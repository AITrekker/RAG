"""
Configuration module for HR RAG Pipeline.

This module provides configuration management and logging setup.
"""

from .settings import (
    Settings,
    AppSettings,
    DatabaseSettings,
    VectorStoreSettings,
    ModelSettings,
    FileProcessingSettings,
    SyncSettings,
    RAGSettings,
    SecuritySettings,
    ResourceSettings,
    LoggingSettings,
    get_settings,
    load_settings,
    reload_settings,
)

from .logging_config import (
    configure_logging,
    setup_logging,
    get_logger,
    RequestContextFilter,
    set_request_context,
)

__all__ = [
    # Settings classes
    "Settings",
    "AppSettings",
    "DatabaseSettings", 
    "VectorStoreSettings",
    "ModelSettings",
    "FileProcessingSettings",
    "SyncSettings",
    "RAGSettings",
    "SecuritySettings",
    "ResourceSettings",
    "LoggingSettings",
    
    # Settings functions
    "get_settings",
    "load_settings", 
    "reload_settings",
    
    # Logging functions
    "configure_logging",
    "setup_logging",
    "get_logger",
    "RequestContextFilter",
    "set_request_context",
] 