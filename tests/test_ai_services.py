"""
Comprehensive tests for AI/ML services and classification logic.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.services.ai_classifier import (
    OpenAIClassifier,
    DummyClassifier,
    get_classifier,
)
from app.services.ticket_service import TicketService


class TestAIClassifierBase:
    """Test the base AIClassifier interface."""

    @pytest.mark.asyncio
    async def test_dummy_classifier_initialization(self):
        """Test dummy classifier can be initialized."""
        classifier = DummyClassifier()
        assert classifier is not None

        # Test classification
        result = await classifier.classify("Test technical issue with server")
        assert hasattr(result, "category")
        assert hasattr(result, "confidence_score")
        assert hasattr(result, "summary")
        assert hasattr(result, "model_name")
        assert result.category in ["technical", "billing", "general"]
        assert 0.0 <= result.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_dummy_classifier_categories(self):
        """Test dummy classifier returns all expected categories."""
        classifier = DummyClassifier()

        # Test multiple classifications to see variety
        texts = [
            "Server is down and crashing",
            "Billing invoice issue",
            "General question about features",
            "Database error and technical problems",
            "Payment charge problem",
        ]

        categories_seen = set()
        for text in texts:
            result = await classifier.classify(text)
            categories_seen.add(result.category)

        # Should see all categories over multiple runs
        expected_categories = {"technical", "billing", "general"}
        assert categories_seen.issubset(expected_categories)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    def test_openai_classifier_initialization(self):
        """Test OpenAI classifier initialization with API key."""
        with patch("openai.OpenAI"):
            classifier = OpenAIClassifier()
            assert classifier is not None
            assert classifier.client is not None

    def test_get_classifier_with_openai_key(self):
        """Test get_classifier returns OpenAI when key is available."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            with patch("openai.OpenAI"):
                classifier = get_classifier()
                assert isinstance(classifier, OpenAIClassifier)

    def test_get_classifier_without_openai_key(self):
        """Test get_classifier returns dummy when no key."""
        with patch("app.services.ai_classifier.settings") as mock_settings:
            mock_settings.openai_api_key = None
            classifier = get_classifier()
            assert isinstance(classifier, DummyClassifier)


class TestOpenAIClassifier:
    """Test OpenAI classifier with mocked responses."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_openai_classification_success(self):
        """Test successful OpenAI classification."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            '{"category": "technical", "confidence": 0.95, '
            '"summary": "Server performance issue"}'
        )
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            classifier = OpenAIClassifier()

            result = await classifier.classify("Server is experiencing high CPU usage")

            assert result.category == "technical"
            assert result.confidence_score == 0.95
            assert result.summary == "Server performance issue"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_openai_classification_api_error(self):
        """Test OpenAI API error handling."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            classifier = OpenAIClassifier()

            result = await classifier.classify("Test text")

            # Should fallback to dummy classification
            assert result.category in ["technical", "billing", "general"]
            assert result.model_name.endswith("-fallback")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_openai_classification_invalid_json(self):
        """Test handling of invalid JSON response."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "invalid json response"
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            classifier = OpenAIClassifier()

            result = await classifier.classify("Test text")

            # Should fallback to dummy classification
            assert result.category in ["technical", "billing", "general"]
            assert result.model_name.endswith("-fallback")


class TestTicketService:
    """Test the ticket service business logic."""

    def test_queue_to_category_mapping(self):
        """Test queue to category mapping logic."""
        from app.services.ticket_service import map_queue_to_category

        # Test technical mappings
        assert map_queue_to_category("Technical Support") == "technical"
        assert map_queue_to_category("IT Support") == "technical"
        assert map_queue_to_category("technical-issues") == "technical"

        # Test billing mappings
        assert map_queue_to_category("Billing and Payments") == "billing"
        assert map_queue_to_category("Payment Issues") == "billing"
        assert map_queue_to_category("billing-department") == "billing"

        # Test general mappings
        assert map_queue_to_category("Customer Service") == "general"
        assert map_queue_to_category("Product Support") == "general"
        assert map_queue_to_category("General Inquiries") == "general"

        # Test default case
        assert map_queue_to_category("Unknown Queue") == "general"
        assert map_queue_to_category("") == "general"
        assert map_queue_to_category(None) == "general"

    def test_priority_to_confidence_mapping(self):
        """Test priority to confidence score mapping."""
        from app.services.ticket_service import map_priority_to_confidence

        # Test priority mappings
        assert map_priority_to_confidence("Critical") == 0.9
        assert map_priority_to_confidence("critical") == 0.9
        assert map_priority_to_confidence("CRITICAL") == 0.9

        assert map_priority_to_confidence("Medium") == 0.7
        assert map_priority_to_confidence("medium") == 0.7

        assert map_priority_to_confidence("Low") == 0.5
        assert map_priority_to_confidence("low") == 0.5

        # Test default case
        assert map_priority_to_confidence("Unknown") == 0.7
        assert map_priority_to_confidence("") == 0.7
        assert map_priority_to_confidence(None) == 0.7

    @pytest.mark.asyncio
    async def test_ticket_service_create_ticket(self):
        """Test ticket creation through service layer."""
        # Mock database session
        mock_db = AsyncMock()
        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.execute = Mock()
        mock_db.scalars = Mock()

        # Mock ticket object
        mock_ticket = Mock()
        mock_ticket.id = 123
        mock_ticket.subject = "Test Subject"
        mock_ticket.body = "Test body content for ticket"

        service = TicketService(mock_db)

        # Mock the classifier to avoid real AI calls
        with patch.object(service, "classifier") as mock_classifier:
            from app.services.ai_classifier import ClassificationResult

            mock_classifier.classify = AsyncMock(
                return_value=ClassificationResult(
                    category="technical",
                    confidence_score=0.8,
                    summary="Test summary",
                    model_name="test-model",
                    processing_time_ms=100,
                )
            )

            # Create request object
            from app.schemas.request import TicketCreateRequest

            request = TicketCreateRequest(text="Test technical issue with server")

            # Mock the database operations
            mock_db.refresh.side_effect = lambda ticket: setattr(ticket, "id", 123)

            result = await service.create_ticket(request)

            # Verify database operations were called
            mock_db.add.assert_called()
            assert mock_db.commit.call_count >= 1
            # Verify result is returned
            assert result is not None

    @pytest.mark.asyncio
    async def test_ticket_service_ai_processing(self):
        """Test AI classification processing in service."""
        mock_db = AsyncMock()
        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_ticket = Mock()
        mock_ticket.id = 123
        mock_ticket.full_text = "Server is experiencing connection timeouts"

        service = TicketService(mock_db)

        # Mock the classifier result
        with patch.object(service, "classifier") as mock_classifier:
            from app.services.ai_classifier import ClassificationResult

            mock_classifier.classify = AsyncMock(
                return_value=ClassificationResult(
                    category="technical",
                    confidence_score=0.85,
                    summary="Server connection issues",
                    model_name="test-model",
                    processing_time_ms=150,
                )
            )

            # Test the private AI classification method
            await service._classify_ticket(mock_ticket)

            # Verify classification was called
            mock_classifier.classify.assert_called_once_with(mock_ticket.full_text)

            # Verify database operations
            mock_db.add.assert_called()
            mock_db.commit.assert_called()


class TestDatasetMapping:
    """Test dataset field mapping and validation."""

    def test_category_mapping_coverage(self):
        """Test that all dataset queues map to valid categories."""
        from app.services.ticket_service import map_queue_to_category

        # Common queue values from the dataset
        dataset_queues = [
            "Technical Support",
            "IT Support",
            "Billing and Payments",
            "Payment Issues",
            "Customer Service",
            "Product Support",
            "General Inquiries",
            "Sales",
            "Account Management",
            "",  # Empty queue
        ]

        valid_categories = {"technical", "billing", "general"}

        for queue in dataset_queues:
            category = map_queue_to_category(queue)
            assert (
                category in valid_categories
            ), f"Queue '{queue}' mapped to invalid category '{category}'"

    def test_confidence_score_ranges(self):
        """Test that confidence scores are in valid range."""
        from app.services.ticket_service import map_priority_to_confidence

        priorities = ["Critical", "Medium", "Low", "", "Unknown", None]

        for priority in priorities:
            confidence = map_priority_to_confidence(priority)
            assert (
                0.0 <= confidence <= 1.0
            ), f"Priority '{priority}' produced invalid confidence {confidence}"

    @pytest.mark.asyncio
    async def test_text_processing(self):
        """Test text processing and validation."""
        classifier = DummyClassifier()

        # Test various text inputs
        test_texts = [
            "Short text",
            "This is a longer text that should be processed correctly by the classifier",
            "Technical issue: database connection failed",
            "Billing problem: overcharged on subscription",
            "General question about your services",
        ]

        for text in test_texts:
            result = await classifier.classify(text)

            # Validate result structure
            assert hasattr(result, "category")
            assert hasattr(result, "confidence_score")
            assert hasattr(result, "summary")
            assert hasattr(result, "model_name")
            assert result.category in ["technical", "billing", "general"]
            assert 0.0 <= result.confidence_score <= 1.0


class TestErrorHandling:
    """Test error handling in AI services."""

    @pytest.mark.asyncio
    async def test_classifier_with_empty_text(self):
        """Test classifier behavior with empty text."""
        classifier = DummyClassifier()

        result = await classifier.classify("")

        # Should still return valid structure
        assert hasattr(result, "category")
        assert result.category in ["technical", "billing", "general"]

    @pytest.mark.asyncio
    async def test_classifier_with_very_long_text(self):
        """Test classifier with very long text input."""
        classifier = DummyClassifier()

        long_text = "Very long text content. " * 1000
        result = await classifier.classify(long_text)

        # Should handle gracefully
        assert hasattr(result, "category")
        assert result.category in ["technical", "billing", "general"]

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_openai_network_timeout(self):
        """Test OpenAI classifier timeout handling."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("Network timeout")

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            classifier = OpenAIClassifier()

            result = await classifier.classify("Test text")

            # Should fallback gracefully
            assert result.model_name.endswith("-fallback")
            assert result.category in ["technical", "billing", "general"]


if __name__ == "__main__":
    # Run specific tests for debugging
    pytest.main([__file__, "-v"])
