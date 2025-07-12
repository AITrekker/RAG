"""
Backend startup and initialization modules.

This package contains all startup logic for the RAG backend:
- Dependency verification (PostgreSQL)
- Database schema verification
- Admin tenant verification
- Health checks

This keeps startup logic within the backend codebase and
separate from operational scripts.
"""

from .dependencies import wait_for_dependencies
from .verification import verify_system_requirements

__all__ = [
    "wait_for_dependencies",
    "verify_system_requirements"
]