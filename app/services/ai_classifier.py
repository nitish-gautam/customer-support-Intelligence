"""
AI-Powered Support Ticket Classification Service.

This module provides intelligent classification capabilities for customer
support
tickets using various AI models. It supports multiple
classification backends
including OpenAI's GPT models and fallback keyword-based classification.

Key Features:
- Multi-model support (OpenAI GPT, fallback keyword matching)
- Automatic category classification (technical, billing, general)
- Confidence scoring and processing time tracking
- Robust error handling with fallback mechanisms
- Configurable model parameters and prompts

Classification Categories:
- Technical: IT issues, software problems, hardware failures, system errors
- Billing: Payment issues, invoices, charges, refunds, pricing questions
- General: Product inquiries, feature requests, general customer questions

Architecture:
- Abstract base class for extensible classifier implementations
- Factory pattern for classifier selection based on configuration
- Standardized result format with metadata and performance metrics

Author: Customer Support Intelligence Team
Version: 1.0.0
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

import openai
from pydantic import BaseModel

from app.config import settings


class ClassificationResult(BaseModel):
    """
    Structured result from AI-powered ticket classification.

    This class defines the standardized format for classification results
    across all classifier implementations. It includes both the classification
    outcomes and metadata about the processing.

    Attributes:
        category: Classification category (technical/billing/general)
        confidence_score: Confidence level between 0.0 and 1.0
        summary: Optional one-sentence summary of the ticket content
        processing_time_ms: Time taken for classification in milliseconds
        model_name: Identifier of the model used for classification

    Note:
        The model_config disables Pydantic's protected namespace warnings
        for the 'model_name' field to avoid conflicts with Pydantic internals.
    """

    model_config = {"protected_namespaces": ()}

    category: str  # Primary classification category
    confidence_score: float  # Classification confidence (0.0-1.0)
    summary: Optional[str] = None  # Optional ticket summary
    processing_time_ms: int  # Processing duration in milliseconds
    model_name: str  # Model identifier for tracking


class BaseClassifier(ABC):
    """
    Abstract base class for all ticket classification implementations.

    This class defines the interface that all classifier implementations
    must follow, ensuring consistent behavior across different AI models
    and fallback mechanisms. It also provides utility methods for mapping
    dataset-specific values to standardized formats.

    Subclasses must implement:
        - classify(): Main classification method

    Utility methods provided:
        - map_queue_to_category(): Convert dataset queue names to categories
        - map_priority_to_confidence(): Convert priority levels to
          confidence scores
    """

    @abstractmethod
    async def classify(self, text: str) -> ClassificationResult:
        """
        Classify the given ticket text into a support category.

        This method must be implemented by all classifier subclasses to
        provide consistent classification functionality.

        Args:
            text: Raw ticket content to classify.

        Returns:
            ClassificationResult: Structured classification result with
                category, confidence, and metadata.

        Note:
            Implementations should handle errors gracefully and provide
            fallback classification when possible.
        """
        pass

    def map_queue_to_category(self, queue: str) -> str:
        """
        Map dataset queue identifiers to standardized categories.

        Converts queue names from the training dataset to our three
        standard categories. This ensures consistency when processing
        different data sources.

        Args:
            queue: Queue identifier from the dataset.

        Returns:
            str: Standardized category (technical/billing/general).

        Mapping Rules:
            - Queues containing "technical" or "it support" -> "technical"
            - Queues containing "billing" or "payment" -> "billing"
            - All other queues -> "general"
        """
        queue_lower = queue.lower()

        if "technical" in queue_lower or "it support" in queue_lower:
            return "technical"
        elif "billing" in queue_lower or "payment" in queue_lower:
            return "billing"
        else:
            return "general"

    def map_priority_to_confidence(self, priority: str) -> float:
        """
        Convert priority levels to confidence scores.

        Maps ticket priority indicators to numerical confidence values,
        assuming that higher priority tickets have more reliable
        classification data.

        Args:
            priority: Priority level string from dataset.

        Returns:
            float: Confidence score between 0.5 and 0.9.

        Priority Mapping:
            - Critical/High: 0.9 (high confidence)
            - Medium: 0.7 (moderate confidence)
            - Low: 0.5 (low confidence)
            - Unknown: 0.7 (default moderate confidence)
        """
        priority_lower = priority.lower() if priority else "medium"

        # Priority to confidence mapping
        mapping = {
            "critical": 0.9,  # Highest confidence for critical issues
            "high": 0.9,  # High confidence for high priority
            "medium": 0.7,  # Moderate confidence for medium priority
            "low": 0.5,  # Lower confidence for low priority
        }

        return mapping.get(priority_lower, 0.7)  # Default to medium confidence


class OpenAIClassifier(BaseClassifier):
    """
    OpenAI GPT-based ticket classification implementation.

    This classifier uses OpenAI's chat completion API to perform intelligent
    ticket classification with high accuracy. It includes robust error handling
    with automatic fallback to keyword-based classification if the API fails.

    Features:
    - JSON-structured prompts for consistent responses
    - Configurable model parameters (temperature, max_tokens)
    - Automatic response validation and sanitization
    - Fallback classification for API failures
    - Performance tracking and monitoring
    """

    def __init__(self) -> None:
        """
        Initialize OpenAI classifier with API client.

        Raises:
            ValueError: If OpenAI API key is not configured in settings.
        """
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.ai_model

    async def classify(self, text: str) -> ClassificationResult:
        """
        Classify text using OpenAI API.
        Returns category, confidence, and optional summary.
        """
        start_time = time.time()

        system_prompt = (
            "You are a customer support ticket classifier. "
            "Analyze the given text and respond with a JSON object "
            "containing:\n"
            "1. 'category': exactly one of 'technical', 'billing', or "
            "'general'\n"
            "   - 'technical': IT issues, software problems, hardware "
            "failures, "
            "system errors\n"
            "   - 'billing': payment issues, invoices, charges, refunds, "
            "pricing\n"
            "   - 'general': product inquiries, feature requests, general "
            "questions\n"
            "2. 'confidence': a score between 0.0 and 1.0 indicating "
            "classification confidence\n"
            "3. 'summary': a one-sentence summary of the issue (max 150 "
            "characters)\n\n"
            "Respond ONLY with valid JSON, no additional text."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Classify this ticket: {text}",
                    },
                ],
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                response_format={"type": "json_object"},
            )

            # Parse response
            result = response.choices[0].message.content
            if not result:
                raise ValueError("Empty response from OpenAI")

            import json

            parsed = json.loads(result)

            # Validate category
            category = parsed.get("category", "general").lower()
            if category not in ["technical", "billing", "general"]:
                category = "general"

            # Validate confidence
            confidence = float(parsed.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))

            # Get summary
            summary = parsed.get("summary", "")
            if summary and len(summary) > 150:
                summary = summary[:147] + "..."

            processing_time = int((time.time() - start_time) * 1000)

            return ClassificationResult(
                category=category,
                confidence_score=confidence,
                summary=summary if summary else None,
                processing_time_ms=processing_time,
                model_name=self.model,
            )

        except Exception as e:
            # Fallback classification based on keywords
            return await self._fallback_classify(text, start_time, str(e))

    async def _fallback_classify(
        self, text: str, start_time: float, error: str
    ) -> ClassificationResult:
        """
        Fallback keyword-based classification.
        Used when AI service fails.
        """
        text_lower = text.lower()

        # Keywords for classification
        technical_keywords = [
            "error",
            "crash",
            "bug",
            "system",
            "software",
            "hardware",
            "server",
            "database",
            "application",
            "platform",
            "technical",
            "IT",
            "computer",
            "network",
            "installation",
            "update",
        ]

        billing_keywords = [
            "invoice",
            "billing",
            "payment",
            "charge",
            "refund",
            "price",
            "cost",
            "fee",
            "subscription",
            "overcharge",
            "bill",
            "money",
            "credit",
            "debit",
            "transaction",
            "purchase",
        ]

        # Count keyword matches
        technical_score = sum(1 for kw in technical_keywords if kw in text_lower)
        billing_score = sum(1 for kw in billing_keywords if kw in text_lower)

        # Determine category
        if technical_score > billing_score and technical_score > 0:
            category = "technical"
            confidence = min(0.6 + (technical_score * 0.05), 0.85)
        elif billing_score > 0:
            category = "billing"
            confidence = min(0.6 + (billing_score * 0.05), 0.85)
        else:
            category = "general"
            confidence = 0.5

        processing_time = int((time.time() - start_time) * 1000)

        return ClassificationResult(
            category=category,
            confidence_score=confidence,
            summary=None,  # No summary in fallback mode
            processing_time_ms=processing_time,
            model_name=f"{self.model}-fallback",
        )


class DummyClassifier(BaseClassifier):
    """
    Dummy classifier for testing without AI services.
    Uses simple keyword matching.
    """

    async def classify(self, text: str) -> ClassificationResult:
        """Simple rule-based classification for testing."""
        start_time = time.time()

        text_lower = text.lower()

        # Simple keyword-based classification
        if any(word in text_lower for word in ["crash", "error", "bug", "technical"]):
            category = "technical"
            confidence = 0.8
        elif any(
            word in text_lower for word in ["invoice", "billing", "payment", "charge"]
        ):
            category = "billing"
            confidence = 0.85
        else:
            category = "general"
            confidence = 0.7

        # Simple summary (first 100 chars)
        summary = text[:100] + "..." if len(text) > 100 else text

        processing_time = int((time.time() - start_time) * 1000)

        return ClassificationResult(
            category=category,
            confidence_score=confidence,
            summary=summary,
            processing_time_ms=processing_time,
            model_name="dummy-classifier",
        )


def get_classifier() -> BaseClassifier:
    """
    Factory function to get appropriate classifier.
    Returns OpenAI classifier if configured, otherwise dummy.
    """
    if settings.openai_api_key and settings.openai_api_key.strip():
        try:
            return OpenAIClassifier()
        except ValueError:
            # If OpenAI initialization fails, fallback to dummy
            return DummyClassifier()
    else:
        # In production, you might want to raise an error here
        # For development, we'll use the dummy classifier
        return DummyClassifier()
