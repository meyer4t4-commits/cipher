"""
SQLAlchemy database engine and session management.
Supports PostgreSQL (production/Railway) and SQLite (local dev).

Detects automatically from DATABASE_URL:
- If DATABASE_URL starts with postgres:// or postgresql:// → PostgreSQL
- Otherwise falls back to SQLite at ./data/cipher.db
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# Resolve database URL — Railway sets DATABASE_URL for Postgres
# ---------------------------------------------------------------------------
_raw_url = os.environ.get("DATABASE_URL", "") or settings.database_url
_is_postgres = _raw_url.startswith("postgres://") or _raw_url.startswith("postgresql://")

if _is_postgres:
    # Railway/Heroku use postgres:// but SQLAlchemy 2.x requires postgresql://
    database_url = _raw_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,   # Reconnect on stale connections
        echo=settings.app_debug,
    )
else:
    # SQLite mode — check if we can actually write to the target path
    database_url = _raw_url
    _on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_ID"))
    _use_memory_db = False

    if _on_railway:
        # Railway's filesystem is ephemeral/read-only for data dirs.
        # Use in-memory SQLite so the app runs (tables exist, just no persistence).
        # To persist data on Railway, set DATABASE_URL to a PostgreSQL connection string.
        database_url = "sqlite://"  # in-memory
        _use_memory_db = True
    else:
        db_path = database_url.replace("sqlite:///", "")
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            database_url = "sqlite://"
            _use_memory_db = True

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # SQLite needs this for FastAPI
        echo=settings.app_debug,
    )

    if _use_memory_db:
        from app.core.logging import logger as _db_logger
        _db_logger.warning(
            "Using in-memory SQLite (no persistence). "
            "Set DATABASE_URL to a PostgreSQL connection string for persistent storage."
        )

    # SQLite performance pragmas — only for file-based SQLite
    if not _use_memory_db:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called on startup."""
    import app.db.models  # noqa: F401 - ensures models are registered
    import app.gateway.models  # noqa: F401 - Elysian Gateway tables
    Base.metadata.create_all(bind=engine)
