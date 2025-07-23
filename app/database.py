"""
Database Configuration and Session Management.

This module provides database connectivity and session management for the
Customer Support Intelligence API using SQLAlchemy 2.0 with async support.
It includes both synchronous and asynchronous database engines for different
use cases, along with session factories and dependency injection functions.

Key Features:
- Async SQLAlchemy 2.0 engine for high-performance database operations
- Sync engine for migrations and administrative scripts
- Connection pooling with configurable parameters
- Session management with proper cleanup
- FastAPI dependency injection support

Database Architecture:
- PostgreSQL with asyncpg driver for async operations
- Connection pooling for efficient resource utilization
- Automatic connection health checks (pool_pre_ping)
- Declarative base class for ORM models

Author: Customer Support Intelligence Team
Version: 1.0.0
"""

from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Database Engine Configuration

# Synchronous engine for migrations and administrative operations
# Used by Alembic for schema migrations and batch processing scripts
sync_engine = create_engine(
    str(settings.database_url),  # Standard PostgreSQL URL
    pool_size=settings.db_pool_size,  # Number of connections to pool
    # Additional connections beyond pool_size
    max_overflow=settings.db_max_overflow,
    echo=settings.db_echo,  # Log SQL statements for debugging
    pool_pre_ping=True,  # Verify connections before using
)

# Asynchronous engine for high-performance application operations
# Used by the FastAPI application for handling API requests
async_engine = create_async_engine(
    settings.database_url_async,  # PostgreSQL URL with asyncpg driver
    pool_size=settings.db_pool_size,  # Number of connections to pool
    # Additional connections beyond pool_size
    max_overflow=settings.db_max_overflow,
    echo=settings.db_echo,  # Log SQL statements for debugging
    pool_pre_ping=True,  # Verify connections before using
)

# Database Session Factory Configuration

# Synchronous session factory for migrations and scripts
# Creates traditional SQLAlchemy sessions bound to the sync engine
SessionLocal = sessionmaker(
    bind=sync_engine,  # Bind to synchronous engine
    autocommit=False,  # Manual transaction control
    autoflush=False,  # Manual flush control for performance
    expire_on_commit=False,  # Keep objects usable after commit
)

# Asynchronous session factory for API request handling
# Creates async SQLAlchemy sessions bound to the async engine
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,  # Bind to asynchronous engine
    autocommit=False,  # Manual transaction control
    autoflush=False,  # Manual flush control for performance
    expire_on_commit=False,  # Keep objects usable after commit
    class_=AsyncSession,  # Use AsyncSession class
)


# Database Model Base Class


class Base(DeclarativeBase):
    """
    Declarative base class for all database models.

    This class serves as the foundation for all SQLAlchemy ORM models
    in the application. It provides common functionality and metadata
    that is inherited by all model classes.

    Features:
    - Automatic table name generation from class names
    - Common model metadata and configuration
    - Type annotation support for modern SQLAlchemy

    Usage:
        class MyModel(Base):
            __tablename__ = "my_table"
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """

    pass


# Database Session Dependency Functions


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for providing async database sessions.

    This function creates an async database session for each request
    and ensures proper cleanup even if an exception occurs. It follows
    the dependency injection pattern used by FastAPI.

    Yields:
        AsyncSession: Database session for the current request.

    Note:
        The session is automatically closed after the request completes,
        ensuring no connection leaks occur.

    Usage:
        @app.get("/items/")
        async def get_items(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_db() -> Session:
    """
    Create synchronous database session for scripts and migrations.

    This function provides a synchronous database session primarily
    used by migration scripts, data seeding scripts, and other
    administrative operations that don't require async support.

    Returns:
        Session: Synchronous SQLAlchemy session.

    Note:
        Remember to close the session manually when using this function
        outside of a context manager.

    Usage:
        with get_sync_db() as db:
            # Use db session here
            pass
    """
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()
