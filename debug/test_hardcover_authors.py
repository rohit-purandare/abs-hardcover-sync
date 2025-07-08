#!/usr/bin/env python3
"""
Test script to verify Hardcover API returns author data
"""

import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.hardcover_client import HardcoverClient


def main() -> None:
    """Test Hardcover author extraction"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config()
        hardcover_config = config.get_hardcover_config()
        hardcover = HardcoverClient(hardcover_config["token"])

        # Test connection
        if not hardcover.test_connection():
            logger.error("Failed to connect to Hardcover")
            return

        logger.info("Connected to Hardcover successfully")

        # Get user's books
        books = hardcover.get_user_books()
        logger.info(f"Found {len(books)} books in library")

        # Analyze author data
        books_with_authors = 0
        books_without_authors = 0

        for book in books[:10]:  # Check first 10 books
            book_data = book.get("book", {})
            contributions = book_data.get("contributions", [])

            if contributions and len(contributions) > 0:
                author_data = contributions[0].get("author")
                if author_data and author_data.get("name"):
                    author_name = author_data["name"]
                    title = book_data.get("title", "Unknown")
                    logger.info(f"✓ {title} by {author_name}")
                    books_with_authors += 1
                else:
                    title = book_data.get("title", "Unknown")
                    logger.warning(f"✗ {title}: Author data incomplete")
                    books_without_authors += 1
            else:
                title = book_data.get("title", "Unknown")
                logger.warning(f"✗ {title}: No contributions found")
                books_without_authors += 1

        logger.info(f"\nSummary:")
        logger.info(f"Books with authors: {books_with_authors}")
        logger.info(f"Books without authors: {books_without_authors}")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
