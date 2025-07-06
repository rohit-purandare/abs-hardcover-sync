#!/usr/bin/env python3
"""
Test script to verify Hardcover API returns author data
"""

import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from hardcover_client import HardcoverClient


def main():
    """Test Hardcover author data retrieval"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config()

        # Initialize Hardcover client
        hardcover = HardcoverClient(config.HARDCOVER_TOKEN)
        logger.info("Hardcover client initialized")

        # Test connection
        if not hardcover.test_connection():
            logger.error("Failed to connect to Hardcover API")
            return

        # Get user books (limited to first 5 for testing)
        logger.info("Fetching user books from Hardcover...")
        books = hardcover.get_user_books()

        if not books:
            logger.warning("No books found in Hardcover library")
            return

        logger.info(f"Found {len(books)} books in Hardcover library")

        # Check first few books for author data
        books_with_authors = 0
        for i, book in enumerate(books[:5]):  # Check first 5 books
            book_data = book.get("book", {})
            title = book_data.get("title", "Unknown")
            contributions = book_data.get("contributions", [])

            logger.info(f"\nBook {i+1}: {title}")

            if contributions:
                authors = []
                for contribution in contributions:
                    author_data = contribution.get("author")
                    if author_data:
                        author_name = author_data.get("name", "Unknown")
                        author_id = author_data.get("id", "Unknown")
                        authors.append(f"{author_name} (ID: {author_id})")

                if authors:
                    books_with_authors += 1
                    logger.info(f"  Authors: {', '.join(authors)}")
                else:
                    logger.warning(f"  No author data in contributions")
            else:
                logger.warning(f"  No contributions found")

        logger.info(f"\nSummary: {books_with_authors}/5 books had author data")

        if books_with_authors > 0:
            logger.info("✅ Hardcover author data is working!")
        else:
            logger.warning("⚠️ No author data found in Hardcover books")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
