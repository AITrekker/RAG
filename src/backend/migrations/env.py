from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config, MetaData
from sqlalchemy import pool
from alembic import context

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# Import all models and their bases
from src.backend.models.database import Base as AppBase
from src.backend.models.tenant import Base as TenantBase
from src.backend.models.document import Base as DocumentBase
from src.backend.models.audit import Base as AuditBase

from src.backend.config.settings import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Autogenerate configuration ---
# Combine metadata from all bases into a single MetaData object
# This allows Alembic to see tables from all models.
target_metadata = MetaData()
for table in AppBase.metadata.tables.values():
    table.tometadata(target_metadata)
for table in TenantBase.metadata.tables.values():
    table.tometadata(target_metadata)
for table in DocumentBase.metadata.tables.values():
    table.tometadata(target_metadata)
for table in AuditBase.metadata.tables.values():
    table.tometadata(target_metadata)
# --- End Autogenerate configuration ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url():
    return settings.database_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
