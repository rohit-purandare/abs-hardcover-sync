#!/usr/bin/env python3
"""
Debug script to examine edition consistency between existing progress records
and the editions we're choosing during sync
"""

import os

from dotenv import load_dotenv

from src.config import Config
from src.audiobookshelf_client import AudiobookshelfClient
from src.hardcover_client import HardcoverClient
from src.sync_manager import SyncManager


def main() -> None:
    """Debug edition consistency issues"""
    load_dotenv("secrets.env")

    config = Config()
    hardcover_config = config.get_hardcover_config()
    abs_config = config.get_audiobookshelf_config()

    hardcover = HardcoverClient(hardcover_config["token"])
    abs_client = AudiobookshelfClient(abs_config["url"], abs_config["token"])
    sync_manager = SyncManager(config, dry_run=True)

    print("=== EDITION CONSISTENCY DEBUG ===")

    # Get books from both sources
    abs_books = abs_client.get_reading_progress()
    hardcover_books = hardcover.get_user_books()

    # Create ISBN lookup like sync_manager does
    isbn_lookup = sync_manager._create_isbn_lookup(hardcover_books)

    print(f"\nFound {len(abs_books)} books in Audiobookshelf")
    print(f"Found {len(hardcover_books)} books in Hardcover")
    print(f"Created ISBN lookup with {len(isbn_lookup)} entries")

    # Check each book for edition consistency
    for abs_book in abs_books:
        title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
        isbn = sync_manager._extract_isbn_from_abs_book(abs_book)

        if not isbn:
            continue

        hardcover_match = isbn_lookup.get(isbn)
        if not hardcover_match:
            continue

        user_book = hardcover_match["book"]
        isbn_edition = hardcover_match["edition"]
        user_book_id = user_book["id"]

        print(f"\n--- {title} ---")
        print(f"  ISBN: {isbn}")
        print(f"  User Book ID: {user_book_id}")
        print(f"  ISBN-matched Edition ID: {isbn_edition.get('id')}")

        # Check what edition the user_book is linked to
        user_book_edition_id = user_book.get("edition_id")
        print(f"  User Book Linked Edition ID: {user_book_edition_id}")

        # Check existing progress records
        existing_progress = hardcover.get_book_current_progress(user_book_id)
        if existing_progress and existing_progress.get("has_progress"):
            latest_read = existing_progress["latest_read"]
            existing_edition_id = latest_read.get("edition_id")
            existing_pages = latest_read.get("progress_pages", 0)
            print(f"  Existing Progress Edition ID: {existing_edition_id}")
            print(f"  Existing Progress Pages: {existing_pages}")

            # Check for conflicts
            if existing_edition_id and existing_edition_id != isbn_edition.get("id"):
                print(f"  ⚠️ EDITION MISMATCH!")
                print(f"    Existing progress is for edition {existing_edition_id}")
                print(f"    But we would sync to edition {isbn_edition.get('id')}")

                # Find the existing edition in the book's editions
                book_data = user_book.get("book", {})
                editions = book_data.get("editions", [])
                existing_edition = None
                for edition in editions:
                    if edition.get("id") == existing_edition_id:
                        existing_edition = edition
                        break

                if existing_edition:
                    print(
                        f"    Existing edition pages: {existing_edition.get('pages')}"
                    )
                    print(
                        f"    Existing edition ISBN-13: {existing_edition.get('isbn_13')}"
                    )
                    print(
                        f"    Existing edition ISBN-10: {existing_edition.get('isbn_10')}"
                    )
                else:
                    print(
                        f"    ❌ Could not find existing edition {existing_edition_id} in book's editions!"
                    )
            else:
                print(f"  ✅ Edition IDs match")
        else:
            print(f"  No existing progress records")


if __name__ == "__main__":
    main()
