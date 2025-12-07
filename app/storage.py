"""
Database storage layer using SQLAlchemy with async support.
Provides the messages table schema and database session management.
"""

from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import String, Text, select, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings


# SQLAlchemy declarative base
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class Message(Base):
    """
    Messages table schema.
    
    Stores incoming webhook messages with message_id as PRIMARY KEY
    to enforce database-level uniqueness and idempotency.
    """
    
    __tablename__ = "messages"
    
    # PRIMARY KEY - ensures uniqueness and idempotency
    message_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        nullable=False,
        comment="Unique message identifier (PRIMARY KEY for idempotency)"
    )
    
    # Sender phone number in E.164 format
    from_msisdn: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Sender phone number in E.164 format"
    )
    
    # Recipient phone number in E.164 format
    to_msisdn: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Recipient phone number in E.164 format"
    )
    
    # Message timestamp (stored as string as received from webhook)
    ts: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Message timestamp"
    )
    
    # Message text content (optional, max 4096 characters)
    text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Message text content (optional)"
    )
    
    # Database creation timestamp
    created_at: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        comment="Timestamp when record was created in database"
    )
    
    def __repr__(self) -> str:
        """String representation of Message object."""
        return (
            f"<Message(message_id='{self.message_id}', "
            f"from='{self.from_msisdn}', to='{self.to_msisdn}')>"
        )


# Global async engine instance
engine: AsyncEngine | None = None

# Global session factory
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Initialize the database engine and create tables.
    
    This should be called on application startup.
    """
    global engine, AsyncSessionLocal
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Set to True for SQL query logging
        future=True,
    )
    
    # Create session factory
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close the database engine.
    
    This should be called on application shutdown.
    """
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Usage in FastAPI:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass
    
    Yields:
        AsyncSession: Database session for the request
    """
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() on application startup."
        )
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Utility functions for common database operations

async def save_message(db: AsyncSession, message_data: dict) -> Message:
    """
    Save a message to the database.
    
    Args:
        db: Database session
        message_data: Dictionary containing message fields
    
    Returns:
        Message: The saved message object
    
    Raises:
        IntegrityError: If message_id already exists (duplicate)
    """
    message = Message(
        message_id=message_data["message_id"],
        from_msisdn=message_data["from_msisdn"],
        to_msisdn=message_data["to_msisdn"],
        ts=message_data["ts"],
        text=message_data.get("text"),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    
    db.add(message)
    await db.flush()  # Flush to check for constraint violations
    
    return message


async def get_all_messages(db: AsyncSession) -> list[Message]:
    """
    Retrieve all messages from the database.
    
    Args:
        db: Database session
    
    Returns:
        List of Message objects
    """
    result = await db.execute(select(Message).order_by(Message.created_at.desc()))
    return list(result.scalars().all())


async def get_message_by_id(db: AsyncSession, message_id: str) -> Message | None:
    """
    Retrieve a specific message by ID.
    
    Args:
        db: Database session
        message_id: Unique message identifier
    
    Returns:
        Message object if found, None otherwise
    """
    result = await db.execute(
        select(Message).where(Message.message_id == message_id)
    )
    return result.scalar_one_or_none()


async def get_message_stats(db: AsyncSession) -> dict:
    """
    Calculate aggregate statistics about messages.
    
    Args:
        db: Database session
    
    Returns:
        Dictionary containing statistics:
            - total_messages: Total count of messages
            - unique_senders: Count of unique sender numbers
            - unique_recipients: Count of unique recipient numbers
    """
    # Count total messages
    total_result = await db.execute(select(func.count(Message.message_id)))
    total_messages = total_result.scalar() or 0
    
    # Count unique senders
    senders_result = await db.execute(
        select(func.count(func.distinct(Message.from_msisdn)))
    )
    unique_senders = senders_result.scalar() or 0
    
    # Count unique recipients
    recipients_result = await db.execute(
        select(func.count(func.distinct(Message.to_msisdn)))
    )
    unique_recipients = recipients_result.scalar() or 0
    
    return {
        "total_messages": total_messages,
        "unique_senders": unique_senders,
        "unique_recipients": unique_recipients,
    }
