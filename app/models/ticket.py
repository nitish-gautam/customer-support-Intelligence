"""
Ticket model representing customer support requests.
Maps to the HuggingFace dataset structure.
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.classification import Classification, TicketTag


class Ticket(Base):
    """
    Support ticket model with full dataset field mapping.
    """

    __tablename__ = "tickets"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Core fields from dataset
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Original answer from dataset for training",
    )

    # Original dataset fields
    original_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Original type from dataset"
    )
    original_queue: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Original queue from dataset",
    )
    original_priority: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Original priority: low/medium/critical",
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="Language code (e.g., 'en', 'de')"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    classification: Mapped[Optional["Classification"]] = relationship(
        "Classification",
        back_populates="ticket",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tags: Mapped[List["TicketTag"]] = relationship(
        "TicketTag",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        subject_preview = self.subject[:50] if self.subject else "None"
        return f"<Ticket(id={self.id}, subject='{subject_preview}...)>'"

    @property
    def full_text(self) -> str:
        """Concatenated subject and body for AI processing."""
        if self.subject:
            return f"{self.subject}\n\n{self.body}"
        return self.body
