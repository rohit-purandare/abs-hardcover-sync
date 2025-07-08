#!/usr/bin/env python3
"""
Test script to verify author caching functionality
"""

import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sync_manager import BookCache


def main() -> None:
    """Test author cache functionality"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Initialize cache
        cache = BookCache()
        logger.info("Cache initialized")

        # Test storing and retrieving author data
        test_isbn = "9780593099322"
        test_title = "Project Hail Mary"
        test_author = "Andy Weir"
        test_edition_id = 12345

        logger.info(f"Testing with: {test_title} by {test_author}")

        # Store edition mapping with author
        cache.store_edition_mapping(test_isbn, test_title, test_edition_id, test_author)
        logger.info("Stored edition mapping with author")

        # Retrieve edition
        retrieved_edition = cache.get_edition_for_book(test_isbn, test_title)
        logger.info(f"Retrieved edition ID: {retrieved_edition}")

        # Check if author is stored
        with cache._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT author FROM books WHERE isbn = ? AND title = ?",
                (test_isbn, test_title.lower().strip()),
            )
            result = cursor.fetchone()
            if result and result["author"]:
                logger.info(f"✅ Author stored: {result['author']}")
            else:
                logger.warning("❌ Author not found in cache")

        # Test getting books by author
        books_by_author = cache.get_books_by_author(test_author)
        logger.info(f"Found {len(books_by_author)} books by {test_author}")

        for book in books_by_author:
            logger.info(f"  - {book['title']} (ISBN: {book['isbn']})")

        logger.info("✅ Author cache test completed!")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
