#!/usr/bin/env python3
"""
Debug script to examine Hardcover library data and ISBN extraction
"""

import json
import logging

from src.config import Config
from src.hardcover_client import HardcoverClient


def main() -> None:
    """Debug Hardcover library data"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config()

        # Initialize Hardcover client
        hc_client = HardcoverClient(config.HARDCOVER_TOKEN)

        # Get user's books
        books = hc_client.get_user_books()
        logger.info(f"Found {len(books)} books in Hardcover library")

        # Examine each book's structure
        for i, book in enumerate(books):
            logger.info(f"\n=== Book {i+1} ===")
            logger.info(f"Book title: {book.get('title', 'Unknown')}")
            logger.info(f"Book ID: {book.get('id')}")
            logger.info(f"Top-level keys: {list(book.keys())}")

            # Check editions data
            editions = book.get("editions", [])
            logger.info(f"Number of editions: {len(editions)}")

            if editions:
                for j, edition in enumerate(editions):
                    logger.info(f"  Edition {j+1}:")
                    logger.info(f"    ID: {edition.get('id')}")
                    logger.info(f"    ISBN-10: {edition.get('isbn_10')}")
                    logger.info(f"    ISBN-13: {edition.get('isbn_13')}")
                    logger.info(f"    Pages: {edition.get('pages')}")
                    logger.info(f"    All keys: {list(edition.keys())}")
            else:
                logger.info("  No editions data found")

            # Show full book structure for first book
            if i == 0:
                logger.info(f"Full book data: {json.dumps(book, indent=2)}")

    except Exception as e:
        logger.error(f"Debug failed: {str(e)}")


if __name__ == "__main__":
    main()
