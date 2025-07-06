#!/usr/bin/env python3
"""
Parallel API Optimization Proof-of-Concept
Demonstrates how parallel requests could speed up Audiobookshelf API calls
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

# Mock data for demonstration
MOCK_ITEM_IDS = [f"item_{i}" for i in range(1, 12)]  # 11 books like in your case


def fetch_item_details_parallel(item_id: str) -> Dict[str, Any]:
    """Fetch details for a single item (simulated)"""
    # Simulate network delay
    time.sleep(0.1)  # 100ms per request
    return {"id": item_id, "title": f"Book {item_id}", "progress": 0.5}


def fetch_progress_parallel(item_id: str) -> Dict[str, Any]:
    """Fetch progress for a single item (simulated)"""
    # Simulate network delay
    time.sleep(0.1)  # 100ms per request
    return {"id": item_id, "progress": 0.5, "currentTime": 3600}


def optimized_fetch_all():
    """Fetch all items and progress in parallel using ThreadPoolExecutor"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Fetch item details in parallel
        item_futures = [
            executor.submit(fetch_item_details_parallel, item_id)
            for item_id in MOCK_ITEM_IDS
        ]
        items = [future.result() for future in as_completed(item_futures)]

        # Fetch progress in parallel
        progress_futures = [
            executor.submit(fetch_progress_parallel, item_id)
            for item_id in MOCK_ITEM_IDS
        ]
        progress_data = [future.result() for future in as_completed(progress_futures)]

        # Combine results
        combined = []
        for item, progress in zip(items, progress_data):
            item["progress_percentage"] = progress["progress"] * 100
            combined.append(item)

        return combined


def sequential_fetch_all():
    """Fetch all items and progress sequentially (current approach)"""
    results = []
    for item_id in MOCK_ITEM_IDS:
        # Simulate sequential API calls
        time.sleep(0.1)  # 100ms per request
        item = {"id": item_id, "title": f"Book {item_id}", "progress": 0.5}
        time.sleep(0.1)  # 100ms per request
        progress = {"id": item_id, "progress": 0.5, "currentTime": 3600}

        item["progress_percentage"] = progress["progress"] * 100
        results.append(item)

    return results


def compare_approaches():
    """Compare sequential vs parallel approaches"""
    print("🔍 PARALLEL vs SEQUENTIAL API OPTIMIZATION")
    print("=" * 50)

    # Test sequential approach
    print("\n🔄 Sequential Approach (Current)")
    start_time = time.time()
    sequential_results = sequential_fetch_all()
    sequential_time = time.time() - start_time
    print(f"⏱️  Time: {sequential_time:.3f}s")
    print(f"📊 Items fetched: {len(sequential_results)}")

    # Test parallel approach
    print("\n⚡ Parallel Approach (Optimized)")
    start_time = time.time()
    parallel_results = optimized_fetch_all()
    parallel_time = time.time() - start_time
    print(f"⏱️  Time: {parallel_time:.3f}s")
    print(f"📊 Items fetched: {len(parallel_results)}")

    # Calculate improvement
    improvement = ((sequential_time - parallel_time) / sequential_time) * 100
    print(f"\n📈 Performance Improvement: {improvement:.1f}%")
    print(f"⏱️  Time saved: {sequential_time - parallel_time:.3f}s")

    # Real-world estimate
    print(f"\n🌍 Real-world estimate for your 11 books:")
    print(f"   Current time: ~2.2s")
    print(f"   Optimized time: ~{2.2 * (parallel_time/sequential_time):.1f}s")
    print(f"   Time saved: ~{2.2 - (2.2 * (parallel_time/sequential_time)):.1f}s")


if __name__ == "__main__":
    compare_approaches()
