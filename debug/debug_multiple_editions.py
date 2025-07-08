#!/usr/bin/env python3
"""
Debug script to examine if any books have multiple progress records
across different editions
"""


from dotenv import load_dotenv

from src.config import Config
from src.hardcover_client import HardcoverClient


def main() -> None:
    """Debug multiple edition progress records"""
    load_dotenv("secrets.env")

    config = Config()
    hardcover_config = config.get_hardcover_config()
    hardcover = HardcoverClient(hardcover_config["token"])

    print("=== MULTIPLE EDITION PROGRESS DEBUG ===")

    # Get all user books
    hardcover_books = hardcover.get_user_books()

    print(f"Checking {len(hardcover_books)} books for multiple edition progress...")

    books_with_multiple_progress = []

    for user_book in hardcover_books:
        user_book_id = user_book["id"]
        book_title = user_book.get("book", {}).get("title", "Unknown")

        # Get detailed progress info including all progress records
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
                    # Check if they're for different editions
                    edition_ids = set()
                    for read in reads:
                        if read.get("edition_id"):
                            edition_ids.add(read["edition_id"])

                    if len(edition_ids) > 1:
                        books_with_multiple_progress.append(
                            {
                                "user_book_id": user_book_id,
                                "title": book_title,
                                "reads": reads,
                                "edition_ids": list(edition_ids),
                            }
                        )

                        print(f"\n📖 {book_title} (user_book_id: {user_book_id})")
                        print(
                            f"   Has {len(reads)} progress records across {len(edition_ids)} editions"
                        )

                        for i, read in enumerate(reads):
                            print(f"   [{i+1}] Record ID: {read['id']}")
                            print(f"       Edition: {read['edition_id']}")
                            print(f"       Progress: {read['progress_pages']} pages")
                            print(f"       Started: {read['started_at']}")
                            print(f"       Finished: {read['finished_at']}")
                            print()

        except Exception as e:
            print(f"Error checking {book_title}: {str(e)}")
            continue

    print("\n=== SUMMARY ===")
    print(
        f"Found {len(books_with_multiple_progress)} books with multiple edition progress"
    )

    if books_with_multiple_progress:
        print("\nBooks with multiple edition progress:")
        for book in books_with_multiple_progress:
            print(
                f"  - {book['title']}: {len(book['reads'])} records across editions {book['edition_ids']}"
            )
    else:
        print("✅ No books found with multiple edition progress records")


if __name__ == "__main__":
    main()
