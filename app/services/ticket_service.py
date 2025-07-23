"""
Business logic for ticket management.
Handles creation, retrieval, and AI processing.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.classification import Classification
from app.models.ticket import Ticket
from app.schemas.request import TicketCreateRequest, TicketFilterParams
from app.services.ai_classifier import get_classifier


def map_queue_to_category(queue: str) -> str:
    """
    Map dataset queue identifiers to standardized categories.

    Args:
        queue: Queue identifier from the dataset.

    Returns:
        str: Standardized category (technical/billing/general).
    """
    if not queue:
        return "general"

    queue_lower = queue.lower()

    if "technical" in queue_lower or "it support" in queue_lower:
        return "technical"
    elif "billing" in queue_lower or "payment" in queue_lower:
        return "billing"
    else:
        return "general"


def map_priority_to_confidence(priority: str) -> float:
    """
    Convert priority levels to confidence scores.

    Args:
        priority: Priority level string from dataset.

    Returns:
        float: Confidence score between 0.5 and 0.9.
    """
    priority_lower = priority.lower() if priority else "medium"

    mapping = {
        "critical": 0.9,
        "high": 0.9,
        "medium": 0.7,
        "low": 0.5,
    }

    return mapping.get(priority_lower, 0.7)


class TicketService:
    """Service for managing support tickets."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.classifier = get_classifier()

    async def create_ticket(self, request: TicketCreateRequest) -> Ticket:
        """
        Create a new ticket and trigger AI classification.
        """
        # Create ticket instance
        ticket = Ticket(
            subject=request.get_subject(),
            body=request.get_body(),
            original_queue=request.original_queue,
            original_priority=request.original_priority,
            language="en",  # Could be detected from text
        )

        # Add to database
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)

        # Trigger AI classification (async)
        await self._classify_ticket(ticket)

        return ticket

    async def get_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """
        Retrieve a single ticket with classification.
        """
        query = (
            select(Ticket)
            .options(selectinload(Ticket.classification))
            .where(Ticket.id == ticket_id)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_tickets(
        self, params: TicketFilterParams
    ) -> tuple[List[Ticket], int]:
        """
        List tickets with optional filtering and pagination.
        Returns (tickets, total_count).
        """
        # Base query
        query = select(Ticket).options(selectinload(Ticket.classification))
        count_query = select(func.count(Ticket.id))

        # Apply category filter if provided
        if params.category:
            query = query.join(Classification).where(
                Classification.category == params.category
            )
            count_query = count_query.join(Classification).where(
                Classification.category == params.category
            )

        # Get total count
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar() or 0

        # Apply pagination
        query = query.offset(params.offset).limit(params.limit)
        query = query.order_by(Ticket.created_at.desc())

        # Execute query
        result = await self.db.execute(query)
        tickets = result.scalars().all()

        return list(tickets), total_count

    async def get_stats(self, days: int = 7) -> Dict:
        """
        Get ticket statistics for the past N days.
        """
        # Calculate date range
        from datetime import timezone

        end_date = datetime.now(timezone.utc).replace(tzinfo=None)
        start_date = end_date - timedelta(days=days)

        # Get tickets in date range with classifications
        query = (
            select(Ticket)
            .options(selectinload(Ticket.classification))
            .where(Ticket.created_at >= start_date)
        )
        result = await self.db.execute(query)
        tickets = result.scalars().all()

        # Calculate statistics
        total_tickets = len(tickets)
        category_counts = {"technical": 0, "billing": 0, "general": 0}
        daily_counts: dict[str, int] = {}
        total_confidence = 0.0
        classified_count = 0

        for ticket in tickets:
            # Daily counts
            date_key = ticket.created_at.date().isoformat()
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1

            # Category counts and confidence
            if ticket.classification:
                category_counts[ticket.classification.category] += 1
                total_confidence += ticket.classification.confidence_score
                classified_count += 1

        # Calculate percentages
        categories = []
        for category, count in category_counts.items():
            percentage = (count / total_tickets * 100) if total_tickets > 0 else 0
            categories.append(
                {
                    "category": category,
                    "count": count,
                    "percentage": round(percentage, 2),
                }
            )

        # Average confidence
        avg_confidence = (
            total_confidence / classified_count if classified_count > 0 else 0
        )

        return {
            "total_tickets": total_tickets,
            "period_days": days,
            "categories": sorted(categories, key=lambda x: x["count"], reverse=True),
            "daily_counts": dict(sorted(daily_counts.items())),
            "average_confidence": round(avg_confidence, 3),
        }

    async def _classify_ticket(self, ticket: Ticket) -> None:
        """
        Perform AI classification on a ticket.
        This could be moved to a background task in production.
        """
        try:
            # Get classification from AI
            result = await self.classifier.classify(ticket.full_text)

            # Create classification record
            classification = Classification(
                ticket_id=ticket.id,
                category=result.category,
                confidence_score=result.confidence_score,
                summary=result.summary,
                model_name=result.model_name,
                processing_time_ms=result.processing_time_ms,
            )

            self.db.add(classification)
            await self.db.commit()

        except Exception as e:
            # Log error but don't fail ticket creation
            # In production, you'd want proper logging here
            print(f"Classification failed for ticket {ticket.id}: {e}")

            # Create a default classification
            classification = Classification(
                ticket_id=ticket.id,
                category="general",
                confidence_score=0.0,
                summary=None,
                model_name="error-fallback",
                processing_time_ms=0,
            )

            self.db.add(classification)
            await self.db.commit()
