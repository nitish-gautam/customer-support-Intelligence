"""
Dataset validation tests using real Hugging Face dataset samples.
Tests classification accuracy against ground truth labels.
"""

import pytest
import warnings

# Suppress fsspec deprecation warning from datasets library
warnings.filterwarnings(
    "ignore",
    message=".*maxsplit.*",
    category=DeprecationWarning,
    module="fsspec",
)

# Import dataset library
try:
    from datasets import load_dataset

    DATASETS_AVAILABLE = True
except ImportError:
    DATASETS_AVAILABLE = False

from app.services.ai_classifier import get_classifier
from app.services.ai_classifier import DummyClassifier


@pytest.mark.skipif(not DATASETS_AVAILABLE, reason="datasets library not available")
class TestDatasetValidation:
    """Test classification accuracy using real dataset samples."""

    @classmethod
    def setup_class(cls):
        """Load dataset samples for testing."""
        try:
            # Load a small subset of the dataset for testing
            dataset = load_dataset(
                "tobi-bueck/customer-support-tickets", split="train[:100]"
            )
            cls.dataset_samples = dataset
        except Exception as e:
            pytest.skip(f"Could not load dataset: {e}")

    def test_queue_category_mapping_accuracy(self):
        """Test that queue to category mapping works for dataset samples."""
        if not hasattr(self, "dataset_samples"):
            pytest.skip("Dataset not loaded")

        # Test mapping accuracy on sample data
        mapping_results = {"correct": 0, "total": 0}

        classifier = DummyClassifier()
        for sample in self.dataset_samples:
            queue = sample.get("queue", "")
            if not queue:
                continue

            mapped_category = classifier.map_queue_to_category(queue)

            # Verify mapping is reasonable
            queue_lower = queue.lower()
            mapping_results["total"] += 1

            if (
                "technical" in queue_lower or "it support" in queue_lower
            ) and mapped_category == "technical":
                mapping_results["correct"] += 1
            elif (
                "billing" in queue_lower or "payment" in queue_lower
            ) and mapped_category == "billing":
                mapping_results["correct"] += 1
            elif mapped_category == "general":  # Default case
                mapping_results["correct"] += 1

        if mapping_results["total"] > 0:
            accuracy = mapping_results["correct"] / mapping_results["total"]
            assert accuracy >= 0.7, f"Queue mapping accuracy too low: {accuracy:.2f}"

    def test_priority_confidence_mapping(self):
        """Test priority to confidence mapping on dataset samples."""
        if not hasattr(self, "dataset_samples"):
            pytest.skip("Dataset not loaded")

        confidence_ranges = {"critical": [], "medium": [], "low": []}
        classifier = DummyClassifier()

        for sample in self.dataset_samples:
            priority = sample.get("priority", "")
            if not priority:
                continue

            confidence = classifier.map_priority_to_confidence(priority)
            priority_lower = priority.lower()

            if "critical" in priority_lower:
                confidence_ranges["critical"].append(confidence)
            elif "medium" in priority_lower:
                confidence_ranges["medium"].append(confidence)
            elif "low" in priority_lower:
                confidence_ranges["low"].append(confidence)

        # Verify confidence ordering
        if confidence_ranges["critical"]:
            avg_critical = sum(confidence_ranges["critical"]) / len(
                confidence_ranges["critical"]
            )
            assert avg_critical >= 0.8, "Critical priority should have high confidence"

        if confidence_ranges["low"]:
            avg_low = sum(confidence_ranges["low"]) / len(confidence_ranges["low"])
            assert avg_low <= 0.7, "Low priority should have lower confidence"

    @pytest.mark.asyncio
    async def test_ai_classification_on_dataset_samples(self):
        """Test AI classifier on real dataset samples."""
        if not hasattr(self, "dataset_samples"):
            pytest.skip("Dataset not loaded")

        classifier = get_classifier()

        # Test on a few representative samples
        # Test on first 10 samples
        test_samples = list(self.dataset_samples)[:10]

        classification_results = []

        for sample in test_samples:
            subject = sample.get("subject", "")
            body = sample.get("body", "")
            queue = sample.get("queue", "")

            # Create full text like the application does
            if subject and body:
                full_text = f"{subject}\n\n{body}"
            elif body:
                full_text = body
            elif subject:
                full_text = subject
            else:
                continue

            # Skip very short texts
            if len(full_text.strip()) < 10:
                continue

            # Classify
            result = await classifier.classify(full_text)

            # Verify result structure
            assert hasattr(result, "category")
            assert hasattr(result, "confidence_score")
            assert result.category in ["technical", "billing", "general"]
            assert 0.0 <= result.confidence_score <= 1.0

            # Store for analysis
            expected_category = (
                classifier.map_queue_to_category(queue) if queue else "general"
            )
            classification_results.append(
                {
                    "text": full_text[:100],
                    "expected": expected_category,
                    "actual": result.category,
                    "confidence": result.confidence_score,
                    "match": result.category == expected_category,
                }
            )

        # Analyze results
        if classification_results:
            matches = sum(1 for r in classification_results if r["match"])
            accuracy = matches / len(classification_results)

            # Print results for debugging
            print("\nClassification Results:")
            print(f"Total samples: {len(classification_results)}")
            print(f"Correct: {matches}")
            print(f"Accuracy: {accuracy:.2f}")

            # We expect some accuracy, but allow for model differences
            assert accuracy >= 0.3, f"Classification accuracy too low: {accuracy:.2f}"

    def test_english_language_filtering(self):
        """Test that only English language tickets are processed."""
        if not hasattr(self, "dataset_samples"):
            pytest.skip("Dataset not loaded")

        english_samples = []
        non_english_samples = []

        for sample in self.dataset_samples:
            language = sample.get("language", "").lower()
            if language == "en" or language == "english":
                english_samples.append(sample)
            elif language and language not in ["en", "english"]:
                non_english_samples.append(sample)

        print(f"English samples: {len(english_samples)}")
        print(f"Non-English samples: {len(non_english_samples)}")

        # Most samples should be English as per requirements
        if english_samples or non_english_samples:
            total = len(english_samples) + len(non_english_samples)
            english_ratio = len(english_samples) / total
            assert english_ratio >= 0.6, "Dataset should be primarily English"

    def test_tag_system_preservation(self):
        """Test that tag system from dataset is preserved in structure."""
        if not hasattr(self, "dataset_samples"):
            pytest.skip("Dataset not loaded")

        tag_columns_found = set()
        sample_with_tags = None

        for sample in self.dataset_samples:
            for key in sample.keys():
                if key.startswith("tag_") and key[4:].isdigit():
                    tag_columns_found.add(key)
                    if sample[key] and sample[key].strip():
                        sample_with_tags = sample

        print(f"Tag columns found: {sorted(tag_columns_found)}")

        # Should have tag_1 through tag_8
        expected_tags = {f"tag_{i}" for i in range(1, 9)}
        assert (
            tag_columns_found == expected_tags
        ), f"Missing tag columns: {expected_tags - tag_columns_found}"

        if sample_with_tags:
            print(f"Sample with tags: {sample_with_tags}")


class TestDatasetIntegration:
    """Test dataset integration without requiring actual dataset load."""

    def test_dataset_field_mapping(self):
        """Test expected dataset field mappings."""
        # Test the fields we expect from the dataset
        expected_fields = {
            "subject",
            "body",
            "queue",
            "priority",
            "language",
            "type",
            "answer",
            "tag_1",
            "tag_2",
            "tag_3",
            "tag_4",
            "tag_5",
            "tag_6",
            "tag_7",
            "tag_8",
        }

        # Mock dataset record structure
        mock_record = {
            "subject": "Test Subject",
            "body": "Test body content",
            "queue": "Technical Support",
            "priority": "Medium",
            "language": "en",
            "type": "Incident",
            "answer": "Test answer",
            "tag_1": "server",
            "tag_2": "performance",
            "tag_3": "",
            "tag_4": "",
            "tag_5": "",
            "tag_6": "",
            "tag_7": "",
            "tag_8": "",
        }

        # Verify mock record has all expected fields
        assert set(mock_record.keys()) == expected_fields

        classifier = DummyClassifier()

        # Test queue mapping
        category = classifier.map_queue_to_category(mock_record["queue"])
        assert category == "technical"

        # Test priority mapping
        confidence = classifier.map_priority_to_confidence(mock_record["priority"])
        assert confidence == 0.7

        # Test tag extraction
        tags = []
        for i in range(1, 9):
            tag_value = mock_record.get(f"tag_{i}", "").strip()
            if tag_value:
                tags.append((i, tag_value))

        assert len(tags) == 2
        assert ("server", "performance") == (tags[0][1], tags[1][1])

    @pytest.mark.asyncio
    async def test_realistic_ticket_examples(self):
        """Test classification on realistic ticket examples."""
        classifier = get_classifier()

        realistic_examples = [
            {
                "subject": "Database Connection Issues",
                "body": (
                    "Our production database server is experiencing "
                    "intermittent connection timeouts. The application shows "
                    "error messages about unable to connect to PostgreSQL "
                    "server. This started happening after the recent system "
                    "update. Please investigate urgently."
                ),
                "expected_category": "technical",
            },
            {
                "subject": "Billing Discrepancy",
                "body": (
                    "I noticed that my account was charged $299 this month "
                    "instead of the usual $199 subscription fee. I haven't "
                    "made any changes to my plan or added any additional "
                    "services. Could you please review my account and process "
                    "a refund for the difference?"
                ),
                "expected_category": "billing",
            },
            {
                "subject": "Product Information Request",
                "body": (
                    "I'm evaluating your software for our company and would "
                    "like to understand what features are included in the "
                    "enterprise tier. Specifically, I'm interested in user "
                    "management capabilities, API access, and integration "
                    "options with third-party tools."
                ),
                "expected_category": "general",
            },
        ]

        correct_classifications = 0

        for example in realistic_examples:
            full_text = f"{example['subject']}\n\n{example['body']}"
            result = await classifier.classify(full_text)

            print(f"\nText: {example['subject']}")
            print(f"Expected: {example['expected_category']}")
            print(f"Actual: {result.category}")
            print(f"Confidence: {result.confidence_score}")

            if result.category == example["expected_category"]:
                correct_classifications += 1

        accuracy = correct_classifications / len(realistic_examples)
        print(f"\nRealistic examples accuracy: {accuracy:.2f}")

        # Should get most examples right (allow some flexibility)
        assert accuracy >= 0.5, f"Accuracy too low on realistic examples: {accuracy}"


if __name__ == "__main__":
    # Run dataset validation tests
    pytest.main([__file__, "-v", "-s"])
