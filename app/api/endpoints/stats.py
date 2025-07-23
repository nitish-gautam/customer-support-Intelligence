"""
API endpoints for statistics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.response import StatsResponse
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get(
    "/",
    response_model=StatsResponse,
    summary="Get ticket statistics",
    description="Returns ticket counts and metrics for the specified period",
)
async def get_stats(
    days: int = Query(
        7,
        ge=1,
        le=90,
        description="Number of days to include in statistics",
    ),
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """
    Get ticket statistics for the past N days.

    Returns:
    - Total ticket count
    - Breakdown by category with percentages
    - Daily ticket counts
    - Average classification confidence
    """
    service = TicketService(db)
    stats = await service.get_stats(days)

    return StatsResponse(**stats)
