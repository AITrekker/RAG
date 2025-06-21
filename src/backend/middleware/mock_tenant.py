"""
Mock tenant context for demo purposes.
In production, this would be replaced with proper tenant authentication.
"""

from typing import Optional


async def get_current_tenant_id() -> str:
    """Mock function to return default tenant ID for demo."""
    return "default"


async def get_optional_tenant_id() -> Optional[str]:
    """Mock function to return optional tenant ID for demo."""
    return "default" 