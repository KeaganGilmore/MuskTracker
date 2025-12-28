"""Database session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from musktracker.config import get_config

# Module-level engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine.

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is None:
        config = get_config()
        _engine = create_engine(
            config.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def get_session_factory():
    """Get or create session factory.

    Returns:
        SQLAlchemy sessionmaker
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup.

    Yields:
        SQLAlchemy Session instance

    Example:
        with get_db_session() as session:
            session.add(obj)
            session.commit()
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

