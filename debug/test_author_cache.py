#!/usr/bin/env python3
"""
Test script to verify author caching functionality
"""

import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_manager import BookCache


def main():
    """Test author caching functionality"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Initialize cache
        cache = BookCache()
        logger.info("Cache initialized")

        # Test storing a book with author
        test_isbn = "9780593135228"
        test_title = "Project Hail Mary"
        test_author = "Andy Weir"
        test_edition_id = 12345

        logger.info(f"Storing test book: {test_title} by {test_author}")
        cache.store_edition_mapping(test_isbn, test_title, test_edition_id, test_author)

        # Test retrieving books by author
        logger.info(f"Retrieving books by {test_author}")
        books = cache.get_books_by_author(test_author)

        if books:
            logger.info(f"Found {len(books)} books by {test_author}:")
            for book in books:
                logger.info(
                    f"  - {book['title']} (ISBN: {book['isbn']}, Edition: {book['edition_id']})"
                )
        else:
            logger.warning(f"No books found by {test_author}")

        # Test with non-existent author
        logger.info("Testing with non-existent author")
        books = cache.get_books_by_author("Non-existent Author")
        logger.info(f"Found {len(books)} books by non-existent author")

        # Test cache stats
        stats = cache.get_cache_stats()
        logger.info(f"Cache stats: {stats}")

        logger.info("Author caching test completed successfully!")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
