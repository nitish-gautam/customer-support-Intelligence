"""
Basic API tests for the customer support system.
Uses requests to test against running server.
"""

import requests
from time import sleep


class TestHealthEndpoints:
    """Test health check endpoints."""

    BASE_URL = "http://localhost:8000"

    def test_root_endpoint(self):
        """Test root endpoint returns expected response."""
        response = requests.get(f"{self.BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data


class TestRequestEndpoints:
    """Test request CRUD endpoints."""

    BASE_URL = "http://localhost:8000"

    def test_create_request_with_text(self):
        """Test creating request with single text field."""
        payload = {
            "text": "The data analytics platform crashed due to insufficient RAM"
        }

        response = requests.post(f"{self.BASE_URL}/api/v1/requests/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["status"] == "processing"
        assert "message" in data

    def test_create_request_with_subject_body(self):
        """Test creating request with subject and body."""
        payload = {
            "subject": "Billing Issue",
            "body": "I was overcharged on my last invoice. Please review and refund.",
        }

        response = requests.post(f"{self.BASE_URL}/api/v1/requests/", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["status"] == "processing"

    def test_create_request_validation_error(self):
        """Test validation error for invalid request."""
        payload = {"body": "Too short"}  # Less than 10 characters

        response = requests.post(f"{self.BASE_URL}/api/v1/requests/", json=payload)
        assert response.status_code == 422

        data = response.json()
        assert "errors" in data

    def test_get_request(self):
        """Test retrieving a specific request."""
        # First create a request
        create_response = requests.post(
            f"{self.BASE_URL}/api/v1/requests/",
            json={"text": "Test ticket for retrieval testing"},
        )
        ticket_id = create_response.json()["id"]

        # Wait a moment for processing
        sleep(1)

        # Retrieve it
        response = requests.get(f"{self.BASE_URL}/api/v1/requests/{ticket_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == ticket_id
        assert "body" in data
        assert "created_at" in data

    def test_get_nonexistent_request(self):
        """Test retrieving non-existent request returns 404."""
        response = requests.get(f"{self.BASE_URL}/api/v1/requests/99999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_list_requests(self):
        """Test listing requests with pagination."""
        # List requests
        response = requests.get(f"{self.BASE_URL}/api/v1/requests?limit=3")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) <= 3

    def test_list_requests_with_category_filter(self):
        """Test filtering requests by category."""
        response = requests.get(f"{self.BASE_URL}/api/v1/requests?category=technical")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        # All returned items should have technical category
        # (if classification was completed)


class TestStatsEndpoint:
    """Test statistics endpoint."""

    BASE_URL = "http://localhost:8000"

    def test_get_stats(self):
        """Test getting statistics."""
        response = requests.get(f"{self.BASE_URL}/api/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_tickets" in data
        assert "period_days" in data
        assert data["period_days"] == 7  # Default
        assert "categories" in data
        assert "daily_counts" in data
        assert "average_confidence" in data

    def test_get_stats_custom_period(self):
        """Test getting statistics for custom period."""
        response = requests.get(f"{self.BASE_URL}/api/v1/stats?days=30")
        assert response.status_code == 200

        data = response.json()
        assert data["period_days"] == 30
