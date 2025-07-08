#!/usr/bin/env python3
"""
Test script for parallel Hardcover updates
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from src.config import Config
from src.hardcover_client import (
    MAX_PARALLEL_WORKERS,
    RATE_LIMIT_PER_MINUTE,
    HardcoverClient,
)


def test_parallel_status_updates() -> None:
    """Test parallel status updates"""
    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)

    # Get user's books
    print("📚 Getting user's books...")
    user_books = client.get_user_books()

    if len(user_books) < 3:
        print("❌ Need at least 3 books to test parallel updates")
        return

    # Use first 3 books for testing
    test_books = user_books[:3]

    print(f"📖 Testing with {len(test_books)} books:")
    for book in test_books:
        print(
            f"   - {book['book']['title']} (ID: {book['id']}, Status: {book.get('status_id', 'unknown')})"
        )

    # Prepare status updates (toggle between status 1 and 2)
    status_updates = []
    for book in test_books:
        current_status = book.get("status_id", 1)
        new_status = 2 if current_status != 2 else 1
        status_updates.append({"user_book_id": book["id"], "status_id": new_status})

    print(f"\n🔄 Testing parallel status updates...")
    print(f"   Updates: {len(status_updates)}")
    print(f"   Parallel workers: {MAX_PARALLEL_WORKERS}")
    print(f"   Rate limit: {RATE_LIMIT_PER_MINUTE} requests/minute")

    start_time = time.time()
    results = client.batch_update_status(status_updates)
    end_time = time.time()

    print(f"\n📊 Results:")
    print(f"   Time: {end_time - start_time:.3f}s")
    print(f"   Success: {results['success']}")
    print(f"   Failed: {results['failed']}")
    print(f"   Errors: {len(results['errors'])}")

    if results["errors"]:
        print(f"   Error details:")
        for error in results["errors"]:
            print(f"     - {error}")

    # Restore original statuses
    print(f"\n🔄 Restoring original statuses...")
    restore_updates = []
    for book in test_books:
        restore_updates.append(
            {"user_book_id": book["id"], "status_id": book.get("status_id", 1)}
        )

    restore_results = client.batch_update_status(restore_updates)
    print(f"   Restore success: {restore_results['success']}/{len(restore_updates)}")


def test_sequential_vs_parallel() -> None:
    """Compare sequential vs parallel performance"""
    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)

    # Get user's books
    user_books = client.get_user_books()
    if len(user_books) < 5:
        print("❌ Need at least 5 books to test performance")
        return

    test_books = user_books[:5]

    # Test sequential updates
    print("🔄 Testing sequential status updates...")
    start_time = time.time()

    sequential_success = 0
    for book in test_books:
        current_status = book.get("status_id", 1)
        new_status = 2 if current_status != 2 else 1
        if client.update_book_status(book["id"], new_status):
            sequential_success += 1

    sequential_time = time.time() - start_time

    # Test parallel updates
    print("⚡ Testing parallel status updates...")
    start_time = time.time()

    status_updates = []
    for book in test_books:
        current_status = book.get("status_id", 1)
        new_status = 2 if current_status != 2 else 1
        status_updates.append({"user_book_id": book["id"], "status_id": new_status})

    parallel_results = client.batch_update_status(status_updates)
    parallel_time = time.time() - start_time

    print(f"\n📊 Performance Comparison:")
    print(
        f"   Sequential: {sequential_time:.3f}s ({sequential_success}/{len(test_books)} success)"
    )
    print(
        f"   Parallel: {parallel_time:.3f}s ({parallel_results['success']}/{len(test_books)} success)"
    )
    print(f"   Speedup: {sequential_time/parallel_time:.1f}x")

    # Restore original statuses
    restore_updates = []
    for book in test_books:
        restore_updates.append(
            {"user_book_id": book["id"], "status_id": book.get("status_id", 1)}
        )
    client.batch_update_status(restore_updates)


if __name__ == "__main__":
    print("🔍 PARALLEL HARDCOVER UPDATES TEST")
    print("=" * 40)

    test_parallel_status_updates()
    print("\n" + "=" * 40)
    test_sequential_vs_parallel()
