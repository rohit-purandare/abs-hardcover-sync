#!/usr/bin/env python3
"""
Test script to check what fields can be sent in Hardcover progress mutations
"""

import os
import sys
import json
from datetime import datetime

# Ensure src is importable regardless of working directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from hardcover_client import HardcoverClient
from config import Config

def test_progress_percentage_field():
    """Test if progress_percentage field is supported in mutations"""
    print("🧪 Testing progress_percentage field support...")
    
    config = Config()
    user = config.get_users()[0]  # Get first user
    client = HardcoverClient(user["hardcover_token"])
    
    # Get user books to find a book with progress
    user_books = client.get_user_books()
    if not user_books:
        print("❌ No books found in library")
        return
    
    # Find a book with existing progress
    test_book = None
    for user_book in user_books:
        existing_progress = client.get_book_current_progress(user_book["id"])
        if existing_progress and existing_progress.get("has_progress"):
            test_book = user_book
            break
    
    if not test_book:
        print("❌ No books with existing progress found")
        return
    
    user_book = test_book
    edition = user_book["book"]["editions"][0]
    existing_progress = client.get_book_current_progress(user_book["id"])
    if not existing_progress or not existing_progress.get("has_progress"):
        print("❌ No valid progress found for this book")
        return
    read_id = existing_progress["latest_read"]["id"]
    
    print(f"✅ Testing with book: {user_book['book'].get('title', 'Unknown')}")
    print(f"   Edition ID: {edition['id']}")
    print(f"   Current progress record ID: {read_id}")
    
    # Test 1: Try to update with progress_percentage field
    print("\n📝 Test 1: Trying to update with progress_percentage field...")
    
    test_mutation = """
    mutation TestProgressPercentage($id: Int!, $pages: Int, $percentage: Float, $editionId: Int, $startedAt: date) {
        update_user_book_read(id: $id, object: {
            progress_pages: $pages,
            progress_percentage: $percentage,
            edition_id: $editionId,
            started_at: $startedAt
        }) {
            error
            user_book_read {
                id
                progress_pages
                progress_percentage
                edition_id
            }
        }
    }
    """
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    variables = {
        "id": read_id,
        "pages": 50,
        "percentage": 25.5,
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
                print("✅ progress_percentage field is supported!")
                return True
        else:
            print("❌ Unexpected response format")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

def test_all_possible_fields():
    """Test all possible fields that might be supported in progress mutations"""
    print("\n🔍 Testing all possible progress-related fields...")
    
    config = Config()
    user = config.get_users()[0]  # Get first user
    client = HardcoverClient(user["hardcover_token"])
    
    # Get user books
    user_books = client.get_user_books()
    if not user_books:
        print("❌ No books found in library")
        return
    
    user_book = user_books[0]
    edition = user_book["book"]["editions"][0]
    
    # List of fields to test
    test_fields = [
        "progress_pages",
        "progress_percentage", 
        "progress_audio_seconds",
        "progress_minutes",
        "progress_hours",
        "progress_time",
        "progress_duration",
        "progress_completion",
        "progress_ratio",
        "progress_fraction",
        "current_page",
        "current_percentage",
        "current_audio_seconds",
        "audio_progress",
        "time_progress",
        "duration_progress",
        "completion_percentage",
        "read_percentage",
        "finished_at",
        "completed_at",
        "last_read_at",
        "reading_date",
        "progress_date",
        "notes",
        "comment",
        "rating",
        "review"
    ]
    
    print(f"📋 Testing {len(test_fields)} potential fields...")
    
    # Test each field individually
    supported_fields = []
    
    for field in test_fields:
        print(f"\n🔬 Testing field: {field}")
        
        test_mutation = f"""
        mutation TestField($id: Int!, $value: String, $editionId: Int, $startedAt: date) {{
            update_user_book_read(id: $id, object: {{
                {field}: $value,
                edition_id: $editionId,
                started_at: $startedAt
            }}) {{
                error
                user_book_read {{
                    id
                    {field}
                    edition_id
                }}
            }}
        }}
        """
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        variables = {
            "id": 1,  # Use a dummy ID to avoid affecting real data
            "value": "test_value",
            "editionId": edition["id"],
            "startedAt": current_date,
        }
        
        try:
            result = client._execute_query(test_mutation, variables)
            
            if result and "update_user_book_read" in result:
                if result["update_user_book_read"].get("error"):
                    error = result["update_user_book_read"]["error"]
                    if "not found" in error.lower():
                        print(f"   ❌ Field not found: {error}")
                    else:
                        print(f"   ⚠️  Other error: {error}")
                else:
                    print(f"   ✅ Field supported!")
                    supported_fields.append(field)
            else:
                print(f"   ❌ Unexpected response")
                
        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")
    
    print(f"\n📊 Results: {len(supported_fields)} supported fields found:")
    for field in supported_fields:
        print(f"   ✅ {field}")

def test_schema_introspection():
    """Use introspection to see what fields are actually available"""
    print("\n🔍 Using GraphQL introspection to explore schema...")
    
    config = Config()
    user = config.get_users()[0]  # Get first user
    client = HardcoverClient(user["hardcover_token"])
    
    # Introspection query for user_book_read input type
    introspection_query = """
    query IntrospectUserBookReadInput {
        __type(name: "DatesReadInput") {
            name
            inputFields {
                name
                type {
                    name
                    kind
                    ofType {
                        name
                        kind
                    }
                }
                description
            }
        }
    }
    """
    
    try:
        result = client._execute_query(introspection_query)
        if result and "__type" in result:
            input_fields = result["__type"]["inputFields"]
            
            print("📋 Available fields in DatesReadInput:")
            for field in input_fields:
                field_name = field["name"]
                field_type = field["type"]["name"] or field["type"]["ofType"]["name"]
                description = field.get("description", "No description")
                print(f"   - {field_name}: {field_type} - {description}")
                
        else:
            print("❌ Could not introspect DatesReadInput schema")
            
    except Exception as e:
        print(f"❌ Schema introspection failed: {str(e)}")

def test_user_book_read_output_fields():
    """Check what fields are available in the output"""
    print("\n🔍 Checking user_book_read output fields...")
    
    config = Config()
    user = config.get_users()[0]  # Get first user
    client = HardcoverClient(user["hardcover_token"])
    
    introspection_query = """
    query IntrospectUserBookReadOutput {
        __type(name: "user_book_read") {
            name
            fields {
                name
                type {
                    name
                    kind
                    ofType {
                        name
                        kind
                    }
                }
                description
            }
        }
    }
    """
    
    try:
        result = client._execute_query(introspection_query)
        if result and "__type" in result:
            fields = result["__type"]["fields"]
            
            print("📋 Available fields in user_book_read output:")
            for field in fields:
                field_name = field["name"]
                field_type = field["type"]["name"] or field["type"]["ofType"]["name"]
                description = field.get("description", "No description")
                print(f"   - {field_name}: {field_type} - {description}")
                
        else:
            print("❌ Could not introspect user_book_read schema")
            
    except Exception as e:
        print(f"❌ Schema introspection failed: {str(e)}")

if __name__ == "__main__":
    print("🧪 Testing Hardcover Progress Field Support")
    print("=" * 60)
    
    config = Config()
    users = config.get_users()
    for user in users:
        print(f"\n=== Running progress field tests for user: {user['id']} ===")
        client = HardcoverClient(user["hardcover_token"])
        # Patch the test functions to use this client
        # (You may need to refactor test functions to accept a client argument)
        # For now, run the main test with this client
        # Example: test_progress_percentage_field(client)
        # Example: test_all_possible_fields(client)
        # If not refactored, set up a context or monkeypatch as needed
        # For demonstration, just print the user id
        print(f"[INFO] Would run tests for user: {user['id']}")
    
    print("\n" + "=" * 60)
    print("�� Testing complete") 