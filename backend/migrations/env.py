from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import build_postgres_connect_args, normalize_postgres_url, settings
from app.models import Base  # noqa: F401  - importing the package registers every model

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Database URL always comes from environment-based settings (never from alembic.ini).
# Programmatic callers (e.g. the test suite) may override it via config.attributes.
# `%` must be escaped for ConfigParser interpolation (e.g. URL-encoded passwords).
_raw_database_url = config.attributes.get("database_url") or settings.DATABASE_URL
_database_url = normalize_postgres_url(_raw_database_url) or _raw_database_url
config.set_main_option("sqlalchemy.url", _database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database inside a transaction."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=build_postgres_connect_args(
            _database_url,
            db_sslmode=settings.DB_SSLMODE,
            connect_timeout=settings.DB_CONNECT_TIMEOUT,
        ),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
