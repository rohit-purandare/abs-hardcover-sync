#!/usr/bin/env python3
"""
Test script to verify author integration during sync
"""

import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.sync_manager import SyncManager


def main() -> None:
    """Test author integration during sync"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config()

        # Initialize sync manager with dry run
        sync_manager = SyncManager(config, dry_run=True)
        logger.info("Sync manager initialized (dry run mode)")

        # Run a sync to populate the cache with author data
        logger.info("Running sync to populate cache with author data...")
        result = sync_manager.sync_progress()

        if result["success"]:
            logger.info(f"Sync completed successfully!")
            logger.info(f"Books processed: {result['books_processed']}")
            logger.info(f"Books synced: {result['books_synced']}")
            logger.info(f"Books auto-added: {result['books_auto_added']}")
            logger.info(f"Books skipped: {result['books_skipped']}")

            # Check cache for author data
            logger.info("\nChecking cache for author data...")
            cache_stats = sync_manager.get_cache_stats()
            logger.info(f"Cache stats: {cache_stats}")

            # Test getting books by a specific author
            test_authors = ["Andy Weir", "George R.R. Martin", "Ernest Cline"]

            for author in test_authors:
                books = sync_manager.get_books_by_author(author)
                if books:
                    logger.info(f"\nFound {len(books)} books by {author}:")
                    for book in books:
                        logger.info(
                            f"  - {book['title']} (ISBN: {book['isbn']}, Progress: {book['progress_percent']}%)"
                        )
                else:
                    logger.info(f"\nNo books found by {author}")

            logger.info("\n✅ Author integration test completed!")
        else:
            logger.error(f"Sync failed: {result['errors']}")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
