"""
Core functionality tests that work reliably.
Focuses on essential features with proper async handling.
"""

import pytest

from app.services.ai_classifier import (
    DummyClassifier,
    get_classifier,
    ClassificationResult,
)


class TestCoreClassifierFunctionality:
    """Test core classifier functionality with proper async handling."""

    @pytest.mark.asyncio
    async def test_dummy_classifier_basic_functionality(self):
        """Test dummy classifier basic classification."""
        classifier = DummyClassifier()

        # Test technical classification
        result = await classifier.classify("Server technical error database crash")
        assert isinstance(result, ClassificationResult)
        assert result.category == "technical"
        assert result.model_name == "dummy-classifier"
        assert 0.0 <= result.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_dummy_classifier_billing_classification(self):
        """Test billing classification."""
        classifier = DummyClassifier()

        result = await classifier.classify("Invoice billing payment charge issue")
        assert result.category == "billing"
        assert result.confidence_score >= 0.8

    @pytest.mark.asyncio
    async def test_dummy_classifier_general_classification(self):
        """Test general classification."""
        classifier = DummyClassifier()

        result = await classifier.classify("General information about your services")
        assert result.category == "general"
        assert result.confidence_score > 0.0

    def test_queue_to_category_mapping(self):
        """Test queue to category mapping logic."""
        classifier = DummyClassifier()

        # Test technical mappings
        assert classifier.map_queue_to_category("Technical Support") == "technical"
        assert classifier.map_queue_to_category("IT Support") == "technical"

        # Test billing mappings
        assert classifier.map_queue_to_category("Billing and Payments") == "billing"
        assert classifier.map_queue_to_category("Payment Issues") == "billing"

        # Test general mappings
        assert classifier.map_queue_to_category("Customer Service") == "general"
        assert classifier.map_queue_to_category("General Inquiries") == "general"
        assert classifier.map_queue_to_category("Unknown Queue") == "general"

    def test_priority_to_confidence_mapping(self):
        """Test priority to confidence mapping logic."""
        classifier = DummyClassifier()

        # Test priority mappings
        assert classifier.map_priority_to_confidence("Critical") == 0.9
        assert classifier.map_priority_to_confidence("Medium") == 0.7
        assert classifier.map_priority_to_confidence("Low") == 0.5
        assert classifier.map_priority_to_confidence("Unknown") == 0.7

    def test_classifier_initialization(self):
        """Test that classifiers can be initialized."""
        classifier = DummyClassifier()
        assert classifier is not None

        # Test get_classifier function
        classifier = get_classifier()
        assert classifier is not None

    @pytest.mark.asyncio
    async def test_classification_result_structure(self):
        """Test that classification results have proper structure."""
        classifier = DummyClassifier()

        result = await classifier.classify("Test classification request")

        # Verify all required fields are present
        assert hasattr(result, "category")
        assert hasattr(result, "confidence_score")
        assert hasattr(result, "summary")
        assert hasattr(result, "model_name")
        assert hasattr(result, "processing_time_ms")

        # Verify field types and constraints
        assert isinstance(result.category, str)
        assert isinstance(result.confidence_score, float)
        assert isinstance(result.processing_time_ms, int)
        assert result.category in ["technical", "billing", "general"]
        assert 0.0 <= result.confidence_score <= 1.0


class TestSchemaValidation:
    """Test Pydantic schema validation without database dependencies."""

    def test_classification_result_validation(self):
        """Test ClassificationResult schema validation."""
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
        assert result.model_name == "test-model"

    def test_request_schema_validation(self):
        """Test request schema validation."""
        from app.schemas.request import TicketCreateRequest

        # Valid text-only request
        request = TicketCreateRequest(
            text="This is a test ticket with sufficient length for validation"
        )
        assert request.text is not None

        # Valid subject/body request
        request = TicketCreateRequest(
            subject="Test Subject",
            body="This is a test body with sufficient length for validation",
        )
        assert request.subject == "Test Subject"
        assert request.body is not None

    def test_response_schema_validation(self):
        """Test response schema validation."""
        from app.schemas.response import ClassificationResponse

        response = ClassificationResponse(
            category="billing",
            confidence_score=0.75,
            summary="Test billing issue summary",
            model_name="test-model",
            processing_time_ms=200,
        )

        assert response.category == "billing"
        assert 0.0 <= response.confidence_score <= 1.0


class TestConfigurationHandling:
    """Test configuration and environment handling."""

    def test_config_import(self):
        """Test that configuration can be imported."""
        from app.config import settings

        assert settings is not None

    def test_database_models_import(self):
        """Test that database models can be imported."""
        from app.models.ticket import Ticket
        from app.models.classification import Classification, TicketTag

        assert Ticket is not None
        assert Classification is not None
        assert TicketTag is not None

    def test_api_schemas_import(self):
        """Test that API schemas can be imported."""
        from app.schemas.request import TicketCreateRequest
        from app.schemas.response import TicketResponse, ClassificationResponse

        assert TicketCreateRequest is not None
        assert TicketResponse is not None
        assert ClassificationResponse is not None


class TestDatasetCompatibility:
    """Test dataset field compatibility and mapping."""

    def test_dataset_field_mapping_logic(self):
        """Test that dataset field mapping works correctly."""
        classifier = DummyClassifier()

        # Mock dataset record structure
        mock_record = {
            "subject": "Database Performance Issue",
            "body": "The production database is experiencing slow query performance",
            "queue": "Technical Support",
            "priority": "Critical",
            "language": "en",
            "tag_1": "database",
            "tag_2": "performance",
        }

        # Test mapping functions
        category = classifier.map_queue_to_category(mock_record["queue"])
        assert category == "technical"

        confidence = classifier.map_priority_to_confidence(mock_record["priority"])
        assert confidence == 0.9

        # Test tag extraction (simulated)
        tags = []
        for i in range(1, 9):
            tag_value = mock_record.get(f"tag_{i}", "")
            if tag_value:
                tags.append((i, tag_value))

        assert len(tags) == 2
        assert tags[0][1] == "database"
        assert tags[1][1] == "performance"

    def test_category_coverage(self):
        """Test that all expected categories are covered."""
        classifier = DummyClassifier()

        test_queues = [
            ("Technical Support", "technical"),
            ("IT Support", "technical"),
            ("Billing and Payments", "billing"),
            ("Payment Issues", "billing"),
            ("Customer Service", "general"),
            ("Product Support", "general"),
            ("Sales", "general"),
            ("", "general"),  # Empty queue
        ]

        for queue, expected_category in test_queues:
            actual_category = classifier.map_queue_to_category(queue)
            assert (
                actual_category == expected_category
            ), f"Queue '{queue}' mapped to '{actual_category}', expected '{expected_category}'"


if __name__ == "__main__":
    # Run core tests
    pytest.main([__file__, "-v"])
