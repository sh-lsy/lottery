"""
Database engine, session management, and SQLite pragmas configuration.
Implements SQLAlchemy 2.0 DeclarativeBase, WAL mode, foreign keys, and connection pooling.
"""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from backend.app.config import DATABASE_URL


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""
    pass


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Enforce SQLite performance and integrity PRAGMAs:
    - WAL journal mode for concurrent reads during writes
    - NORMAL synchronous mode for high-throughput safe writes
    - FOREIGN KEYS ON for relational integrity
    - BUSY TIMEOUT 5000ms for avoiding lock contention
    """
    # Check if connection is SQLite
    if "sqlite" in type(dbapi_connection).__module__:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode = WAL")
        except Exception:
            # In-memory SQLite databases may not support WAL mode
            pass
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()


def create_db_engine(url: str = DATABASE_URL, echo: bool = False) -> Engine:
    """Create and configure a SQLAlchemy 2.0 engine."""
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, echo=echo)


# Global Engine and SessionLocal
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Engine = engine) -> None:
    """
    Initialize database schema by creating all registered tables.
    Importing backend.app.models registers all 4 core tables with Base.
    """
    # Import models here to ensure they are registered on Base.metadata
    from backend.app import models  # noqa: F401
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI / Context manager dependency yielding a database session.
    Automatically closes session on completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
