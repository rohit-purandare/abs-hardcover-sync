#!/usr/bin/env python3
"""
Focused cleanup script to handle the specific duplicate progress issue we identified
"""


from dotenv import load_dotenv

from src.config import Config
from src.hardcover_client import HardcoverClient


def cleanup_book_progress(
    hardcover: HardcoverClient, user_book_id: int, book_title: str, dry_run: bool = True
) -> bool:
    """Clean up duplicate progress records for a specific book"""

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
        if not result:
            return False

        reads = result.get("user_book_reads", [])

        if len(reads) <= 1:
            print(f"✓ {book_title}: Only {len(reads)} record(s), no cleanup needed")
            return True

        print(f"\n📖 {book_title} (user_book_id: {user_book_id})")
        print(f"   Found {len(reads)} progress records")

        # Find the best record to keep (most recent with highest progress)
        best_record = None
        best_progress = 0

        for read in reads:
            progress = read.get("progress_pages", 0) or 0
            if progress > best_progress or (
                progress == best_progress
                and (best_record is None or read["id"] > best_record["id"])
            ):
                best_progress = progress
                best_record = read

        if not best_record:
            print("   ❌ No valid record found")
            return False

        print(
            f"   ✓ Best record: ID {best_record['id']}, Edition {best_record['edition_id']}, Progress {best_record['progress_pages']} pages"
        )

        # Find records to delete
        records_to_delete = [r for r in reads if r["id"] != best_record["id"]]
        print(f"   🗑️  Will delete {len(records_to_delete)} duplicate records")

        if dry_run:
            print("   [DRY RUN] Would delete:")
            for record in records_to_delete[:5]:  # Show first 5
                print(
                    f"     - Record ID {record['id']}: Edition {record['edition_id']}, Progress {record['progress_pages']}"
                )
            if len(records_to_delete) > 5:
                print(f"     ... and {len(records_to_delete) - 5} more")
            return True

        # Delete duplicate records
        deleted_count = 0
        for record in records_to_delete:
            mutation = """
            mutation DeleteProgressRecord($id: Int!) {
                delete_user_book_read(id: $id) {
                    id
                }
            }
            """

            try:
                delete_result = hardcover._execute_query(mutation, {"id": record["id"]})
                if delete_result and "delete_user_book_read" in delete_result:
                    deleted_count += 1
                else:
                    print(f"     ❌ Failed to delete record ID {record['id']}")
            except Exception as e:
                print(f"     ❌ Error deleting record {record['id']}: {str(e)}")

        print(
            f"   ✅ Deleted {deleted_count}/{len(records_to_delete)} duplicate records"
        )
        return True

    except Exception as e:
        print(f"❌ Error processing {book_title}: {str(e)}")
        return False


def main() -> None:
    """Main cleanup function"""
    load_dotenv("secrets.env")

    config = Config()
    hardcover_config = config.get_hardcover_config()
    hardcover = HardcoverClient(hardcover_config["token"])

    print("=== FOCUSED DUPLICATE PROGRESS CLEANUP ===")
    print("Cleaning up known problematic books")
    print()

    # Books we know have issues from our debug
    problematic_books = [
        (4784449, "Project Hail Mary"),  # Had 28 records
        (8052173, "Yellowface"),  # Check if it has duplicates
        (8052156, "Circe"),  # Check if it has duplicates
        (8052157, "The Martian"),  # Check if it has duplicates
    ]

    response = input("Run cleanup? (y/n/dry): ").lower().strip()

    if response == "n":
        print("Cleanup cancelled")
        return

    dry_run = response != "y"
    if dry_run:
        print("Running in DRY RUN mode - no changes will be made")

    print("\nStarting cleanup...")

    success_count = 0
    for user_book_id, book_title in problematic_books:
        if cleanup_book_progress(hardcover, user_book_id, book_title, dry_run):
            success_count += 1

    print("\n=== CLEANUP SUMMARY ===")
    print(f"Books processed: {success_count}/{len(problematic_books)}")

    if dry_run:
        print(
            "\nThis was a dry run. Run with 'y' to actually delete duplicate records."
        )
    else:
        print(
            "\nCleanup completed! Run a test sync to verify progress updates work correctly."
        )


if __name__ == "__main__":
    main()
