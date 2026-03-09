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
    # Local SQLite — ensure data directory exists
    database_url = _raw_url
    db_path = database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # SQLite needs this for FastAPI
        echo=settings.app_debug,
    )

    # SQLite performance pragmas — only for SQLite
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
