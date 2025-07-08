#!/usr/bin/env python3
"""
Script to clear all books with "Currently Reading" status from Hardcover
This prevents duplicate entries when the new ASIN-first sync system runs
"""

import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from src.config import Config
from src.hardcover_client import HardcoverClient


def get_currently_reading_books(hardcover: HardcoverClient) -> List[Dict[str, Any]]:
    """Get all books with 'Currently Reading' status (status_id=2)"""
    
    query = """
    query getCurrentlyReadingBooks($offset: Int = 0, $limit: Int = 100) {
        me {
            user_books(
                where: {status_id: {_eq: 2}},
                offset: $offset,
                limit: $limit
            ) {
                id
                status_id
                book {
                    id
                    title
                    contributions(where: {contributable_type: {_eq: "Book"}}) {
                        author {
                            id
                            name
                        }
                    }
                }
            }
        }
    }
    """

    all_books = []
    offset = 0
    limit = 100

    try:
        while True:
            variables = {"offset": offset, "limit": limit}
            result = hardcover._execute_query(query, variables)

            if not result:
                print("❌ No result from GraphQL query")
                break

            if "me" not in result:
                print(f"❌ 'me' key not found in result. Available keys: {list(result.keys())}")
                break

            me_data = result["me"]
            
            # Handle both possible response formats
            if isinstance(me_data, list):
                if me_data and "user_books" in me_data[0]:
                    books = me_data[0]["user_books"]
                else:
                    books = []
            elif isinstance(me_data, dict) and "user_books" in me_data:
                books = me_data["user_books"]
            else:
                print(f"❌ Unexpected me data structure. Type: {type(me_data)}")
                break

            if not books:
                break

            all_books.extend(books)

            # If we got fewer books than the limit, we've reached the end
            if len(books) < limit:
                break

            offset += limit
            print(f"📚 Fetched {len(all_books)} currently reading books so far...")

        print(f"✅ Retrieved {len(all_books)} currently reading books from Hardcover")
        return all_books

    except Exception as e:
        print(f"❌ Error fetching currently reading books: {str(e)}")
        return []


def clear_currently_reading_books(hardcover: HardcoverClient, dry_run: bool = True) -> None:
    """Clear all books with 'Currently Reading' status"""
    
    print("🔍 Fetching currently reading books from Hardcover...")
    currently_reading = get_currently_reading_books(hardcover)
    
    if not currently_reading:
        print("✅ No currently reading books found - nothing to clear!")
        return
    
    print(f"\n📚 Found {len(currently_reading)} books with 'Currently Reading' status:")
    
    for i, user_book in enumerate(currently_reading, 1):
        book_data = user_book.get("book", {})
        title = book_data.get("title", "Unknown")
        
        # Get author name
        contributions = book_data.get("contributions", [])
        author_name = "Unknown"
        if contributions:
            author = contributions[0].get("author", {})
            author_name = author.get("name", "Unknown")
        
        print(f"  {i}. {title} by {author_name} (ID: {user_book['id']})")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Would clear {len(currently_reading)} books from 'Currently Reading' status")
        print("   Run with --execute to actually perform the operation")
        return
    
    print(f"\n🗑️  Clearing {len(currently_reading)} books from 'Currently Reading' status...")
    
    success_count = 0
    failed_count = 0
    
    for user_book in currently_reading:
        user_book_id = user_book["id"]
        book_data = user_book.get("book", {})
        title = book_data.get("title", "Unknown")
        
        # Change status to "Want to Read" (status_id=1) instead of deleting
        success = hardcover.update_book_status(user_book_id, 1)
        
        if success:
            print(f"  ✅ {title}: Changed to 'Want to Read'")
            success_count += 1
        else:
            print(f"  ❌ {title}: Failed to change status")
            failed_count += 1
    
    print(f"\n📊 Summary:")
    print(f"  ✅ Successfully changed: {success_count} books")
    print(f"  ❌ Failed to change: {failed_count} books")
    
    if failed_count == 0:
        print("🎉 All currently reading books have been cleared!")
    else:
        print(f"⚠️  {failed_count} books could not be cleared. You may need to handle them manually.")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clear currently reading books from Hardcover")
    parser.add_argument("--execute", action="store_true", 
                       help="Actually perform the operation (default is dry run)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Load configuration
    load_dotenv()
    config = Config()
    
    # Initialize Hardcover client
    hardcover = HardcoverClient(config.HARDCOVER_TOKEN)
    
    # Test connection
    user = hardcover.get_current_user()
    if not user:
        print("❌ Failed to connect to Hardcover API. Check your token.")
        return
    
    # Handle both list and dict formats
    if isinstance(user, list) and user:
        username = user[0].get('username', 'Unknown')  # type: ignore
    elif isinstance(user, dict):
        username = user.get('username', 'Unknown')
    else:
        username = 'Unknown'
    
    print(f"✅ Connected to Hardcover as: {username}")
    
    # Clear currently reading books
    clear_currently_reading_books(hardcover, dry_run=not args.execute)


if __name__ == "__main__":
    main() 