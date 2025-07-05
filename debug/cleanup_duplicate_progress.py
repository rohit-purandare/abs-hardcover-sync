#!/usr/bin/env python3
"""
Cleanup script to consolidate duplicate progress records and maintain only one active record per book.
This addresses the issue where multiple progress records were created instead of updating existing ones.
"""

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

from config import Config
from hardcover_client import HardcoverClient


def find_books_with_duplicate_progress(hardcover: HardcoverClient) -> List[Dict]:
    """Find all books that have multiple progress records"""
    print("Scanning for books with duplicate progress records...")

    hardcover_books = hardcover.get_user_books()
    books_with_duplicates = []

    for user_book in hardcover_books:
        user_book_id = user_book["id"]
        book_title = user_book.get("book", {}).get("title", "Unknown")

        # Get all progress records for this book
        query = """
        query getBookProgress($user_book_id: Int!) {
            user_book_reads(where: {user_book_id: {_eq: $user_book_id}}, order_by: {id: desc}) {
                id
                progress_pages
                user_book_id
                edition_id
                finished_at
                started_at
            }
        }
        """

        try:
            result = hardcover._execute_query(query, {"user_book_id": user_book_id})
            if result:
                reads = result.get("user_book_reads", [])

                if len(reads) > 1:
                    books_with_duplicates.append(
                        {
                            "user_book_id": user_book_id,
                            "title": book_title,
                            "reads": reads,
                            "total_records": len(reads),
                        }
                    )

        except Exception as e:
            print(f"Error checking {book_title}: {str(e)}")
            continue

    print(f"Found {len(books_with_duplicates)} books with duplicate progress records")
    return books_with_duplicates


def consolidate_book_progress(
    hardcover: HardcoverClient, book_info: Dict, dry_run: bool = True
) -> Dict:
    """
    Consolidate multiple progress records for a single book into one record.
    Strategy:
    1. Find the most recent/relevant progress record (highest progress or most recent)
    2. Delete all other progress records
    3. Keep only the consolidated record
    """
    user_book_id = book_info["user_book_id"]
    title = book_info["title"]
    reads = book_info["reads"]

    print(f"\n--- Consolidating {title} ---")
    print(f"Current records: {len(reads)}")

    # Find the best record to keep
    best_record = None
    best_progress = 0

    # Priority: Record with highest progress, then most recent ID
    for read in reads:
        progress = read.get("progress_pages", 0) or 0
        if progress > best_progress or (
            progress == best_progress
            and (best_record is None or read["id"] > best_record["id"])
        ):
            best_progress = progress
            best_record = read

    if not best_record:
        return {"status": "error", "message": "No valid record found"}

    print(
        f"Best record: ID {best_record['id']}, Edition {best_record['edition_id']}, Progress {best_record['progress_pages']} pages"
    )

    # Find records to delete (all except the best one)
    records_to_delete = [r for r in reads if r["id"] != best_record["id"]]

    if not records_to_delete:
        return {"status": "no_action", "message": "Only one record exists"}

    print(f"Records to delete: {len(records_to_delete)}")

    if dry_run:
        print("DRY RUN: Would delete the following records:")
        for record in records_to_delete:
            print(
                f"  - Record ID {record['id']}: Edition {record['edition_id']}, Progress {record['progress_pages']}"
            )
        return {
            "status": "dry_run",
            "would_delete": len(records_to_delete),
            "would_keep": best_record["id"],
        }

    # Delete duplicate records
    deleted_count = 0
    for record in records_to_delete:
        if delete_progress_record(hardcover, record["id"]):
            deleted_count += 1
            print(f"✓ Deleted record ID {record['id']}")
        else:
            print(f"✗ Failed to delete record ID {record['id']}")

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "kept_record_id": best_record["id"],
        "kept_edition_id": best_record["edition_id"],
        "kept_progress": best_record["progress_pages"],
    }


def delete_progress_record(hardcover: HardcoverClient, record_id: int) -> bool:
    """Delete a specific progress record"""
    mutation = """
    mutation DeleteProgressRecord($id: Int!) {
        delete_user_book_read(id: $id) {
            id
        }
    }
    """

    try:
        result = hardcover._execute_query(mutation, {"id": record_id})
        return result and "delete_user_book_read" in result
    except Exception as e:
        print(f"Error deleting record {record_id}: {str(e)}")
        return False


def main():
    """Main cleanup function"""
    load_dotenv("secrets.env")

    config = Config()
    hardcover_config = config.get_hardcover_config()
    hardcover = HardcoverClient(hardcover_config["token"])

    print("=== DUPLICATE PROGRESS CLEANUP ===")
    print(
        "This tool will consolidate multiple progress records into single records per book"
    )
    print()

    # Find books with duplicate progress
    books_with_duplicates = find_books_with_duplicate_progress(hardcover)

    if not books_with_duplicates:
        print("✓ No books found with duplicate progress records")
        return

    # Show summary
    total_duplicate_records = sum(
        book["total_records"] - 1 for book in books_with_duplicates
    )
    print(f"\nSummary:")
    print(f"  Books with duplicates: {len(books_with_duplicates)}")
    print(f"  Total duplicate records to clean: {total_duplicate_records}")
    print()

    # Ask for confirmation
    response = input("Run cleanup? (y/n/dry): ").lower().strip()

    if response == "n":
        print("Cleanup cancelled")
        return

    dry_run = response != "y"
    if dry_run:
        print("Running in DRY RUN mode - no changes will be made")

    print("\nStarting cleanup...")

    # Process each book
    summary = {"processed": 0, "total_deleted": 0, "errors": 0}

    for book_info in books_with_duplicates:
        result = consolidate_book_progress(hardcover, book_info, dry_run)
        summary["processed"] += 1

        if result["status"] == "success":
            summary["total_deleted"] += result["deleted_count"]
        elif result["status"] == "error":
            summary["errors"] += 1
        elif result["status"] == "dry_run":
            summary["total_deleted"] += result["would_delete"]

    print(f"\n=== CLEANUP SUMMARY ===")
    print(f"Books processed: {summary['processed']}")
    print(f"Records deleted: {summary['total_deleted']}")
    print(f"Errors: {summary['errors']}")

    if dry_run:
        print(
            "\nThis was a dry run. Run with 'y' to actually delete duplicate records."
        )
    else:
        print("\nCleanup completed! Your progress records should now be consolidated.")


if __name__ == "__main__":
    main()
