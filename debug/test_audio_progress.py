#!/usr/bin/env python3
"""
Test script to check if Hardcover API supports audio_seconds in progress tracking
"""

import os
import sys
import json
from datetime import datetime

# Ensure src is importable regardless of working directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from hardcover_client import HardcoverClient
from config import Config

def test_audio_progress_mutation():
    """Test if Hardcover API supports audio_seconds in progress mutations"""
    
    # Load config
    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)
    
    # Test connection
    if not client.test_connection():
        print("❌ Failed to connect to Hardcover API")
        return
    
    print("✅ Connected to Hardcover API")
    
    # Get user books to find an audiobook
    print("\n📚 Fetching user books...")
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
    print(f"   Audio seconds: {edition.get('audio_seconds', 'N/A')}")
    print(f"   Pages: {edition.get('pages', 'N/A')}")
    print(f"   Physical format: {edition.get('physical_format', 'N/A')}")
    print(f"   Reading format: {edition.get('reading_format', {}).get('format', 'N/A')}")
    
    # Test 1: Try to update with audio_seconds in the mutation
    print("\n🧪 Test 1: Trying to update progress with audio_seconds field...")
    
    test_mutation = """
    mutation TestAudioProgress($id: Int!, $audioSeconds: Int, $editionId: Int, $startedAt: date) {
        update_user_book_read(id: $id, object: {
            progress_audio_seconds: $audioSeconds,
            edition_id: $editionId,
            started_at: $startedAt
        }) {
            error
            user_book_read {
                id
                progress_audio_seconds
                edition_id
            }
        }
    }
    """
    
    # Get existing progress to update
    existing_progress = client.get_book_current_progress(user_book["id"])
    
    if existing_progress and existing_progress.get("has_progress"):
        read_id = existing_progress["latest_read"]["id"]
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        variables = {
            "id": read_id,
            "audioSeconds": 1800,  # 30 minutes
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
                    print("✅ Audio seconds mutation succeeded!")
                    return True
            else:
                print("❌ Unexpected response format")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
    else:
        print("❌ No existing progress found to update")
    
    # Test 2: Try to insert with audio_seconds
    print("\n🧪 Test 2: Trying to insert progress with audio_seconds field...")
    
    insert_mutation = """
    mutation TestAudioProgressInsert($id: Int!, $audioSeconds: Int, $editionId: Int, $startedAt: date) {
        insert_user_book_read(user_book_id: $id, user_book_read: {
            progress_audio_seconds: $audioSeconds,
            edition_id: $editionId,
            started_at: $startedAt
        }) {
            error
            user_book_read {
                id
                progress_audio_seconds
                edition_id
            }
        }
    }
    """
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    variables = {
        "id": user_book["id"],
        "audioSeconds": 1800,  # 30 minutes
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
                print("✅ Audio seconds insert succeeded!")
                return True
        else:
            print("❌ Unexpected response format")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    print("\n❌ Audio seconds progress tracking is not supported by Hardcover API")
    return False

def test_audio_seconds_in_schema():
    """Test if audio_seconds field exists in the schema"""
    print("\n🔍 Testing if audio_seconds field exists in user_book_read schema...")
    
    config = Config()
    client = HardcoverClient(config.HARDCOVER_TOKEN)
    
    # Introspection query to check schema
    introspection_query = """
    query IntrospectUserBookRead {
        __type(name: "user_book_read") {
            name
            fields {
                name
                type {
                    name
                    kind
                }
            }
        }
    }
    """
    
    try:
        result = client._execute_query(introspection_query)
        if result and "__type" in result:
            fields = result["__type"]["fields"]
            audio_fields = [f for f in fields if "audio" in f["name"].lower()]
            
            print("📋 Audio-related fields in user_book_read:")
            for field in audio_fields:
                print(f"   - {field['name']}: {field['type']['name']}")
            
            if not audio_fields:
                print("   No audio-related fields found")
                
        else:
            print("❌ Could not introspect schema")
            
    except Exception as e:
        print(f"❌ Schema introspection failed: {str(e)}")

if __name__ == "__main__":
    print("🧪 Testing Hardcover Audio Progress Support")
    print("=" * 50)
    
    # Test schema first
    test_audio_seconds_in_schema()
    
    # Test mutations
    test_audio_progress_mutation()
    
    print("\n" + "=" * 50)
    print("�� Testing complete") 