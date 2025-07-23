"""
Support Ticket Request API Endpoints.

This module provides RESTful API endpoints for managing customer support
tickets, including creation, retrieval, and listing with filtering
capabilities. All endpoints include AI-powered classification and comprehensive
error handling.

Endpoints:
- POST /requests/: Create new support ticket with AI classification
- GET /requests/{id}: Retrieve specific ticket by ID
- GET /requests/: List tickets with filtering and pagination

Features:
- Automatic AI classification of tickets
- Category-based filtering (technical, billing, general)
- Pagination support with configurable limits
- Comprehensive error handling and validation
- OpenAPI documentation with detailed descriptions

Author: Customer Support Intelligence Team
Version: 1.0.0
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.request import TicketCreateRequest, TicketFilterParams
from app.schemas.response import (
    TicketCreateResponse,
    TicketListResponse,
    TicketResponse,
)
from app.services.ticket_service import TicketService

# API router configuration with common prefix and tags
router = APIRouter(prefix="/requests", tags=["requests"])


@router.post(
    "/",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new support request",
    description="Accept a support request and trigger AI classification",
)
async def create_request(
    request: TicketCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TicketCreateResponse:
    """
    Create a new customer support ticket with AI classification.

    This endpoint accepts customer support requests in multiple formats and
    automatically triggers AI-powered classification to categorize the ticket
    and determine its priority and routing.

    Request Format Options:
    - `text`: Complete ticket content in a single field
    - `subject` and `body`: Separate subject line and body content

    The ticket is immediately stored in the database and queued for AI
    processing, which includes:
    - Category classification (technical, billing, general)
    - Confidence scoring
    - Priority assessment
    - Suggested routing information

    Args:
        request: Ticket creation request containing customer information
            and support request details.
        db: Database session dependency for data persistence.

    Returns:
        TicketCreateResponse: Confirmation response with ticket ID and
            processing status.

    Raises:
        HTTPException: 500 error if ticket creation fails due to database
            or service issues.

    Example:
        POST /api/v1/requests/
        {
            "customer_email": "user@example.com",
            "subject": "Login Issues",
            "body": "I can't log into my account"
        }
    """
    # Initialize ticket service with database session
    service = TicketService(db)

    try:
        # Create and classify the ticket
        ticket = await service.create_ticket(request)

        return TicketCreateResponse(
            id=ticket.id,
            status="processing",
            message="Ticket created and queued for AI processing",
        )
    except Exception:
        # TODO: Add proper logging for production error tracking
        # In production, log the actual error and return generic message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ticket",
        )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get a specific request",
    description="Retrieve a support request with its AI classification",
)
async def get_request(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """
    Retrieve a specific support ticket by its unique identifier.

    This endpoint fetches a single ticket from the database along with
    its AI classification results, if processing has been completed.
    The response includes all ticket metadata, customer information,
    and classification details.

    Args:
        ticket_id: Unique integer identifier for the ticket.
        db: Database session dependency for data retrieval.

    Returns:
        TicketResponse: Complete ticket information including:
            - Basic ticket data (ID, customer info, content)
            - AI classification results (category, confidence)
            - Processing status and timestamps

    Raises:
        HTTPException: 404 error if the ticket ID doesn't exist
            in the database.

    Example:
        GET /api/v1/requests/123

        Response:
        {
            "id": 123,
            "customer_email": "user@example.com",
            "subject": "Login Issues",
            "category": "technical",
            "confidence": 0.85,
            "created_at": "2024-01-01T12:00:00Z"
        }
    """
    # Initialize ticket service
    service = TicketService(db)

    # Attempt to retrieve the ticket
    ticket = await service.get_ticket(ticket_id)

    # Return 404 if ticket doesn't exist
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with ID {ticket_id} not found",
        )

    # Convert ORM model to response schema
    return TicketResponse.model_validate(ticket)


@router.get(
    "/",
    response_model=TicketListResponse,
    summary="List support requests",
    description="List requests with optional category filtering",
)
async def list_requests(
    category: Optional[str] = Query(
        None,
        description="Filter by category",
        pattern="^(technical|billing|general)$",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Number of results to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip",
    ),
    db: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    """
    List support tickets with filtering and pagination support.

    This endpoint retrieves a paginated list of support tickets with
    optional category-based filtering. It's designed to handle large
    datasets efficiently while providing flexible querying capabilities
    for different user interfaces and reporting needs.

    Query Parameters:
    - **category**: Filter tickets by AI classification category
        - Options: "technical", "billing", "general"
        - Leave empty to retrieve all categories
    - **limit**: Maximum number of tickets to return
        - Default: 100, Range: 1-1000
        - Controls page size for pagination
    - **offset**: Number of tickets to skip
        - Default: 0, Minimum: 0
        - Used for pagination (page_number * limit)

    Args:
        category: Optional category filter for ticket classification.
        limit: Maximum number of results per page.
        offset: Number of results to skip for pagination.
        db: Database session dependency for data retrieval.

    Returns:
        TicketListResponse: Paginated response containing:
            - items: List of ticket data with classifications
            - total: Total count of tickets matching filters
            - limit: Applied limit value
            - offset: Applied offset value

    Example:
        GET /api/v1/requests/?category=technical&limit=50&offset=0

        Response:
        {
            "items": [...],
            "total": 245,
            "limit": 50,
            "offset": 0
        }

    Note:
        For optimal performance with large datasets, consider using
        smaller limit values and implement client-side pagination.
    """
    # Build filter parameters from query parameters
    params = TicketFilterParams(
        category=category,
        limit=limit,
        offset=offset,
    )

    # Initialize service and retrieve filtered tickets
    service = TicketService(db)
    tickets, total = await service.list_tickets(params)

    # Build paginated response with metadata
    return TicketListResponse(
        items=[TicketResponse.model_validate(t) for t in tickets],
        total=total,
        limit=limit,
        offset=offset,
    )
