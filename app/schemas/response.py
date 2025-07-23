"""
Response schemas for API output serialization.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ClassificationResponse(BaseModel):
    """AI classification details."""

    category: str = Field(
        ..., description="Assigned category: technical, billing, or general"
    )
    confidence_score: float = Field(
        ..., description="Confidence score (0.0-1.0)", ge=0.0, le=1.0
    )
    summary: Optional[str] = Field(
        None, description="AI-generated one-sentence summary"
    )
    model_name: str = Field(..., description="AI model used")
    processing_time_ms: Optional[int] = Field(
        None, description="Processing time in milliseconds"
    )

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class TicketResponse(BaseModel):
    """Complete ticket response with classification."""

    id: int = Field(..., description="Unique ticket identifier")
    subject: Optional[str] = Field(None, description="Ticket subject")
    body: str = Field(..., description="Ticket body content")
    original_queue: Optional[str] = Field(
        None, description="Original queue from dataset"
    )
    original_priority: Optional[str] = Field(
        None, description="Original priority level"
    )
    language: Optional[str] = Field(None, description="Language code")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    classification: Optional[ClassificationResponse] = Field(
        None, description="AI classification results"
    )

    model_config = {"from_attributes": True}


class TicketCreateResponse(BaseModel):
    """Response after creating a ticket."""

    id: int = Field(..., description="Created ticket ID")
    status: str = Field("processing", description="Processing status")
    message: str = Field(..., description="Status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123,
                "status": "processing",
                "message": "Ticket created and queued for AI processing",
            }
        }
    }


class TicketListResponse(BaseModel):
    """Paginated list of tickets."""

    items: List[TicketResponse] = Field(..., description="List of tickets")
    total: int = Field(..., description="Total number of matching tickets")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Number of skipped results")

    @property
    def has_more(self) -> bool:
        """Check if more results are available."""
        return (self.offset + len(self.items)) < self.total


class CategoryStatsResponse(BaseModel):
    """Statistics per category."""

    category: str = Field(..., description="Category name")
    count: int = Field(..., description="Number of tickets")
    percentage: float = Field(..., description="Percentage of total", ge=0.0, le=100.0)


class StatsResponse(BaseModel):
    """Overall statistics response."""

    total_tickets: int = Field(..., description="Total tickets in period")
    period_days: int = Field(..., description="Statistics period in days")
    categories: List[CategoryStatsResponse] = Field(
        ..., description="Breakdown by category"
    )
    daily_counts: Dict[str, int] = Field(
        ..., description="Tickets per day (ISO date format)"
    )
    average_confidence: float = Field(
        ..., description="Average classification confidence", ge=0.0, le=1.0
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_tickets": 150,
                "period_days": 7,
                "categories": [
                    {"category": "technical", "count": 75, "percentage": 50.0},
                    {"category": "billing", "count": 45, "percentage": 30.0},
                    {"category": "general", "count": 30, "percentage": 20.0},
                ],
                "daily_counts": {
                    "2024-07-15": 20,
                    "2024-07-16": 25,
                    "2024-07-17": 30,
                },
                "average_confidence": 0.85,
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error description")
    status_code: int = Field(..., description="HTTP status code")
    error_type: Optional[str] = Field(None, description="Error classification")

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "Ticket not found",
                "status_code": 404,
                "error_type": "not_found",
            }
        }
    }
