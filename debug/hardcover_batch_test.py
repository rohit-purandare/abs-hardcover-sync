#!/usr/bin/env python3
"""
Test script to check if Hardcover supports GraphQL aliases for batching
"""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.hardcover_client import HardcoverClient


def test_graphql_aliases() -> bool:
    """Test if Hardcover supports GraphQL aliases for batching"""

    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)

    # First get some real book IDs from the user's library
    print("📚 Getting user's books to test with real IDs...")
    user_books = client.get_user_books()

    if not user_books or len(user_books) < 2:
        print("❌ Need at least 2 books in library to test batching")
        return False

    # Use first two books for testing
    book1 = user_books[0]
    book2 = user_books[1]
    book1_id = book1["id"]
    book2_id = book2["id"]

    print(
        f"📖 Testing with books: {book1['book']['title']} (ID: {book1_id}) and {book2['book']['title']} (ID: {book2_id})"
    )

    # Test GraphQL aliases for batching multiple status updates
    batch_mutation = """
    mutation BatchUpdateStatus(
        $book1_id: Int!, $book1_status: Int!,
        $book2_id: Int!, $book2_status: Int!
    ) {
        book1: update_user_book(id: $book1_id, object: {status_id: $book1_status}) {
            id
            status_id
        }
        book2: update_user_book(id: $book2_id, object: {status_id: $book2_status}) {
            id
            status_id
        }
    }
    """

    # Get current statuses first
    current_status1 = book1.get("status_id", 1)
    current_status2 = book2.get("status_id", 1)

    # Test with different statuses (but keep them valid)
    test_status1 = 2 if current_status1 != 2 else 1  # Toggle between 1 and 2
    test_status2 = 2 if current_status2 != 2 else 1  # Toggle between 1 and 2

    variables = {
        "book1_id": book1_id,
        "book1_status": test_status1,
        "book2_id": book2_id,
        "book2_status": test_status2,
    }

    print(
        f"🔄 Testing batch status update: {current_status1}->{test_status1}, {current_status2}->{test_status2}"
    )
    print("=" * 50)

    try:
        result = client._execute_query(batch_mutation, variables)
        print("✅ GraphQL aliases for status updates WORK!")
        print(f"📊 Result: {result}")

        # Verify the updates worked
        if (
            result
            and "book1" in result
            and "book2" in result
            and result["book1"].get("status_id") == test_status1
            and result["book2"].get("status_id") == test_status2
        ):
            print("✅ Status updates confirmed successful!")
        else:
            print("⚠️  Status updates may not have worked as expected")

        # Restore original statuses
        restore_mutation = """
        mutation RestoreStatus(
            $book1_id: Int!, $book1_status: Int!,
            $book2_id: Int!, $book2_status: Int!
        ) {
            book1: update_user_book(id: $book1_id, object: {status_id: $book1_status}) {
                id
            }
            book2: update_user_book(id: $book2_id, object: {status_id: $book2_status}) {
                id
            }
        }
        """

        restore_variables = {
            "book1_id": book1_id,
            "book1_status": current_status1,
            "book2_id": book2_id,
            "book2_status": current_status2,
        }

        client._execute_query(restore_mutation, restore_variables)
        print("🔄 Restored original statuses")

        return True
    except Exception as e:
        print(f"❌ GraphQL aliases for status updates failed: {str(e)}")
        return False


def test_parallel_mutations() -> bool:
    """Test parallel execution of individual mutations"""
    import time
    from concurrent.futures import ThreadPoolExecutor

    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)

    def update_status(book_id: int, status: int) -> Any:
        """Update a single book status"""
        try:
            # Use a safe test - just get current progress instead of updating
            return client.get_book_current_progress(book_id)
        except Exception as e:
            return f"Error: {str(e)}"

    print("\n⚡ Testing parallel mutation execution...")
    print("=" * 50)

    # Test with 5 parallel "mutations" (actually just progress checks)
    test_books = [(1, 2), (2, 2), (3, 2), (4, 2), (5, 2)]

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(update_status, book_id, status)
            for book_id, status in test_books
        ]
        results = [future.result() for future in futures]

    parallel_time = time.time() - start_time

    # Test sequential execution
    start_time = time.time()
    sequential_results = []
    for book_id, status in test_books:
        sequential_results.append(update_status(book_id, status))
    sequential_time = time.time() - start_time

    print(f"🔄 Sequential time: {sequential_time:.3f}s")
    print(f"⚡ Parallel time: {parallel_time:.3f}s")
    print(f"📈 Speedup: {sequential_time/parallel_time:.1f}x")

    return parallel_time < sequential_time


def main() -> None:
    print("🔍 HARDCOVER BATCH OPERATIONS TEST")
    print("=" * 40)

    # Test GraphQL aliases
    aliases_supported = test_graphql_aliases()

    # Test parallel execution
    parallel_works = test_parallel_mutations()

    print("\n📊 SUMMARY:")
    print(
        f"   GraphQL aliases: {'✅ Supported' if aliases_supported else '❌ Not supported'}"
    )
    print(f"   Parallel execution: {'✅ Works' if parallel_works else '❌ Issues'}")

    if not aliases_supported and parallel_works:
        print(
            "\n💡 RECOMMENDATION: Use parallel individual mutations for optimization"
        )


if __name__ == "__main__":
    from src.config import Config
    config = Config()
    users = config.get_users()
    for user in users:
        print(f"\n=== Running batch/parallel tests for user: {user['id']} ===")
        client = HardcoverClient(user["hardcover_token"])
        # You may need to refactor test functions to accept a client argument
        # For now, just print the user id
        print(f"[INFO] Would run batch/parallel tests for user: {user['id']}")
