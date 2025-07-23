"""
Request schemas for API input validation.
Uses Pydantic v2 for robust validation and serialization.
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TicketCreateRequest(BaseModel):
    """
    Schema for creating a new support ticket.
    Supports both single text field or subject/body combination.
    """

    text: Optional[str] = Field(
        None,
        description="Full ticket text (alternative to subject/body)",
        min_length=10,
        max_length=10000,
    )
    subject: Optional[str] = Field(
        None, description="Ticket subject line", max_length=500
    )
    body: Optional[str] = Field(
        None,
        description="Ticket body content",
        min_length=10,
        max_length=10000,
    )

    # Optional dataset/import metadata
    original_queue: Optional[str] = Field(
        None,
        description=(
            "Original queue/department (e.g., 'Technical Support', "
            "'Billing and Payments')"
        ),
        max_length=100,
    )
    original_priority: Optional[str] = Field(
        None,
        description=(
            "Original priority level (e.g., 'low', 'medium', 'high', " "'critical')"
        ),
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_text_or_body(self) -> "TicketCreateRequest":
        """
        Ensure either 'text' or 'body' is provided.
        If both are provided, 'text' takes precedence.
        """
        if not self.text and not self.body:
            raise ValueError("Either 'text' or 'body' must be provided")

        return self

    @field_validator("body", mode="after")
    @classmethod
    def validate_body_length(cls, body: Optional[str]) -> Optional[str]:
        """Ensure body has meaningful content if provided."""
        if body and len(body.strip()) < 10:
            raise ValueError(
                "Body must contain at least 10 characters of meaningful " "content"
            )
        return body

    def get_full_text(self) -> str:
        """
        Get the complete text for AI processing.
        Prioritizes 'text' field, falls back to subject+body.
        """
        if self.text:
            return self.text

        if self.subject and self.body:
            return f"{self.subject}\n\n{self.body}"

        return self.body or ""

    def get_subject(self) -> Optional[str]:
        """Extract subject from request."""
        if self.subject:
            return self.subject

        # If only text is provided, try to extract first line as subject
        if self.text:
            lines = self.text.strip().split("\n", 1)
            if lines:
                subject = lines[0].strip()
                # Limit subject length
                return subject[:500] if subject else None

        return None

    def get_body(self) -> str:
        """Extract body from request."""
        if self.text:
            # If subject was extracted, remove it from body
            if self.subject:
                return self.text
            else:
                lines = self.text.strip().split("\n", 1)
                return lines[1] if len(lines) > 1 else lines[0]

        return self.body or ""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": (
                        "The data analytics platform crashed due to " "insufficient RAM"
                    )
                },
                {
                    "subject": "Billing Issue",
                    "body": ("I was overcharged on my last invoice. Please review."),
                },
            ]
        }
    }


class TicketFilterParams(BaseModel):
    """Query parameters for filtering tickets."""

    category: Optional[str] = Field(
        None,
        description="Filter by category (technical, billing, general)",
        pattern="^(technical|billing|general)$",
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results",
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of results to skip",
    )
