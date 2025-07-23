"""
Classification model for AI-generated ticket categorization.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Classification(Base):
    """
    AI classification results for support tickets.
    """

    __tablename__ = "classifications"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to ticket
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), unique=True
    )

    # Classification results
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="technical, billing, or general",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Confidence score 0.0-1.0",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated one-sentence summary",
    )

    # Model metadata
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="AI model used for classification",
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Model version if applicable",
    )

    # Processing metadata
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Time taken for AI processing in milliseconds",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="classification")

    def __repr__(self) -> str:
        return (
            f"<Classification(id={self.id}, category='{self.category}', "
            f"confidence={self.confidence_score:.2f})>"
        )


class TicketTag(Base):
    """
    Tags associated with tickets (from dataset tag_1 through tag_8).
    """

    __tablename__ = "ticket_tags"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to ticket
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE")
    )

    # Tag information
    tag_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Position 1-8 from dataset"
    )
    tag_value: Mapped[str] = mapped_column(String(100), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="tags")

    def __repr__(self) -> str:
        return (
            f"<TicketTag(position={self.tag_position}, " f"value='{self.tag_value}')>"
        )
