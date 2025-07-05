#!/usr/bin/env python3
"""
Debug script to examine Audiobookshelf metadata and ISBN extraction
"""

import json
import logging

from audiobookshelf_client import AudiobookshelfClient
from config import Config


def main():
    """Debug metadata extraction"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config()

        # Initialize Audiobookshelf client
        abs_client = AudiobookshelfClient(
            config.AUDIOBOOKSHELF_URL, config.AUDIOBOOKSHELF_TOKEN
        )

        # Get books with progress
        books = abs_client.get_reading_progress()
        logger.info(f"Found {len(books)} books with progress")

        # Focus on Project Hail Mary
        for book in books:
            title = book.get("media", {}).get("metadata", {}).get("title", "Unknown")
            if "Hail Mary" in title:
                logger.info(f"\n=== {title} ===")
                logger.info(
                    f"Progress percentage: {book.get('progress_percentage', 'Not found')}"
                )
                logger.info(
                    f"ISBN: {book.get('media', {}).get('metadata', {}).get('isbn', 'Not found')}"
                )
                logger.info(
                    f"Duration: {book.get('media', {}).get('duration', 'Not found')}"
                )
                logger.info(f"Current time: {book.get('current_time', 'Not found')}")

                # Show full structure for debugging
                logger.info(
                    f"Full book data: {json.dumps(book, indent=2, default=str)}"
                )
                break

    except Exception as e:
        logger.error(f"Debug failed: {str(e)}")


if __name__ == "__main__":
    main()
