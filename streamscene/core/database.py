"""Database connection and session management."""

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=20,  # Connection pool size
    max_overflow=10,  # Additional connections beyond pool_size
    echo=False,  # Set to True for SQL logging during development
    connect_args={"client_encoding": "utf8"},  # Force UTF-8 encoding
)

# Force UTF-8 encoding on all connections (event listener)
@event.listens_for(engine, "connect")
def set_unicode_mode(dbapi_conn, connection_record):
    """Set client encoding to UTF-8 on every new connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET CLIENT_ENCODING TO 'UTF8'")
    cursor.close()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for declarative models
Base = declarative_base()


def get_session() -> Session:
    """
    Create a new database session.

    Returns:
        Session: SQLAlchemy session instance

    Usage:
        session = get_session()
        try:
            # Use session
            pass
        finally:
            session.close()
    """
    return SessionLocal()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Automatically commits on success and rolls back on error.

    Usage:
        with get_db_session() as session:
            # Use session
            user = session.query(User).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Initialize database by creating all tables.
    Only use this in development or for testing.
    In production, use Alembic migrations.
    """
    from . import models  # Import models to register them
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """
    Drop all tables in the database.
    WARNING: This will delete all data!
    Only use for testing.
    """
    Base.metadata.drop_all(bind=engine)
