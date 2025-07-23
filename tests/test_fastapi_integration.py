"""
Comprehensive integration tests using FastAPI TestClient.
Provides actual code coverage and tests all components together.
"""

import os
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.models.ticket import Ticket
from app.models.classification import Classification
from app.services.ai_classifier import get_classifier


# Test database setup - Use SQLite with async support
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def override_get_db():
    """Override database dependency for testing."""
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
async def setup_test_database():
    """Create test database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Clean up test database file
    await test_engine.dispose()
    if os.path.exists("test.db"):
        os.remove("test.db")


class TestFastAPIIntegration:
    """Test FastAPI application with actual database integration."""

    def test_root_endpoint(self):
        """Test root endpoint returns correct response."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert data["services"]["database"] == "healthy"
        assert data["services"]["ai_classifier"] == "healthy"

    def test_create_ticket_with_text_only(self):
        """Test ticket creation with single text field."""
        payload = {
            "text": (
                "The application server is experiencing high CPU usage and "
                "frequent timeouts"
            )
        }

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["status"] == "processing"
        assert "message" in data
        assert isinstance(data["id"], int)

    def test_create_ticket_with_subject_body(self):
        """Test ticket creation with subject and body."""
        payload = {
            "subject": "Billing Discrepancy",
            "body": (
                "I notice my account was charged $199 instead of the "
                "expected $99 for the monthly subscription. Please "
                "investigate and provide a refund for the overcharge."
            ),
        }

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["status"] == "processing"

    def test_create_ticket_validation_errors(self):
        """Test validation error handling."""
        # Test empty payload
        response = client.post("/api/v1/requests/", json={})
        assert response.status_code == 422

        # Test text too short
        response = client.post("/api/v1/requests/", json={"text": "Short"})
        assert response.status_code == 422

        # Test body too short when only body provided
        response = client.post("/api/v1/requests/", json={"body": "Short"})
        assert response.status_code == 422

    def test_get_ticket_by_id(self):
        """Test retrieving a specific ticket."""
        # Create a ticket first
        payload = {
            "text": (
                "Database connection pool exhausted, application unable to "
                "process requests"
            )
        }

        create_response = client.post("/api/v1/requests/", json=payload)
        assert create_response.status_code == 201
        ticket_id = create_response.json()["id"]

        # Retrieve the ticket
        response = client.get(f"/api/v1/requests/{ticket_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == ticket_id
        assert "body" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Check classification if available
        if data.get("classification"):
            assert "category" in data["classification"]
            assert "confidence_score" in data["classification"]
            assert data["classification"]["category"] in [
                "technical",
                "billing",
                "general",
            ]

    def test_get_nonexistent_ticket(self):
        """Test 404 for non-existent ticket."""
        response = client.get("/api/v1/requests/99999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_list_tickets_basic(self):
        """Test basic ticket listing."""
        response = client.get("/api/v1/requests/")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)

    def test_list_tickets_with_pagination(self):
        """Test ticket listing with pagination parameters."""
        response = client.get("/api/v1/requests/?limit=5&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) <= 5
        assert data["limit"] == 5
        assert data["offset"] == 0

    def test_list_tickets_with_category_filter(self):
        """Test filtering tickets by category."""
        # Create tickets of different categories first
        technical_ticket = {
            "text": (
                "Server memory leak causing application crashes and "
                "performance degradation"
            )
        }
        billing_ticket = {
            "subject": "Payment Issue",
            "body": (
                "Double charged on my account this month, need refund for "
                "duplicate transaction"
            ),
        }

        client.post("/api/v1/requests/", json=technical_ticket)
        client.post("/api/v1/requests/", json=billing_ticket)

        # Test category filtering
        response = client.get("/api/v1/requests/?category=technical")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data

        # If classifications exist, verify they match the filter
        for item in data["items"]:
            if item.get("classification"):
                assert item["classification"]["category"] == "technical"

    def test_stats_endpoint_basic(self):
        """Test statistics endpoint."""
        response = client.get("/api/v1/stats/")
        assert response.status_code == 200

        data = response.json()
        assert "total_tickets" in data
        assert "period_days" in data
        assert "categories" in data
        assert "daily_counts" in data
        assert "average_confidence" in data
        assert data["period_days"] == 7  # default

        # Verify categories structure
        for category in data["categories"]:
            assert "category" in category
            assert "count" in category
            assert "percentage" in category
            assert category["category"] in ["technical", "billing", "general"]

    def test_stats_endpoint_custom_period(self):
        """Test statistics with custom time period."""
        response = client.get("/api/v1/stats/?days=30")
        assert response.status_code == 200

        data = response.json()
        assert data["period_days"] == 30


class TestAIClassifierIntegration:
    """Test AI classifier service integration."""

    def test_classifier_initialization(self):
        """Test that classifier can be initialized."""
        classifier = get_classifier()
        assert classifier is not None
        assert hasattr(classifier, "classify")

    def test_technical_classification(self):
        """Test AI classification for technical tickets."""
        payload = {
            "text": (
                "The PostgreSQL database server is experiencing connection "
                "timeouts and high CPU usage during peak hours"
            )
        }

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201
        ticket_id = response.json()["id"]

        # Retrieve and check classification
        response = client.get(f"/api/v1/requests/{ticket_id}")
        data = response.json()

        if data.get("classification"):
            classification = data["classification"]
            assert classification["category"] in ["technical", "billing", "general"]
            assert 0.0 <= classification["confidence_score"] <= 1.0
            assert "model_name" in classification

            # Technical content should likely be classified as technical
            # (though we allow flexibility for different AI models)
            assert classification["category"] == "technical"

    def test_billing_classification(self):
        """Test AI classification for billing tickets."""
        payload = {
            "subject": "Subscription Billing Error",
            "body": (
                "My credit card was charged $299 instead of the agreed "
                "$199 monthly rate. Please process a refund for the "
                "difference."
            ),
        }

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201
        ticket_id = response.json()["id"]

        # Retrieve and check classification
        response = client.get(f"/api/v1/requests/{ticket_id}")
        data = response.json()

        if data.get("classification"):
            classification = data["classification"]
            assert classification["category"] == "billing"
            assert 0.0 <= classification["confidence_score"] <= 1.0

    def test_general_classification(self):
        """Test AI classification for general inquiries."""
        payload = {
            "text": (
                "I would like to learn more about your enterprise features "
                "and pricing options for large teams"
            )
        }

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201
        ticket_id = response.json()["id"]

        # Retrieve and check classification
        response = client.get(f"/api/v1/requests/{ticket_id}")
        data = response.json()

        if data.get("classification"):
            classification = data["classification"]
            assert classification["category"] == "general"


class TestDatabaseIntegration:
    """Test database models and relationships."""

    @pytest.mark.asyncio
    async def test_ticket_creation_in_database(self):
        """Test that tickets are properly stored in database."""
        payload = {
            "subject": "Database Test",
            "body": (
                "This is a test ticket to verify database storage " "functionality"
            ),
        }

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201
        ticket_id = response.json()["id"]

        # Verify ticket exists in database
        async with TestingSessionLocal() as db:
            from sqlalchemy import select

            result = await db.execute(select(Ticket).filter(Ticket.id == ticket_id))
            ticket = result.scalar_one_or_none()
            assert ticket is not None
            assert ticket.subject == "Database Test"
            assert "test ticket" in ticket.body.lower()

    @pytest.mark.asyncio
    async def test_classification_relationship(self):
        """Test ticket-classification relationship."""
        payload = {
            "text": (
                "Network infrastructure experiencing intermittent "
                "connectivity issues affecting production systems"
            )
        }

        response = client.post("/api/v1/requests/", json=payload)
        ticket_id = response.json()["id"]

        # Check database relationships
        async with TestingSessionLocal() as db:
            from sqlalchemy import select

            result = await db.execute(select(Ticket).filter(Ticket.id == ticket_id))
            ticket = result.scalar_one_or_none()
            assert ticket is not None

            # Classification might be created asynchronously
            result = await db.execute(
                select(Classification).filter(Classification.ticket_id == ticket_id)
            )
            classification = result.scalar_one_or_none()

            if classification:
                assert classification.ticket_id == ticket_id
                assert classification.category in ["technical", "billing", "general"]
                assert 0.0 <= classification.confidence_score <= 1.0

    def test_error_handling(self):
        """Test API error handling."""
        # Test malformed JSON
        response = client.post(
            "/api/v1/requests/",
            content="invalid json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

        # Test missing required fields
        response = client.post("/api/v1/requests/", json={"invalid_field": "value"})
        assert response.status_code == 422


class TestDatasetAccuracy:
    """Test classification accuracy using realistic dataset examples."""

    @pytest.mark.parametrize(
        "text,expected_category",
        [
            ("Server memory leak causing application crashes", "technical"),
            ("Database connection timeout errors in production", "technical"),
            (
                "Invoice shows incorrect billing amount for last month",
                "billing",
            ),
            ("Refund request for cancelled subscription service", "billing"),
            ("What features are included in the enterprise plan?", "general"),
            ("Need information about your API rate limits", "general"),
        ],
    )
    def test_classification_accuracy(self, text, expected_category):
        """Test that classification matches expected categories."""
        payload = {"text": text}

        response = client.post("/api/v1/requests/", json=payload)
        assert response.status_code == 201
        ticket_id = response.json()["id"]

        # Get classification result
        response = client.get(f"/api/v1/requests/{ticket_id}")
        data = response.json()

        if data.get("classification"):
            actual_category = data["classification"]["category"]
            assert (
                actual_category == expected_category
            ), f"Text '{text}' classified as '{actual_category}', expected '{expected_category}'"

    def test_confidence_scores_reasonable(self):
        """Test that confidence scores are reasonable for clear examples."""
        clear_examples = [
            "Critical database server failure causing complete service outage",
            "Billing error: charged twice for the same monthly subscription",
            "General inquiry about your company's privacy policy",
        ]

        for text in clear_examples:
            payload = {"text": text}

            response = client.post("/api/v1/requests/", json=payload)
            ticket_id = response.json()["id"]

            response = client.get(f"/api/v1/requests/{ticket_id}")
            data = response.json()

            if data.get("classification"):
                confidence = data["classification"]["confidence_score"]
                # Clear examples should have reasonable confidence
                assert (
                    confidence >= 0.6
                ), f"Low confidence ({confidence}) for clear example: '{text}'"
