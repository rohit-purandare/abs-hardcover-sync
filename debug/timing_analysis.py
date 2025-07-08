#!/usr/bin/env python3
"""
Timing Analysis Script - Measures where time is spent during sync operations
"""

import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.sync_manager import SyncManager


@contextmanager
def timer(operation_name: str) -> Any:
    """Context manager to time operations"""
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        print(f"⏱️  {operation_name}: {elapsed:.3f}s")


class TimedSyncManager(SyncManager):
    """SyncManager with timing instrumentation"""

    def __init__(self, config: Any, dry_run: bool = False) -> None:
        super().__init__(config, dry_run)
        self.timing_data: Dict[str, float] = {}

    def sync_progress(self) -> Dict[str, Any]:
        """Main synchronization method with timing"""
        print("\n🔍 TIMING ANALYSIS - SYNC OPERATIONS")
        print("=" * 50)

        result = super().sync_progress()

        # Print timing summary
        print("\n📊 TIMING SUMMARY")
        print("=" * 30)
        total_time = sum(self.timing_data.values())
        for operation, elapsed in sorted(
            self.timing_data.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (elapsed / total_time) * 100 if total_time > 0 else 0
            print(f"{operation:30} {elapsed:8.3f}s ({percentage:5.1f}%)")

        print(f"{'TOTAL':30} {total_time:8.3f}s")

        return result

    def _time_operation(self, operation_name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Time a specific operation"""
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            self.timing_data[operation_name] = elapsed
            print(f"⏱️  {operation_name}: {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.timing_data[operation_name] = elapsed
            print(f"⏱️  {operation_name}: {elapsed:.3f}s (FAILED: {str(e)})")
            raise


def analyze_sync_timing() -> None:
    """Run timing analysis on sync operations"""
    print("🔍 SYNC TIMING ANALYSIS")
    print("=" * 40)

    # Load configuration
    with timer("Config Loading"):
        config = Config()

    # Initialize sync manager
    with timer("Sync Manager Initialization"):
        sync_manager = TimedSyncManager(config, dry_run=False)

    # Test API connections
    print("\n🔗 API CONNECTION TESTS")
    print("-" * 25)

    with timer("Audiobookshelf Connection Test"):
        abs_connected = sync_manager.audiobookshelf.test_connection()
        print(f"✅ Audiobookshelf: {'Connected' if abs_connected else 'Failed'}")

    with timer("Hardcover Connection Test"):
        hc_connected = sync_manager.hardcover.test_connection()
        print(f"✅ Hardcover: {'Connected' if hc_connected else 'Failed'}")

    if not (abs_connected and hc_connected):
        print("❌ Cannot proceed with timing analysis - API connections failed")
        return

    # Run sync with timing
    print("\n🔄 SYNC OPERATION TIMING")
    print("-" * 25)

    # Override methods to add timing
    original_get_reading_progress = sync_manager.audiobookshelf.get_reading_progress
    original_get_user_books = sync_manager.hardcover.get_user_books

    def timed_get_reading_progress() -> List[Dict[str, Any]]:
        return sync_manager._time_operation(
            "Audiobookshelf Progress Fetch", original_get_reading_progress
        )

    def timed_get_user_books() -> List[Dict[str, Any]]:
        return sync_manager._time_operation(
            "Hardcover Library Fetch", original_get_user_books
        )

    # Use monkey patching to replace methods
    sync_manager.audiobookshelf.get_reading_progress = timed_get_reading_progress  # type: ignore[method-assign]
    sync_manager.hardcover.get_user_books = timed_get_user_books  # type: ignore[method-assign]

    # Run the sync
    result = sync_manager.sync_progress()

    print(f"\n✅ Timing analysis completed!")
    print(f"📊 Books processed: {result['books_processed']}")
    print(f"📊 Books synced: {result['books_synced']}")
    print(f"📊 Books completed: {result['books_completed']}")
    print(f"📊 Books auto-added: {result['books_auto_added']}")
    print(f"📊 Books skipped: {result['books_skipped']}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    analyze_sync_timing()
