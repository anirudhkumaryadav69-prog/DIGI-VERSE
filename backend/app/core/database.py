from contextlib import contextmanager
from typing import Generator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import build_postgres_connect_args, normalize_postgres_url, settings

# Deterministic constraint names so Alembic migrations stay stable and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_engine(url: str) -> Engine:
    normalized_url = normalize_postgres_url(url) or url
    return create_engine(
        normalized_url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        connect_args=build_postgres_connect_args(
            normalized_url,
            db_sslmode=settings.DB_SSLMODE,
            connect_timeout=settings.DB_CONNECT_TIMEOUT,
        ),
        echo=False,
    )


engine = build_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session; rolls back automatically on errors."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def transaction() -> Generator[Session, None, None]:
    """Unit-of-work helper: commits on success, rolls back on any exception."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str | None]:
    """Execute a real round-trip query. Returns (is_connected, error_message)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - surface any driver/network failure
        return False, exc.__class__.__name__
