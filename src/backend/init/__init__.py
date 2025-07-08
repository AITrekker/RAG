"""
Backend initialization module.

This module contains critical infrastructure code for initializing
the RAG system, including database setup and admin tenant creation.

This code is executed by the init container during deployment and
is essential for the system to function properly.
"""

from .container import main as run_init_container

__all__ = ["run_init_container"]