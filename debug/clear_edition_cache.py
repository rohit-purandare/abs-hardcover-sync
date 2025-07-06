#!/usr/bin/env python3
"""
Clear only edition mappings from cache, keeping progress data
"""

import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_manager import BookCache


def main():
    """Clear edition mappings but keep progress data"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Initialize cache
        cache = BookCache()
        logger.info("Cache initialized")

        # Get stats before clearing
        stats_before = cache.get_cache_stats()
        logger.info(f"Cache stats before: {stats_before}")

        # Clear only edition mappings (set edition_id to NULL)
        with cache._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE books SET edition_id = NULL, author = NULL")
            affected_rows = cursor.rowcount
            conn.commit()

        logger.info(f"Cleared edition mappings for {affected_rows} books")

        # Get stats after clearing
        stats_after = cache.get_cache_stats()
        logger.info(f"Cache stats after: {stats_after}")

        logger.info(
            "✅ Edition mappings cleared - next sync will re-fetch editions and authors"
        )

    except Exception as e:
        logger.error(f"Clear failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
