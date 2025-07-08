#!/usr/bin/env python3
"""
Check what authors are stored in the cache
"""

import logging
import os
import sqlite3
import sys
from typing import Any, Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sync_manager import BookCache


def main() -> None:
    """Check cache for author data"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Initialize cache
        cache = BookCache()
        logger.info("Cache initialized")

        # Get all books with authors
        with cache._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT isbn, title, author, edition_id, progress_percent
                FROM books 
                WHERE author IS NOT NULL
                ORDER BY author, title
                """
            )
            results = cursor.fetchall()

            if results:
                logger.info(f"Found {len(results)} books with author data:")

                # Group by author
                authors: Dict[str, List[Dict[str, Any]]] = {}
                for row in results:
                    author = row["author"]
                    if author not in authors:
                        authors[author] = []
                    authors[author].append(
                        {
                            "title": row["title"],
                            "isbn": row["isbn"],
                            "edition_id": row["edition_id"],
                            "progress_percent": row["progress_percent"],
                        }
                    )

                for author, books in authors.items():
                    logger.info(f"\n{author} ({len(books)} books):")
                    for book in books:
                        progress = (
                            f"{book['progress_percent']}%"
                            if book["progress_percent"] is not None
                            else "No progress"
                        )
                        logger.info(
                            f"  - {book['title']} (ISBN: {book['isbn']}, Progress: {progress})"
                        )
            else:
                logger.warning("No books with author data found in cache")

        # Also check total books vs books with authors
        stats = cache.get_cache_stats()
        logger.info(f"\nCache stats: {stats}")

    except Exception as e:
        logger.error(f"Check failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
