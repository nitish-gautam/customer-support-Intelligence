"""
Script to seed the database with data from Hugging Face dataset.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, get_sync_db
from app.models.classification import Classification, TicketTag
from app.models.ticket import Ticket
from app.services.ai_classifier import get_classifier

# Import Hugging Face datasets library
try:
    from datasets import load_dataset
except ImportError:
    print("Error: datasets library not installed. Run: pip install datasets")
    sys.exit(1)


def map_queue_to_category(queue: str) -> str:
    """Map dataset queue to our categories."""
    if not queue:
        return "general"

    queue_lower = queue.lower()

    if "technical" in queue_lower or "it support" in queue_lower:
        return "technical"
    elif "billing" in queue_lower or "payment" in queue_lower:
        return "billing"
    else:
        return "general"


def map_priority_to_confidence(priority: str) -> float:
    """Map dataset priority to confidence scores."""
    if not priority:
        return 0.7

    priority_lower = priority.lower()

    mapping = {
        "critical": 0.9,
        "high": 0.9,
        "medium": 0.7,
        "low": 0.5,
    }

    return mapping.get(priority_lower, 0.7)


async def seed_database(limit: int = 100, dataset_name: str = None) -> None:
    """
    Seed database with sample data from Hugging Face dataset.

    Args:
        limit: Maximum number of records to seed
        dataset_name: Hugging Face dataset name (defaults to Tobi-Bueck/customer-support-tickets)
    """
    if dataset_name is None:
        dataset_name = getattr(settings, 'dataset_name', 'Tobi-Bueck/customer-support-tickets')

    print(f"Loading Hugging Face dataset: {dataset_name}")
    
    # Load dataset from Hugging Face
    try:
        hf_token = os.getenv("HUGGINGFACE_API_KEY")
        if not hf_token:
            print("Warning: HUGGINGFACE_API_KEY not found in environment")
        
        dataset = load_dataset(
            dataset_name,
            token=hf_token if hf_token else None,
            cache_dir=getattr(settings, 'dataset_cache_dir', './data/cache')
        )
        print(f"Dataset loaded successfully. Available splits: {list(dataset.keys())}")
        
        # Use train split or first available split
        if 'train' in dataset:
            data = dataset['train']
        else:
            split_name = list(dataset.keys())[0]
            data = dataset[split_name]
            print(f"Using split: {split_name}")
            
    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("Make sure you have access to the dataset and proper authentication")
        return

    # Get database session
    db = get_sync_db()

    # Check if data already exists
    existing_count = db.query(Ticket).count()
    if existing_count > 0:
        print(f"Database already contains {existing_count} tickets.")
        response = input("Do you want to continue? (y/n): ")
        if response.lower() != "y":
            print("Seeding cancelled.")
            return

    # Process records
    created_count = 0
    processed_count = 0

    print(f"Processing up to {limit} records from {len(data)} total records...")
    
    for record in data:
        if created_count >= limit:
            break
            
        processed_count += 1
        
        # Skip non-English records for now (as per requirements)
        language = record.get("language", "").lower()
        if language != "en":
            if processed_count <= 20:  # Show first 20 skipped languages for debugging
                print(f"Skipping record {processed_count}: language={language}")
            continue

        try:
            # Create ticket
            ticket = Ticket(
                subject=record.get("subject") or None,
                body=record.get("body", ""),
                answer=record.get("answer") or None,
                original_type=record.get("type") or None,
                original_queue=record.get("queue") or None,
                original_priority=record.get("priority") or None,
                language=record.get("language", "en"),
            )

            db.add(ticket)
            db.flush()  # Get ticket ID

            # Create classification based on dataset
            category = map_queue_to_category(record.get("queue", ""))
            confidence = map_priority_to_confidence(record.get("priority", ""))

            # Extract summary from answer field
            answer = record.get("answer", "")
            summary = None
            if answer:
                # Take first sentence as summary
                sentences = answer.split(".")
                if sentences:
                    summary = sentences[0].strip()[:150]

            classification = Classification(
                ticket_id=ticket.id,
                category=category,
                confidence_score=confidence,
                summary=summary,
                model_name="dataset-mapping",
                processing_time_ms=0,
            )

            db.add(classification)

            # Add tags if present
            for tag_num in range(1, 9):
                tag_value = record.get(f"tag_{tag_num}", "")
                if tag_value and tag_value.strip():
                    tag = TicketTag(
                        ticket_id=ticket.id,
                        tag_position=tag_num,
                        tag_value=tag_value.strip(),
                    )
                    db.add(tag)

            # Commit every 10 records
            if (created_count + 1) % 10 == 0:
                db.commit()
                print(f"Processed {created_count + 1} records...")

            created_count += 1

        except Exception as e:
            print(f"Error processing record {processed_count}: {e}")
            db.rollback()
            continue

    # Final commit
    db.commit()
    db.close()

    print(f"\nSeeding completed!")
    print(f"Created {created_count} tickets with classifications")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with Hugging Face dataset")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of records to seed (default: 100)",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        help="Hugging Face dataset name (defaults to Tobi-Bueck/customer-support-tickets)",
    )

    args = parser.parse_args()

    # Run async function
    asyncio.run(seed_database(args.limit, args.dataset_name))


if __name__ == "__main__":
    main()
