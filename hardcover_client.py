"""
Hardcover API Client - Handles all interactions with Hardcover GraphQL API
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

MAX_PARALLEL_WORKERS = 5  # Conservative default for rate limiting
RATE_LIMIT_PER_MINUTE = 50
RATE_LIMIT_DELAY = 60.0 / RATE_LIMIT_PER_MINUTE  # 1.2 seconds between requests


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, max_requests_per_minute: int = RATE_LIMIT_PER_MINUTE):
        self.max_requests = max_requests_per_minute
        self.delay = 60.0 / max_requests_per_minute
        self.last_request_time = 0
        self.logger = logging.getLogger(__name__)

    def wait_if_needed(self):
        """Wait if needed to respect rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay:
            sleep_time = self.delay - time_since_last
            self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.3f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()


class HardcoverClient:
    """Client for interacting with Hardcover GraphQL API"""

    def __init__(self, token: str):
        self.token = token
        self.api_url = "https://api.hardcover.app/v1/graphql"
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = RateLimiter()

        # Setup session with authentication
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

        self.logger.info("HardcoverClient initialized")

    def test_connection(self) -> bool:
        """Test connection to Hardcover API"""
        query = """
        query {
            me {
                id
                username
            }
        }
        """

        try:
            result = self._execute_query(query)
            return result is not None and "me" in result
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def get_user_books(self) -> List[Dict]:
        """
        Get all books in user's library - simplified query to match actual schema
        """
        self.logger.info("Fetching user's book library from Hardcover...")

        query = """
        query getUserBooks($offset: Int = 0, $limit: Int = 100) {
            me {
                user_books(
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
                        editions {
                            id
                            isbn_10
                            isbn_13
                            pages
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
                result = self._execute_query(query, variables)

                if not result:
                    self.logger.error("No result from GraphQL query")
                    break

                self.logger.debug(f"GraphQL result structure: {type(result)}")

                if "me" not in result:
                    self.logger.error(
                        f"'me' key not found in result. Available keys: {list(result.keys())}"
                    )
                    break

                me_data = result["me"]
                self.logger.debug(f"Me data type: {type(me_data)}")

                # Handle both possible response formats
                if isinstance(me_data, list):
                    # If me_data is a list, extract user_books from the first item
                    if me_data and "user_books" in me_data[0]:
                        books = me_data[0]["user_books"]
                        self.logger.debug(
                            f"Found user_books in me list with {len(books)} items"
                        )
                    else:
                        self.logger.error(
                            f"Expected user_books in me list but not found. Structure: {me_data[:1] if me_data else 'Empty list'}"
                        )
                        books = []
                elif isinstance(me_data, dict) and "user_books" in me_data:
                    # Standard format: me.user_books
                    books = me_data["user_books"]
                    self.logger.debug(
                        f"Found user_books in me data with {len(books)} items"
                    )
                else:
                    self.logger.error(
                        f"Unexpected me data structure. Type: {type(me_data)}, Keys: {list(me_data.keys()) if isinstance(me_data, dict) else 'Not a dict'}"
                    )
                    break
                if not books:
                    break

                all_books.extend(books)

                # If we got fewer books than the limit, we've reached the end
                if len(books) < limit:
                    break

                offset += limit
                self.logger.debug(f"Fetched {len(all_books)} books so far...")

            self.logger.info(f"Retrieved {len(all_books)} books from Hardcover library")
            return all_books

        except Exception as e:
            self.logger.error(f"Error fetching user books: {str(e)}")
            raise

    def update_reading_progress(
        self,
        user_book_id: int,
        current_page: int,
        progress_percentage: float,
        edition_id: int,
    ) -> bool:
        """
        Update reading progress for a book using user_book_reads system
        First checks for existing progress and updates if found, otherwise creates new

        Args:
            user_book_id: ID of the user_book record in Hardcover
            current_page: Current page number
            progress_percentage: Progress as percentage (0-100)
            edition_id: ID of the specific edition being read

        Returns:
            True if update was successful, False otherwise
        """
        self.logger.debug(
            f"Updating progress for user_book_id {user_book_id}: "
            f"page {current_page}, {progress_percentage:.1f}%"
        )

        # First, check if there's existing progress
        existing_progress = self.get_book_current_progress(user_book_id)

        from datetime import datetime

        current_date = datetime.now().strftime("%Y-%m-%d")

        if existing_progress and existing_progress.get("has_progress"):
            # Update existing progress record using KOReader's approach
            latest_read = existing_progress["latest_read"]
            read_id = latest_read["id"]

            self.logger.debug(f"Found existing progress record {read_id}, updating...")

            update_mutation = """
            mutation UpdateBookProgress($id: Int!, $pages: Int, $editionId: Int, $startedAt: date) {
                update_user_book_read(id: $id, object: {
                    progress_pages: $pages,
                    edition_id: $editionId,
                    started_at: $startedAt
                }) {
                    error
                    user_book_read {
                        id
                        progress_pages
                        edition_id
                    }
                }
            }
            """

            variables = {
                "id": read_id,
                "pages": current_page,
                "editionId": edition_id,
                "startedAt": current_date,
            }

            try:
                result = self._execute_query(update_mutation, variables)
                self.logger.debug(f"Progress update response: {result}")

                if (
                    result
                    and "update_user_book_read" in result
                    and result["update_user_book_read"]
                    and result["update_user_book_read"].get("user_book_read")
                ):
                    updated_record = result["update_user_book_read"]["user_book_read"]
                    if updated_record and updated_record.get("id"):
                        self.logger.info(
                            f"Successfully updated reading progress: record {read_id} to page {current_page}"
                        )
                        return True

                # If update failed, check for error
                if (
                    result
                    and "update_user_book_read" in result
                    and result["update_user_book_read"]
                    and result["update_user_book_read"].get("error")
                ):
                    error_msg = result["update_user_book_read"]["error"]
                    self.logger.warning(f"Update failed with error: {error_msg}")
                    return False

                self.logger.warning(
                    f"Update may have failed for record {read_id}. Response: {result}"
                )
                return False

            except Exception as e:
                self.logger.error(
                    f"Error updating existing progress record {read_id}: {str(e)}"
                )
                return False

        # Create new progress record using KOReader's approach
        self.logger.debug(
            f"Creating new progress record for user_book_id {user_book_id}..."
        )

        insert_mutation = """
        mutation InsertUserBookRead($id: Int!, $pages: Int, $editionId: Int, $startedAt: date) {
            insert_user_book_read(user_book_id: $id, user_book_read: {
                progress_pages: $pages,
                edition_id: $editionId,
                started_at: $startedAt
            }) {
                error
                user_book_read {
                    id
                    started_at
                    finished_at
                    edition_id
                    progress_pages
                }
            }
        }
        """

        variables = {
            "id": user_book_id,
            "pages": current_page,
            "editionId": edition_id,
            "startedAt": current_date,
        }

        try:
            result = self._execute_query(insert_mutation, variables)
            self.logger.debug(f"Progress insert response: {result}")

            if (
                result
                and "insert_user_book_read" in result
                and result["insert_user_book_read"]
                and result["insert_user_book_read"].get("user_book_read")
            ):
                inserted_read = result["insert_user_book_read"]["user_book_read"]
                if inserted_read and inserted_read.get("id"):
                    self.logger.info(
                        f"Successfully created reading progress with new record ID: {inserted_read['id']}"
                    )
                    return True

            # Check for error in response
            if (
                result
                and "insert_user_book_read" in result
                and result["insert_user_book_read"]
                and result["insert_user_book_read"].get("error")
            ):
                error_msg = result["insert_user_book_read"]["error"]
                self.logger.warning(f"Insert failed with error: {error_msg}")
                return False

            self.logger.warning(
                f"Insert may have failed for user_book_id {user_book_id}. Response: {result}"
            )
            return False

        except Exception as e:
            self.logger.error(
                f"Error creating progress for user_book_id {user_book_id}: {str(e)}"
            )
            return False

    def mark_book_completed(
        self, user_book_id: int, edition_id: int, total_pages: int
    ) -> bool:
        """
        Mark a book as completed (Read status) in Hardcover

        Args:
            user_book_id: ID of the user_book record in Hardcover
            edition_id: ID of the specific edition being read
            total_pages: Total pages in the book

        Returns:
            True if marked as completed successfully, False otherwise
        """
        self.logger.debug(f"Marking book as completed: user_book_id {user_book_id}")

        # Get current date for completion
        from datetime import datetime

        current_date = datetime.now().strftime("%Y-%m-%d")

        # Update user_book status to "Read" (status_id=3) and add completion reading record
        # Based on the working progress update mutation pattern
        mutation = """
        mutation completeBook($id: Int!, $statusId: Int!) {
            update_user_book(id: $id, object: {status_id: $statusId}) {
                id
            }
        }
        """

        variables = {
            "id": user_book_id,
            "statusId": 3,  # 3 = Read status
        }

        try:
            result = self._execute_query(mutation, variables)
            self.logger.debug(f"Completion response: {result}")

            if (
                result
                and "update_user_book" in result
                and result["update_user_book"]
                and result["update_user_book"].get("id")
            ):
                self.logger.info(
                    f"Successfully marked book as completed: user_book_id {user_book_id}"
                )
                return True

            self.logger.warning(
                f"Failed to mark book as completed: user_book_id {user_book_id}. Response: {result}"
            )
            return False

        except Exception as e:
            self.logger.error(f"Failed to mark book as completed: {str(e)}")
            return False

    def update_book_status(self, user_book_id: int, status_id: int) -> bool:
        """
        Update the status of a book in Hardcover

        Args:
            user_book_id: ID of the user_book record in Hardcover
            status_id: Status (1=Want to Read, 2=Currently Reading, 3=Read, 4=Did Not Finish)

        Returns:
            True if status updated successfully, False otherwise
        """
        self.logger.debug(
            f"Updating book status: user_book_id {user_book_id} to status {status_id}"
        )

        mutation = """
        mutation updateBookStatus($id: Int!, $statusId: Int!) {
            update_user_book(id: $id, object: {status_id: $statusId}) {
                id
            }
        }
        """

        variables = {
            "id": user_book_id,
            "statusId": status_id,
        }

        try:
            result = self._execute_query(mutation, variables)
            self.logger.debug(f"Status update response: {result}")

            if (
                result
                and "update_user_book" in result
                and result["update_user_book"]
                and result["update_user_book"].get("id")
            ):
                self.logger.info(
                    f"Successfully updated book status: user_book_id {user_book_id} to status {status_id}"
                )
                return True

            self.logger.warning(
                f"Failed to update book status: user_book_id {user_book_id}. Response: {result}"
            )
            return False

        except Exception as e:
            self.logger.error(f"Failed to update book status: {str(e)}")
            return False

    def get_book_current_progress(self, user_book_id: int) -> Optional[Dict]:
        """
        Get current reading progress for a specific user_book
        Returns progress info or None if no progress exists
        """
        query = """
        query getBookProgress($user_book_id: Int!) {
            user_book_reads(where: {user_book_id: {_eq: $user_book_id}}, order_by: {id: desc}, limit: 1) {
                id
                progress_pages
                user_book_id
                edition_id
                finished_at
            }
            user_books(where: {id: {_eq: $user_book_id}}) {
                id
                status_id
            }
        }
        """

        try:
            result = self._execute_query(query, {"user_book_id": user_book_id})
            if result:
                reads = result.get("user_book_reads", [])
                user_books = result.get("user_books", [])

                return {
                    "latest_read": reads[0] if reads else None,
                    "user_book": user_books[0] if user_books else None,
                    "has_progress": len(reads) > 0,
                }
            return None

        except Exception as e:
            self.logger.error(
                f"Error getting book progress for user_book_id {user_book_id}: {str(e)}"
            )
            return None

    def search_books_by_isbn(self, isbn: str) -> List[Dict]:
        """
        Search for books in Hardcover database by ISBN using editions
        """
        self.logger.info(f"Searching for books with ISBN: {isbn}")

        # Search for editions with this ISBN, then get the associated books
        query = """
        query searchBooksByISBN($isbn10: String, $isbn13: String) {
            editions(where: {
                _or: [
                    {isbn_10: {_eq: $isbn10}},
                    {isbn_13: {_eq: $isbn13}}
                ]
            }, limit: 10) {
                id
                isbn_10
                isbn_13
                pages
                book_id
                book {
                    id
                    title
                    cached_contributors
                }
            }
        }
        """

        # Try both as ISBN-10 and ISBN-13 since we don't know which format it is
        variables = {"isbn10": isbn, "isbn13": isbn}

        try:
            result = self._execute_query(query, variables)
            if result and "editions" in result:
                books = []
                seen_book_ids = set()

                for edition in result["editions"]:
                    book_data = edition.get("book")
                    if book_data and book_data["id"] not in seen_book_ids:
                        book_data["editions"] = [edition]  # Include edition info
                        books.append(book_data)
                        seen_book_ids.add(book_data["id"])

                self.logger.info(f"Found {len(books)} books for ISBN {isbn}")
                return books

            self.logger.info(f"No books found for ISBN {isbn}")
            return []

        except Exception as e:
            self.logger.error(f"Error searching for ISBN {isbn}: {str(e)}")
            return []

    def add_book_to_library(self, book_id: int, status_id: int = 2) -> Optional[Dict]:
        """
        Add a book to user's library

        Args:
            book_id: ID of the book to add
            status_id: Status (1=Want to Read, 2=Currently Reading, 3=Read, 4=Did Not Finish)

        Returns:
            The created user_book record or None if failed
        """
        self.logger.info(f"Adding book {book_id} to library with status {status_id}")

        mutation = """
        mutation addBookToLibrary($book_id: Int!, $status_id: Int!) {
            insert_user_book(object: {
                book_id: $book_id,
                status_id: $status_id
            }) {
                id
            }
        }
        """

        variables = {"book_id": book_id, "status_id": status_id}

        try:
            result = self._execute_query(mutation, variables)

            if result and "insert_user_book" in result:
                user_book = result["insert_user_book"]
                if user_book:
                    self.logger.info(f"Successfully added book {book_id} to library")
                    return user_book

            self.logger.warning(f"Failed to add book {book_id} to library")
            return None

        except Exception as e:
            self.logger.error(f"Error adding book {book_id} to library: {str(e)}")
            return None

    def _execute_query(
        self, query: str, variables: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Execute GraphQL query with rate limiting"""
        self.rate_limiter.wait_if_needed()

        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = self.session.post(self.api_url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                self.logger.error(f"GraphQL errors: {data['errors']}")
                return None

            return data.get("data")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            return None

    def get_current_user(self) -> Optional[Dict]:
        """Get current user information"""
        query = """
        query {
            me {
                id
                username
                email
                created_at
            }
        }
        """

        try:
            result = self._execute_query(query)
            return result.get("me") if result else None
        except Exception as e:
            self.logger.error(f"Error getting current user: {str(e)}")
            return None

    def batch_update_status(self, updates: List[Dict[str, int]]) -> Dict[str, Any]:
        """
        Update status for multiple books in parallel

        Args:
            updates: List of dicts with 'user_book_id' and 'status_id' keys

        Returns:
            Dict with results: {'success': int, 'failed': int, 'errors': List[str]}
        """
        if not updates:
            return {"success": 0, "failed": 0, "errors": []}

        self.logger.info(f"Batch updating status for {len(updates)} books")

        def update_single_status(update: Dict[str, int]) -> Dict[str, Any]:
            """Update status for a single book"""
            try:
                success = self.update_book_status(
                    update["user_book_id"], update["status_id"]
                )
                return {
                    "user_book_id": update["user_book_id"],
                    "status_id": update["status_id"],
                    "success": success,
                    "error": None,
                }
            except Exception as e:
                return {
                    "user_book_id": update["user_book_id"],
                    "status_id": update["status_id"],
                    "success": False,
                    "error": str(e),
                }

        results = {"success": 0, "failed": 0, "errors": []}

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
            futures = [
                executor.submit(update_single_status, update) for update in updates
            ]

            for future in as_completed(futures):
                result = future.result()
                if result["success"]:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    if result["error"]:
                        results["errors"].append(
                            f"Book {result['user_book_id']}: {result['error']}"
                        )

        self.logger.info(
            f"Batch status update completed: {results['success']} success, {results['failed']} failed"
        )
        return results

    def batch_update_progress(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update progress for multiple books in parallel

        Args:
            updates: List of dicts with 'user_book_id', 'current_page', 'progress_percentage', 'edition_id' keys

        Returns:
            Dict with results: {'success': int, 'failed': int, 'errors': List[str]}
        """
        if not updates:
            return {"success": 0, "failed": 0, "errors": []}

        self.logger.info(f"Batch updating progress for {len(updates)} books")

        def update_single_progress(update: Dict[str, Any]) -> Dict[str, Any]:
            """Update progress for a single book"""
            try:
                success = self.update_reading_progress(
                    update["user_book_id"],
                    update["current_page"],
                    update["progress_percentage"],
                    update["edition_id"],
                )
                return {
                    "user_book_id": update["user_book_id"],
                    "success": success,
                    "error": None,
                }
            except Exception as e:
                return {
                    "user_book_id": update["user_book_id"],
                    "success": False,
                    "error": str(e),
                }

        results = {"success": 0, "failed": 0, "errors": []}

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
            futures = [
                executor.submit(update_single_progress, update) for update in updates
            ]

            for future in as_completed(futures):
                result = future.result()
                if result["success"]:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    if result["error"]:
                        results["errors"].append(
                            f"Book {result['user_book_id']}: {result['error']}"
                        )

        self.logger.info(
            f"Batch progress update completed: {results['success']} success, {results['failed']} failed"
        )
        return results
