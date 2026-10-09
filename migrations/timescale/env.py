import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

pg_dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@localhost:5432/vigil")
if pg_dsn.startswith("postgresql://"):
    pg_dsn = pg_dsn.replace("postgresql://", "postgresql+psycopg2://", 1)
elif pg_dsn.startswith("postgresql+asyncpg://"):
    pg_dsn = pg_dsn.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

config.set_main_option("sqlalchemy.url", pg_dsn)

target_metadata = None

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="vigil",
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
