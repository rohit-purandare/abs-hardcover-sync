#!/usr/bin/env python3
"""
Test script to test the progress_seconds field discovered in Hardcover schema
"""

import os
import sys
import json
from datetime import datetime

# Ensure src is importable regardless of working directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from hardcover_client import HardcoverClient
from config import Config

def test_progress_seconds_field():
    """Test if progress_seconds field works for audiobooks"""
    print("🧪 Testing progress_seconds field for audiobooks...")
    
    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)
    
    # Get user books to find an audiobook
    user_books = client.get_user_books()
    if not user_books:
        print("❌ No books found in library")
        return
    
    # Find an audiobook
    audiobook = None
    for user_book in user_books:
        book = user_book.get("book", {})
        editions = book.get("editions", [])
        
        for edition in editions:
            if edition.get("audio_seconds") and edition["audio_seconds"] > 0:
                audiobook = {
                    "user_book": user_book,
                    "edition": edition,
                    "book": book
                }
                break
        if audiobook:
            break
    
    if not audiobook:
        print("❌ No audiobooks found in library")
        return
    
    user_book = audiobook["user_book"]
    edition = audiobook["edition"]
    book = audiobook["book"]
    
    print(f"✅ Found audiobook: {book.get('title', 'Unknown')}")
    print(f"   Edition ID: {edition['id']}")
    print(f"   Total audio seconds: {edition.get('audio_seconds', 'N/A')}")
    print(f"   Pages: {edition.get('pages', 'N/A')}")
    
    # Check if there's existing progress to update
    existing_progress = client.get_book_current_progress(user_book["id"])
    
    if existing_progress and existing_progress.get("has_progress"):
        read_id = existing_progress["latest_read"]["id"]
        print(f"   Existing progress record ID: {read_id}")
        
        # Test updating with progress_seconds
        print("\n📝 Test: Updating progress with progress_seconds...")
        
        test_mutation = """
        mutation TestProgressSeconds($id: Int!, $seconds: Int, $editionId: Int, $startedAt: date) {
            update_user_book_read(id: $id, object: {
                progress_seconds: $seconds,
                edition_id: $editionId,
                started_at: $startedAt
            }) {
                error
                user_book_read {
                    id
                    progress_seconds
                    edition_id
                }
            }
        }
        """
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        test_seconds = 3600  # 1 hour
        
        variables = {
            "id": read_id,
            "seconds": test_seconds,
            "editionId": edition["id"],
            "startedAt": current_date,
        }
        
        try:
            result = client._execute_query(test_mutation, variables)
            print(f"📡 Response: {json.dumps(result, indent=2)}")
            
            if result and "update_user_book_read" in result:
                if result["update_user_book_read"].get("error"):
                    print(f"❌ Error: {result['update_user_book_read']['error']}")
                else:
                    print("✅ progress_seconds field works!")
                    updated_record = result["update_user_book_read"]["user_book_read"]
                    if updated_record and updated_record.get("progress_seconds"):
                        print(f"   Updated progress_seconds to: {updated_record['progress_seconds']}")
                    return True
            else:
                print("❌ Unexpected response format")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
    else:
        print("❌ No existing progress found to update")
    
    return False

def test_insert_progress_seconds():
    """Test inserting new progress with progress_seconds"""
    print("\n🧪 Testing insert with progress_seconds...")
    
    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)
    
    # Get user books to find an audiobook
    user_books = client.get_user_books()
    if not user_books:
        print("❌ No books found in library")
        return
    
    # Find an audiobook
    audiobook = None
    for user_book in user_books:
        book = user_book.get("book", {})
        editions = book.get("editions", [])
        
        for edition in editions:
            if edition.get("audio_seconds") and edition["audio_seconds"] > 0:
                audiobook = {
                    "user_book": user_book,
                    "edition": edition,
                    "book": book
                }
                break
        if audiobook:
            break
    
    if not audiobook:
        print("❌ No audiobooks found in library")
        return
    
    user_book = audiobook["user_book"]
    edition = audiobook["edition"]
    book = audiobook["book"]
    
    print(f"✅ Testing insert for: {book.get('title', 'Unknown')}")
    
    # Test inserting with progress_seconds
    insert_mutation = """
    mutation TestInsertProgressSeconds($id: Int!, $seconds: Int, $editionId: Int, $startedAt: date) {
        insert_user_book_read(user_book_id: $id, user_book_read: {
            progress_seconds: $seconds,
            edition_id: $editionId,
            started_at: $startedAt
        }) {
            error
            user_book_read {
                id
                progress_seconds
                edition_id
            }
        }
    }
    """
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    test_seconds = 1800  # 30 minutes
    
    variables = {
        "id": user_book["id"],
        "seconds": test_seconds,
        "editionId": edition["id"],
        "startedAt": current_date,
    }
    
    try:
        result = client._execute_query(insert_mutation, variables)
        print(f"📡 Response: {json.dumps(result, indent=2)}")
        
        if result and "insert_user_book_read" in result:
            if result["insert_user_book_read"].get("error"):
                print(f"❌ Error: {result['insert_user_book_read']['error']}")
            else:
                print("✅ progress_seconds insert works!")
                inserted_record = result["insert_user_book_read"]["user_book_read"]
                if inserted_record and inserted_record.get("progress_seconds"):
                    print(f"   Inserted progress_seconds: {inserted_record['progress_seconds']}")
                return True
        else:
            print("❌ Unexpected response format")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

if __name__ == "__main__":
    print("🧪 Testing Hardcover Progress Seconds Support")
    print("=" * 50)
    
    # Test updating existing progress
    test_progress_seconds_field()
    
    # Test inserting new progress
    test_insert_progress_seconds()
    
    print("\n" + "=" * 50)
    print("�� Testing complete") 