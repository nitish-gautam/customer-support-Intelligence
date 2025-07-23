"""
Simple tests to demonstrate code coverage improvement.
Tests core functionality without complex async database setup.
"""

import pytest
from unittest.mock import patch

from app.services.ai_classifier import DummyClassifier, get_classifier


class TestBasicFunctionality:
    """Test basic functionality to demonstrate coverage."""

    @pytest.mark.asyncio
    async def test_dummy_classifier_basic(self):
        """Test basic dummy classifier functionality."""
        classifier = DummyClassifier()

        result = await classifier.classify("Server technical error")
        assert result.category == "technical"
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.model_name == "dummy-classifier"

    @pytest.mark.asyncio
    async def test_dummy_classifier_billing(self):
        """Test billing classification."""
        classifier = DummyClassifier()

        result = await classifier.classify("Invoice billing problem")
        assert result.category == "billing"
        assert 0.0 <= result.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_dummy_classifier_general(self):
        """Test general classification."""
        classifier = DummyClassifier()

        result = await classifier.classify("General information request")
        assert result.category == "general"
        assert 0.0 <= result.confidence_score <= 1.0

    def test_get_classifier_without_key(self):
        """Test get_classifier returns dummy when no OpenAI key."""
        with patch("app.services.ai_classifier.settings") as mock_settings:
            mock_settings.openai_api_key = None
            classifier = get_classifier()
            assert isinstance(classifier, DummyClassifier)

    def test_queue_to_category_mapping(self):
        """Test queue to category mapping."""
        classifier = DummyClassifier()

        assert classifier.map_queue_to_category("Technical Support") == "technical"
        assert classifier.map_queue_to_category("IT Support") == "technical"
        assert classifier.map_queue_to_category("Billing and Payments") == "billing"
        assert classifier.map_queue_to_category("Customer Service") == "general"
        assert classifier.map_queue_to_category("Unknown") == "general"

    def test_priority_to_confidence_mapping(self):
        """Test priority to confidence mapping."""
        classifier = DummyClassifier()

        assert classifier.map_priority_to_confidence("Critical") == 0.9
        assert classifier.map_priority_to_confidence("Medium") == 0.7
        assert classifier.map_priority_to_confidence("Low") == 0.5
        assert classifier.map_priority_to_confidence("Unknown") == 0.7


class TestTicketServiceFunctions:
    """Test ticket service utility functions."""

    def test_service_mapping_functions(self):
        """Test service-level mapping functions."""
        classifier = DummyClassifier()

        # Test queue mappings
        assert classifier.map_queue_to_category("Technical Support") == "technical"
        assert classifier.map_queue_to_category("Billing and Payments") == "billing"
        assert classifier.map_queue_to_category("General Inquiries") == "general"
        assert classifier.map_queue_to_category("") == "general"

        # Test priority mappings
        assert classifier.map_priority_to_confidence("Critical") == 0.9
        assert classifier.map_priority_to_confidence("Medium") == 0.7
        assert classifier.map_priority_to_confidence("Low") == 0.5


class TestSchemaValidation:
    """Test Pydantic schema validation."""

    def test_classification_result_validation(self):
        """Test classification result validation."""
        from app.services.ai_classifier import ClassificationResult

        # Valid result
        result = ClassificationResult(
            category="technical",
            confidence_score=0.85,
            summary="Test summary",
            processing_time_ms=150,
            model_name="test-model",
        )

        assert result.category == "technical"
        assert result.confidence_score == 0.85

    def test_request_schema_validation(self):
        """Test request schema validation."""
        from app.schemas.request import TicketCreateRequest

        # Valid text-only request
        request = TicketCreateRequest(text="This is a test ticket with enough length")
        assert request.text == "This is a test ticket with enough length"

        # Valid subject/body request
        request = TicketCreateRequest(
            subject="Test Subject", body="This is a test body with enough length"
        )
        assert request.subject == "Test Subject"
        assert request.body == "This is a test body with enough length"

    def test_response_schema_validation(self):
        """Test response schema validation."""
        from app.schemas.response import ClassificationResponse

        response = ClassificationResponse(
            category="technical",
            confidence_score=0.85,
            summary="Test summary",
            model_name="test-model",
            processing_time_ms=150,
        )

        assert response.category == "technical"
        assert 0.0 <= response.confidence_score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
