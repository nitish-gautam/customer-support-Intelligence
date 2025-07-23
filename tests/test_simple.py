"""
Simplified API tests that work with the existing database.
"""

import pytest
import requests
import json
from time import sleep


class TestSimpleAPI:
    """Test API endpoints using requests library."""

    BASE_URL = "http://localhost:8000"

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "services" in data
        assert data["services"]["database"] == "healthy"
        assert data["services"]["ai_classifier"] == "healthy"

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = requests.get(f"{self.BASE_URL}/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data

    def test_create_technical_ticket(self):
        """Test creating a technical support ticket."""
        payload = {
            "text": "The database server keeps crashing with memory allocation errors"
        }

        response = requests.post(
            f"{self.BASE_URL}/api/v1/requests/",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["status"] == "processing"
        assert "message" in data

        # Wait a moment for AI processing
        sleep(2)

        # Verify the ticket was classified correctly
        ticket_response = requests.get(f"{self.BASE_URL}/api/v1/requests/{data['id']}")
        assert ticket_response.status_code == 200

        ticket_data = ticket_response.json()
        assert ticket_data["classification"]["category"] == "technical"
        assert ticket_data["classification"]["confidence_score"] >= 0.8
        assert ticket_data["classification"]["model_name"] in [
            "gpt-4o",
            "gpt-4o-fallback",
            "dummy-classifier",
        ]
        assert "summary" in ticket_data["classification"]

    def test_create_billing_ticket(self):
        """Test creating a billing support ticket."""
        payload = {
            "subject": "Payment Issue",
            "body": "I was charged twice for my subscription this month. Please refund the duplicate charge.",
        }

        response = requests.post(
            f"{self.BASE_URL}/api/v1/requests/",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 201
        data = response.json()

        # Wait for AI processing
        sleep(2)

        # Verify classification
        ticket_response = requests.get(f"{self.BASE_URL}/api/v1/requests/{data['id']}")
        ticket_data = ticket_response.json()

        assert ticket_data["classification"]["category"] == "billing"
        assert ticket_data["classification"]["confidence_score"] >= 0.8

    def test_create_general_ticket(self):
        """Test creating a general support ticket."""
        payload = {
            "text": "I would like to know more about your premium features and pricing plans"
        }

        response = requests.post(
            f"{self.BASE_URL}/api/v1/requests/",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 201
        data = response.json()

        # Wait for AI processing
        sleep(2)

        # Verify classification
        ticket_response = requests.get(f"{self.BASE_URL}/api/v1/requests/{data['id']}")
        ticket_data = ticket_response.json()

        assert ticket_data["classification"]["category"] == "general"

    def test_list_tickets_with_category_filter(self):
        """Test listing tickets with category filter."""
        # Test billing filter
        response = requests.get(
            f"{self.BASE_URL}/api/v1/requests/?category=billing&limit=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data

        # All returned items should be billing category
        for item in data["items"]:
            if item.get("classification"):
                assert item["classification"]["category"] == "billing"

    def test_list_tickets_pagination(self):
        """Test ticket listing with pagination."""
        response = requests.get(f"{self.BASE_URL}/api/v1/requests/?limit=3&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) <= 3
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_get_statistics(self):
        """Test statistics endpoint."""
        response = requests.get(f"{self.BASE_URL}/api/v1/stats/?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "total_tickets" in data
        assert "period_days" in data
        assert "categories" in data
        assert "daily_counts" in data
        assert "average_confidence" in data

        # Verify categories structure
        for category in data["categories"]:
            assert "category" in category
            assert "count" in category
            assert "percentage" in category
            assert category["category"] in ["technical", "billing", "general"]

    def test_validation_error(self):
        """Test validation error handling."""
        payload = {"text": "Short"}  # Too short - less than 10 characters

        response = requests.post(
            f"{self.BASE_URL}/api/v1/requests/",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_nonexistent_ticket(self):
        """Test retrieving non-existent ticket."""
        response = requests.get(f"{self.BASE_URL}/api/v1/requests/99999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_category_mapping_accuracy(self):
        """Test that category mapping works correctly for different types."""
        test_cases = [
            ("Server memory leak causing application crashes", "technical"),
            ("Invoice shows incorrect billing amount", "billing"),
            ("What features are included in the enterprise plan?", "general"),
            ("Database connection timeout errors", "technical"),
            ("Refund request for cancelled subscription", "billing"),
        ]

        for text, expected_category in test_cases:
            payload = {"text": text}

            # Create ticket
            response = requests.post(
                f"{self.BASE_URL}/api/v1/requests/",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 201
            ticket_id = response.json()["id"]

            # Wait for processing
            sleep(2)

            # Check classification
            ticket_response = requests.get(
                f"{self.BASE_URL}/api/v1/requests/{ticket_id}"
            )
            ticket_data = ticket_response.json()

            assert ticket_data["classification"]["category"] == expected_category, (
                f"Text '{text}' was classified as "
                f"'{ticket_data['classification']['category']}' instead of "
                f"'{expected_category}'"
            )


if __name__ == "__main__":
    # Run tests manually if server is running
    test = TestSimpleAPI()
    print("🧪 Running API tests...")

    try:
        test.test_health_endpoint()
        print("✅ Health endpoint test passed")

        test.test_create_technical_ticket()
        print("✅ Technical ticket creation test passed")

        test.test_create_billing_ticket()
        print("✅ Billing ticket creation test passed")

        test.test_get_statistics()
        print("✅ Statistics test passed")

        print("🎉 All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
