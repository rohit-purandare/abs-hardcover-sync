"""
Audiobookshelf API Client - Handles all interactions with Audiobookshelf server
"""

import concurrent.futures
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

MAX_PARALLEL_WORKERS = 8  # Can be made configurable


class AudiobookshelfClient:
    """Client for interacting with Audiobookshelf API"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.logger = logging.getLogger(__name__)

        # Setup session with authentication
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

        self.logger.info(f"AudiobookshelfClient initialized for {self.base_url}")

    def test_connection(self) -> bool:
        """Test connection to Audiobookshelf server"""
        try:
            response = self._make_request("GET", "/ping")
            if response.status_code == 200:
                return True
            else:
                self.logger.error(
                    f"Connection test failed: HTTP {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def get_reading_progress(self) -> List[Dict[str, Any]]:
        """
        Get reading progress for all books (including 0% progress)
        Returns list of books with their progress data to sync with Hardcover
        """
        self.logger.info("Fetching reading progress from Audiobookshelf...")

        try:
            # Get user info first
            user_data = self._get_current_user()
            if not user_data:
                raise Exception("Could not get current user data")

            # Get library items in progress (these have some progress)
            progress_items = self._get_items_in_progress()

            # Also get all library items to catch books with 0% progress or unknown status
            all_libraries = self.get_libraries()
            all_books = []

            # Collect all books from all libraries
            for library in all_libraries:
                library_books = self.get_library_items(library["id"], limit=1000)
                all_books.extend(library_books)

            # Create a set of IDs that are already in progress
            progress_item_ids = {item["id"] for item in progress_items}

            # Combine progress items with other books that might need syncing
            books_to_sync = []

            # --- PARALLEL FETCH START ---
            def safe_get_details(item_id):
                try:
                    return self._get_library_item_details(item_id)
                except Exception as e:
                    self.logger.error(f"Error fetching details for {item_id}: {str(e)}")
                    return None

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=MAX_PARALLEL_WORKERS
            ) as executor:
                # Fetch details for progress items in parallel
                progress_futures = {
                    executor.submit(safe_get_details, item["id"]): item["id"]
                    for item in progress_items
                }
                for future in concurrent.futures.as_completed(progress_futures):
                    detailed_item = future.result()
                    if detailed_item:
                        books_to_sync.append(detailed_item)

                # Fetch details for other books (with 0% or unknown progress) in parallel
                other_books = [
                    book for book in all_books if book["id"] not in progress_item_ids
                ]
                other_futures = {
                    executor.submit(safe_get_details, book["id"]): book["id"]
                    for book in other_books
                }
                for future in concurrent.futures.as_completed(other_futures):
                    detailed_item = future.result()
                    if detailed_item:
                        if "progress_percentage" not in detailed_item:
                            detailed_item["progress_percentage"] = 0.0
                        books_to_sync.append(detailed_item)
            # --- PARALLEL FETCH END ---

            self.logger.info(
                f"Found {len(books_to_sync)} total books to check for sync"
            )
            return books_to_sync

        except Exception as e:
            self.logger.error(f"Error fetching reading progress: {str(e)}")
            raise

    def _get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        try:
            response = self._make_request("GET", "/api/me")
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get user info: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting user info: {str(e)}")
            return None

    def _get_items_in_progress(self) -> List[Dict[str, Any]]:
        """Get library items that are currently in progress"""
        try:
            response = self._make_request("GET", "/api/me/items-in-progress")
            if response.status_code == 200:
                data = response.json()
                return data.get("libraryItems", [])
            else:
                self.logger.error(
                    f"Failed to get items in progress: {response.status_code}"
                )
                return []
        except Exception as e:
            self.logger.error(f"Error getting items in progress: {str(e)}")
            return []

    def _get_library_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific library item"""
        try:
            response = self._make_request("GET", f"/api/items/{item_id}")
            if response.status_code == 200:
                item_data = response.json()

                # Get user's progress for this item
                progress_data = self._get_user_progress(item_id)

                # Combine item data with progress
                if progress_data:
                    item_data["progress_percentage"] = (
                        progress_data.get("progress", 0) * 100
                    )
                    item_data["current_time"] = progress_data.get("currentTime", 0)
                    item_data["is_finished"] = progress_data.get("isFinished", False)

                return item_data
            else:
                self.logger.warning(
                    f"Could not get details for item {item_id}: {response.status_code}"
                )
                return None
        except Exception as e:
            self.logger.error(f"Error getting item details for {item_id}: {str(e)}")
            return None

    def _get_user_progress(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get user's progress for a specific item"""
        try:
            response = self._make_request("GET", f"/api/me/progress/{item_id}")
            if response.status_code == 200:
                return response.json()
            else:
                # No progress data available
                return None
        except Exception as e:
            self.logger.debug(f"No progress data for item {item_id}: {str(e)}")
            return None

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to Audiobookshelf API"""
        url = urljoin(self.base_url, endpoint)

        try:
            response = self.session.request(method, url, **kwargs)

            # Log request details for debugging
            self.logger.debug(f"{method} {url} -> {response.status_code}")

            return response

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {method} {url} - {str(e)}")
            raise

    def get_libraries(self) -> List[Dict[str, Any]]:
        """Get all libraries (useful for debugging)"""
        try:
            response = self._make_request("GET", "/api/libraries")
            if response.status_code == 200:
                return response.json().get("libraries", [])
            return []
        except Exception as e:
            self.logger.error(f"Error getting libraries: {str(e)}")
            return []

    def get_library_items(
        self, library_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get items from a specific library"""
        try:
            params = {"limit": limit}
            response = self._make_request(
                "GET", f"/api/libraries/{library_id}/items", params=params
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            return []
        except Exception as e:
            self.logger.error(f"Error getting library items: {str(e)}")
            return []
