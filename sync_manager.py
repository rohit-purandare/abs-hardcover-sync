"""
Sync Manager - Coordinates synchronization between Audiobookshelf and Hardcover
"""

import json
import logging
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

from audiobookshelf_client import AudiobookshelfClient
from hardcover_client import HardcoverClient
from utils import calculate_progress_percentage, normalize_isbn


class EditionMappingCache:
    """Cache for storing edition mappings to improve performance and consistency"""

    def __init__(self, cache_file: str = ".edition_cache.json"):
        self.cache_file = cache_file
        self.logger = logging.getLogger(__name__)
        self.mappings = self._load_cache()
        self.logger.debug(f"Loaded {len(self.mappings)} edition mappings from cache")

    def _load_cache(self) -> Dict[str, int]:
        """Load edition mappings from cache file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    # Validate cache structure
                    if isinstance(data, dict):
                        return data
                    else:
                        self.logger.warning("Invalid cache format, starting fresh")
                        return {}
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to load edition cache: {str(e)}")
            return {}

    def _save_cache(self) -> None:
        """Save edition mappings to cache file"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.mappings, f, indent=2)
            self.logger.debug(f"Saved {len(self.mappings)} edition mappings to cache")
        except Exception as e:
            self.logger.error(f"Failed to save edition cache: {str(e)}")

    def get_edition_for_book(self, isbn: str, title: str) -> Optional[int]:
        """
        Get cached edition ID for a book

        Args:
            isbn: Normalized ISBN
            title: Book title

        Returns:
            Edition ID if found in cache, None otherwise
        """
        key = self._create_cache_key(isbn, title)
        edition_id = self.mappings.get(key)
        if edition_id:
            self.logger.debug(f"Cache hit for {title}: edition {edition_id}")
        return edition_id

    def store_mapping(self, isbn: str, title: str, edition_id: int) -> None:
        """
        Store edition mapping in cache

        Args:
            isbn: Normalized ISBN
            title: Book title
            edition_id: Edition ID to cache
        """
        key = self._create_cache_key(isbn, title)
        self.mappings[key] = edition_id
        self.logger.debug(f"Cached edition mapping for {title}: {isbn} -> {edition_id}")
        self._save_cache()

    def _create_cache_key(self, isbn: str, title: str) -> str:
        """Create a consistent cache key for a book"""
        # Normalize title for consistent key generation
        normalized_title = title.lower().strip()
        return f"{isbn}_{normalized_title}"

    def clear_cache(self) -> None:
        """Clear all cached mappings"""
        self.mappings = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        self.logger.info("Edition cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "total_mappings": len(self.mappings),
            "cache_file_size": (
                os.path.getsize(self.cache_file)
                if os.path.exists(self.cache_file)
                else 0
            ),
        }


class ProgressTrackingCache:
    """Cache for tracking last synced progress to avoid unnecessary syncs"""

    def __init__(self, cache_file: str = ".progress_cache.json"):
        self.cache_file = cache_file
        self.logger = logging.getLogger(__name__)
        self.progress_data = self._load_cache()
        self.logger.debug(
            f"Loaded {len(self.progress_data)} progress records from cache"
        )

    def _load_cache(self) -> Dict[str, Dict]:
        """Load progress tracking data from cache file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    # Validate cache structure
                    if isinstance(data, dict):
                        return data
                    else:
                        self.logger.warning(
                            "Invalid progress cache format, starting fresh"
                        )
                        return {}
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to load progress cache: {str(e)}")
            return {}

    def _save_cache(self) -> None:
        """Save progress tracking data to cache file"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.progress_data, f, indent=2)
            self.logger.debug(
                f"Saved {len(self.progress_data)} progress records to cache"
            )
        except Exception as e:
            self.logger.error(f"Failed to save progress cache: {str(e)}")

    def get_last_progress(self, isbn: str, title: str) -> Optional[float]:
        """
        Get last synced progress for a book

        Args:
            isbn: Normalized ISBN
            title: Book title

        Returns:
            Last synced progress percentage if found, None otherwise
        """
        key = self._create_cache_key(isbn, title)
        progress_record = self.progress_data.get(key)
        if progress_record:
            progress = progress_record.get("progress_percent", 0)
            if isinstance(progress, (int, float)):
                self.logger.debug(f"Found last progress for {title}: {progress:.1f}%")
                return float(progress)
        return None

    def store_progress(self, isbn: str, title: str, progress_percent: float) -> None:
        """
        Store progress for a book

        Args:
            isbn: Normalized ISBN
            title: Book title
            progress_percent: Progress percentage to cache
        """
        key = self._create_cache_key(isbn, title)
        self.progress_data[key] = {
            "progress_percent": progress_percent,
            "last_synced": datetime.now().isoformat(),
            "title": title,
            "isbn": isbn,
        }
        self.logger.debug(f"Cached progress for {title}: {progress_percent:.1f}%")
        self._save_cache()

    def has_progress_changed(
        self, isbn: str, title: str, current_progress: float
    ) -> bool:
        """
        Check if progress has changed since last sync

        Args:
            isbn: Normalized ISBN
            title: Book title
            current_progress: Current progress percentage

        Returns:
            True if progress has changed, False if no change
        """
        last_progress = self.get_last_progress(isbn, title)

        if last_progress is None:
            # First time syncing this book
            self.logger.debug(f"First sync for {title}, will sync")
            return True

        # Check if progress has increased (allowing for small rounding differences)
        progress_changed = current_progress > last_progress + 0.1

        if progress_changed:
            self.logger.debug(
                f"Progress changed for {title}: {last_progress:.1f}% → {current_progress:.1f}%"
            )
        else:
            self.logger.debug(
                f"No progress change for {title}: {current_progress:.1f}% (last: {last_progress:.1f}%)"
            )

        return progress_changed

    def _create_cache_key(self, isbn: str, title: str) -> str:
        """Create a consistent cache key for a book"""
        # Normalize title for consistent key generation
        normalized_title = title.lower().strip()
        return f"{isbn}_{normalized_title}"

    def clear_cache(self) -> None:
        """Clear all cached progress data"""
        self.progress_data = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        self.logger.info("Progress cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "total_records": len(self.progress_data),
            "cache_file_size": (
                os.path.getsize(self.cache_file)
                if os.path.exists(self.cache_file)
                else 0
            ),
        }


class SyncManager:
    """Manages synchronization between Audiobookshelf and Hardcover"""

    def __init__(self, config: Any, dry_run: bool = False) -> None:
        self.config = config
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)

        # Initialize API clients
        self.audiobookshelf = AudiobookshelfClient(
            config.AUDIOBOOKSHELF_URL, config.AUDIOBOOKSHELF_TOKEN
        )

        self.hardcover = HardcoverClient(config.HARDCOVER_TOKEN)

        # Initialize edition mapping cache
        self.edition_cache = EditionMappingCache()

        # Initialize progress tracking cache
        self.progress_cache = ProgressTrackingCache()

        # Get sync configuration
        sync_config = config.get_sync_config()
        self.min_progress_threshold = sync_config.get("min_progress_threshold", 5.0)

        self.logger.info(
            f"SyncManager initialized (dry_run: {dry_run}, min_threshold: {self.min_progress_threshold}%)"
        )

    def sync_progress(self) -> Dict[str, Any]:
        """
        Main synchronization method
        Returns dictionary with sync results
        """
        self.logger.info("Starting progress synchronization...")

        result: Dict[str, Any] = {
            "success": False,
            "books_processed": 0,
            "books_synced": 0,
            "books_completed": 0,
            "books_auto_added": 0,
            "books_skipped": 0,
            "errors": [],
            "details": [],
        }

        try:
            # Get progress from Audiobookshelf
            self.logger.info("Fetching reading progress from Audiobookshelf...")
            abs_progress = self.audiobookshelf.get_reading_progress()
            self.logger.info(
                f"Found {len(abs_progress)} books with progress in Audiobookshelf"
            )

            if not abs_progress:
                self.logger.warning("No reading progress found in Audiobookshelf")
                result["success"] = True
                return result

            # Get user's books from Hardcover
            self.logger.info("Fetching user's library from Hardcover...")
            hardcover_books = self.hardcover.get_user_books()
            self.logger.info(f"Found {len(hardcover_books)} books in Hardcover library")

            # Create ISBN lookup for Hardcover books (using editions data)
            self.logger.info("Creating ISBN lookup table...")
            isbn_to_hardcover = self._create_isbn_lookup(hardcover_books)

            # Pre-filter books with ISBNs to reduce noise
            self.logger.info("Filtering books with ISBNs...")
            syncable_books = []
            books_without_isbn = 0

            with tqdm(
                total=len(abs_progress), desc="Checking ISBNs", unit="book"
            ) as pbar:
                for abs_book in abs_progress:
                    isbn = self._extract_isbn_from_abs_book(abs_book)
                    if isbn:
                        syncable_books.append(abs_book)
                        pbar.set_postfix({"status": "✓ Has ISBN"})
                    else:
                        books_without_isbn += 1
                        pbar.set_postfix({"status": "✗ No ISBN"})
                    pbar.update(1)

            self.logger.info(
                f"Filtered to {len(syncable_books)} books with ISBNs (excluded {books_without_isbn} without ISBN)"
            )

            # Process only books that have ISBNs and can potentially be synced
            with tqdm(
                total=len(syncable_books), desc="Syncing books", unit="book"
            ) as pbar:
                for abs_book in syncable_books:
                    try:
                        result["books_processed"] += 1

                        # Get book title for progress display
                        title = (
                            abs_book.get("media", {})
                            .get("metadata", {})
                            .get("title", "Unknown")
                        )
                        progress_percent = abs_book.get("progress_percentage", 0)

                        # Update progress bar description
                        pbar.set_description(
                            f"Syncing: {title[:30]}{'...' if len(title) > 30 else ''}"
                        )
                        pbar.set_postfix(
                            {
                                "progress": f"{progress_percent:.1f}%",
                                "processed": result["books_processed"],
                            }
                        )

                        sync_result = self._sync_single_book(
                            abs_book, isbn_to_hardcover
                        )

                        if sync_result["status"] == "synced":
                            result["books_synced"] += 1
                            pbar.set_postfix(
                                {
                                    "status": "✓ Synced",
                                    "progress": f"{progress_percent:.1f}%",
                                }
                            )
                            self.logger.info(f"✓ Synced: {sync_result['title']}")
                        elif sync_result["status"] == "completed":
                            result["books_completed"] += 1
                            pbar.set_postfix(
                                {
                                    "status": "✓ Completed",
                                    "progress": f"{progress_percent:.1f}%",
                                }
                            )
                            self.logger.info(f"✓ Completed: {sync_result['title']}")
                        elif sync_result["status"] == "auto_added":
                            result["books_auto_added"] += 1
                            pbar.set_postfix(
                                {
                                    "status": "✓ Added",
                                    "progress": f"{progress_percent:.1f}%",
                                }
                            )
                            self.logger.info(f"✓ Auto-added: {sync_result['title']}")
                        elif (
                            sync_result["status"] == "skipped"
                            and "threshold" in sync_result["reason"]
                        ):
                            result["books_skipped"] += 1
                            pbar.set_postfix(
                                {
                                    "status": "⏭ Skipped",
                                    "reason": sync_result["reason"][:20],
                                }
                            )
                            self.logger.info(
                                f"⏭ Skipped: {sync_result['title']} - {sync_result['reason']}"
                            )
                        elif sync_result["status"] == "failed":
                            pbar.set_postfix(
                                {
                                    "status": "✗ Failed",
                                    "error": sync_result["reason"][:20],
                                }
                            )
                            self.logger.error(
                                f"✗ Failed: {sync_result['title']} - {sync_result['reason']}"
                            )

                        result["details"].append(sync_result)

                    except Exception as e:
                        error_msg = f"Error syncing {abs_book.get('title', 'Unknown')}: {str(e)}"
                        pbar.set_postfix({"status": "✗ Error", "error": str(e)[:20]})
                        self.logger.error(error_msg)
                        result["errors"].append(error_msg)

                    # Update progress bar
                    pbar.update(1)

            result["success"] = True
            self.logger.info(
                f"Synchronization completed: {result['books_synced']} synced, {result['books_completed']} completed, {result['books_auto_added']} auto-added, {result['books_skipped']} skipped"
            )

        except Exception as e:
            error_msg = f"Synchronization failed: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)

        return result

    def _create_isbn_lookup(self, hardcover_books: List[Dict]) -> Dict[str, Dict]:
        """Create a lookup dictionary mapping normalized ISBNs to Hardcover books"""
        isbn_lookup = {}

        for user_book in hardcover_books:
            # Extract ISBNs from editions - note the correct structure: user_book.book.editions
            book_data = user_book.get("book", {})
            editions = book_data.get("editions", [])
            if not editions:
                continue

            for edition in editions:
                isbn_10 = edition.get("isbn_10")
                isbn_13 = edition.get("isbn_13")

                # Add both ISBN-10 and ISBN-13 to lookup
                for isbn_raw in [isbn_10, isbn_13]:
                    if isbn_raw:
                        isbn_normalized = normalize_isbn(isbn_raw)
                        if isbn_normalized:
                            isbn_lookup[isbn_normalized] = {
                                "book": user_book,  # Store the full user_book record
                                "edition": edition,
                                "isbn_raw": isbn_raw,
                            }

        self.logger.info(f"Created ISBN lookup with {len(isbn_lookup)} entries")
        return isbn_lookup

    def _sync_single_book(
        self, abs_book: Dict, isbn_to_hardcover: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Sync progress for a single book using ISBN matching"""

        # Extract book information
        title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
        progress_percent = abs_book.get("progress_percentage", 0)

        # Extract ISBN
        isbn = self._extract_isbn_from_abs_book(abs_book)
        if not isbn:
            return {"status": "skipped", "title": title, "reason": "No ISBN found"}

        # For books below threshold, we'll still add them but with "Want to Read" status
        # This ensures all started books are tracked, even if progress is minimal

        # For books above threshold, check if progress has changed since last sync
        if progress_percent >= self.min_progress_threshold:
            if not self.progress_cache.has_progress_changed(
                isbn, title, progress_percent
            ):
                return {
                    "status": "skipped",
                    "title": title,
                    "reason": f"No progress change ({progress_percent:.1f}% same as last sync)",
                }
        # For books below threshold, we'll add them regardless of progress changes
        # This ensures they get tracked even with minimal progress

        # Check if book exists in Hardcover
        hardcover_match = isbn_to_hardcover.get(isbn)
        if not hardcover_match:
            # Try to auto-add the book
            return self._try_auto_add_book(abs_book, isbn)

        # Book exists in Hardcover, sync the progress
        return self._sync_existing_book(abs_book, hardcover_match)

    def _try_auto_add_book(self, abs_book: Dict, isbn: str) -> Dict[str, Any]:
        """Try to automatically add book to Hardcover library"""
        title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")

        try:
            # Search for book in Hardcover database by ISBN
            search_results = self.hardcover.search_books_by_isbn(isbn)

            if not search_results:
                return {
                    "status": "skipped",
                    "title": title,
                    "reason": "Book not found in Hardcover database",
                }

            # Take the first result
            book_data = search_results[0]
            book_id = book_data["id"]

            if not self.dry_run:
                # Check if progress meets threshold before adding to "Currently Reading"
                progress_percent = abs_book.get("progress_percentage", 0)
                edition = book_data.get("primary_edition", {})

                if progress_percent >= self.min_progress_threshold:
                    # Add to library with "Currently Reading" status
                    user_book = self.hardcover.add_book_to_library(book_id, status_id=2)

                    if user_book:
                        self.logger.info(
                            f"Auto-added '{title}' to Hardcover library (Currently Reading)"
                        )

                        if edition:
                            return self._sync_progress_to_hardcover(
                                user_book, edition, progress_percent, title, isbn
                            )

                        return {
                            "status": "auto_added",
                            "title": title,
                            "reason": "Added to library (Currently Reading)",
                        }
                    else:
                        return {
                            "status": "failed",
                            "title": title,
                            "reason": "Failed to add to library",
                        }
                else:
                    # Add to library with "Want to Read" status for books below threshold
                    user_book = self.hardcover.add_book_to_library(book_id, status_id=1)

                    if user_book:
                        self.logger.info(
                            f"Auto-added '{title}' to Hardcover library (Want to Read - below threshold)"
                        )

                        return {
                            "status": "auto_added",
                            "title": title,
                            "reason": f"Added to library (Want to Read - {progress_percent:.1f}% < {self.min_progress_threshold}% threshold)",
                        }
                    else:
                        return {
                            "status": "failed",
                            "title": title,
                            "reason": "Failed to add to library",
                        }
            else:
                # Dry run - show what would happen
                progress_percent = abs_book.get("progress_percentage", 0)
                if progress_percent >= self.min_progress_threshold:
                    return {
                        "status": "would_auto_add",
                        "title": title,
                        "reason": f"Would add to library (Currently Reading - {progress_percent:.1f}% >= {self.min_progress_threshold}% threshold)",
                    }
                else:
                    return {
                        "status": "would_auto_add",
                        "title": title,
                        "reason": f"Would add to library (Want to Read - {progress_percent:.1f}% < {self.min_progress_threshold}% threshold)",
                    }

        except Exception as e:
            return {
                "status": "failed",
                "title": title,
                "reason": f"Auto-add failed: {str(e)}",
            }

    def _sync_existing_book(
        self, abs_book: Dict, hardcover_match: Dict
    ) -> Dict[str, Any]:
        """Sync progress for an existing book"""
        title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
        progress_percent = abs_book.get("progress_percentage", 0)

        user_book = hardcover_match["book"]
        isbn_edition = hardcover_match["edition"]
        user_book_id = user_book["id"]

        # Extract ISBN for cache lookup
        isbn = self._extract_isbn_from_abs_book(abs_book)

        # Check cache first for edition preference
        cached_edition_id = None
        if isbn:
            cached_edition_id = self.edition_cache.get_edition_for_book(isbn, title)

        # Select edition using enhanced logic with cache
        edition = self._select_edition_with_cache(
            abs_book, hardcover_match, cached_edition_id, title
        )

        # Store the selected edition in cache for future use
        if isbn and edition:
            self.edition_cache.store_mapping(isbn, title, edition["id"])

        # Check if book is already completed (95%+ progress)
        if progress_percent >= 95:
            return self._handle_completion_status(
                user_book_id, edition, title, progress_percent, abs_book
            )

        # Check if book was previously completed but now below 95%
        return self._handle_progress_status(
            user_book_id, edition, title, progress_percent, abs_book
        )

    def _sync_progress_to_hardcover(
        self,
        user_book: Dict,
        edition: Dict,
        progress_percent: float,
        title: str,
        isbn: Optional[str],
    ) -> Dict[str, Any]:
        """Sync progress percentage to Hardcover page-based system"""

        try:
            user_book_id = user_book["id"]
            edition_id = edition["id"]
            total_pages = edition.get("pages", 0)

            if not total_pages:
                return {
                    "status": "skipped",
                    "title": title,
                    "reason": "No page count available",
                }

            # Calculate current page from percentage
            current_page = max(1, int((progress_percent / 100) * total_pages))

            if not self.dry_run:
                # Log the sync details before attempting
                self.logger.info(
                    f"Syncing {title}: {progress_percent:.1f}% → page {current_page}/{total_pages} (edition {edition_id})"
                )

                # Update progress in Hardcover
                success = self.hardcover.update_reading_progress(
                    user_book_id, current_page, progress_percent, edition_id
                )

                if success:
                    # Store the synced progress in cache (for both above and below threshold)
                    if isbn:
                        self.progress_cache.store_progress(
                            isbn, title, progress_percent
                        )

                    return {
                        "status": "synced",
                        "title": title,
                        "progress": f"{current_page}/{total_pages} pages ({progress_percent:.1f}%)",
                    }
                else:
                    return {
                        "status": "failed",
                        "title": title,
                        "reason": "Failed to update progress",
                    }
            else:
                # Log dry-run sync details
                self.logger.info(
                    f"Would sync {title}: {progress_percent:.1f}% → page {current_page}/{total_pages} (edition {edition_id})"
                )
                return {
                    "status": "would_sync",
                    "title": title,
                    "progress": f"Would sync to {current_page}/{total_pages} pages ({progress_percent:.1f}%)",
                }

        except Exception as e:
            return {
                "status": "failed",
                "title": title,
                "reason": f"Sync failed: {str(e)}",
            }

    def _mark_book_completed(
        self, user_book_id: int, edition: Dict, title: str
    ) -> Dict[str, Any]:
        """Mark a book as completed in Hardcover"""

        try:
            edition_id = edition["id"]
            total_pages = edition.get("pages", 0)

            if not self.dry_run:
                success = self.hardcover.mark_book_completed(
                    user_book_id, edition_id, total_pages
                )

                if success:
                    return {
                        "status": "completed",
                        "title": title,
                        "reason": "Marked as completed",
                    }
                else:
                    return {
                        "status": "failed",
                        "title": title,
                        "reason": "Failed to mark as completed",
                    }
            else:
                return {
                    "status": "would_complete",
                    "title": title,
                    "reason": "Would mark as completed (dry run)",
                }

        except Exception as e:
            return {
                "status": "failed",
                "title": title,
                "reason": f"Completion failed: {str(e)}",
            }

    def _extract_isbn_from_abs_book(self, abs_book: Dict) -> Optional[str]:
        """Extract ISBN from Audiobookshelf book data"""

        # Try to get ISBN from the correct metadata location: media.metadata
        media_metadata = abs_book.get("media", {}).get("metadata", {})

        # Check common ISBN fields in media metadata
        isbn_fields = ["isbn", "isbn13", "isbn10", "ISBN", "ISBN13", "ISBN10", "asin"]

        for field in isbn_fields:
            isbn = media_metadata.get(field)
            if isbn:
                normalized = normalize_isbn(isbn)
                if normalized:
                    return normalized

        # Fallback: check top-level metadata (legacy support)
        metadata = abs_book.get("metadata", {})
        for field in isbn_fields:
            isbn = metadata.get(field)
            if isbn:
                normalized = normalize_isbn(isbn)
                if normalized:
                    return normalized

        return None

    def _select_edition_with_cache(
        self,
        abs_book: Dict,
        hardcover_match: Dict,
        cached_edition_id: Optional[int],
        title: str,
    ) -> Dict[str, Any]:
        """
        Select the best edition for a book using enhanced logic with cache

        Priority order:
        1. Cached edition (if available and valid)
        2. Existing progress edition
        3. Linked edition (user_book.edition_id)
        4. ISBN-matched edition
        5. Best available edition with page data
        """
        user_book = hardcover_match["book"]
        isbn_edition = hardcover_match["edition"]
        user_book_id = user_book["id"]
        book_data = user_book.get("book", {})
        editions = book_data.get("editions", [])

        # 1. Check cached edition first
        if cached_edition_id:
            for edition in editions:
                if edition.get("id") == cached_edition_id:
                    self.logger.debug(
                        f"Using cached edition {cached_edition_id} for {title}"
                    )
                    return edition
            self.logger.debug(
                f"Cached edition {cached_edition_id} not found in available editions for {title}"
            )

        # 2. Check existing progress edition
        existing_progress = self.hardcover.get_book_current_progress(user_book_id)
        if existing_progress and existing_progress.get("has_progress"):
            latest_read = existing_progress["latest_read"]
            existing_edition_id = latest_read.get("edition_id")

            if existing_edition_id:
                for edition in editions:
                    if edition.get("id") == existing_edition_id:
                        self.logger.debug(
                            f"Using existing progress edition {existing_edition_id} for {title}"
                        )
                        return edition
                self.logger.debug(
                    f"Existing progress edition {existing_edition_id} not found, falling back for {title}"
                )

        # 3. Check linked edition (user_book.edition_id)
        user_book_edition_id = user_book.get("edition_id")
        if user_book_edition_id:
            for edition in editions:
                if edition.get("id") == user_book_edition_id:
                    self.logger.debug(
                        f"Using linked edition {user_book_edition_id} for {title}"
                    )
                    return edition
            self.logger.debug(
                f"Linked edition {user_book_edition_id} not found, falling back for {title}"
            )

        # 4. Use ISBN-matched edition
        self.logger.debug(
            f"Using ISBN-matched edition {isbn_edition.get('id')} for {title}"
        )
        return isbn_edition

    def _handle_completion_status(
        self,
        user_book_id: int,
        edition: Dict,
        title: str,
        progress_percent: float,
        abs_book: Dict,
    ) -> Dict[str, Any]:
        """
        Handle completion status for books with 95%+ progress

        Checks current status in Hardcover and only marks as completed if not already completed.
        If already completed, just updates progress.
        """
        self.logger.info(
            f"📖 Book completion check for {title}: {progress_percent:.1f}%"
        )

        # Check current status in Hardcover
        current_progress = self.hardcover.get_book_current_progress(user_book_id)
        current_status_id = None

        if current_progress and current_progress.get("user_book"):
            current_status_id = current_progress["user_book"].get("status_id")
            self.logger.debug(
                f"Current status for {title}: {current_status_id} (3=Read, 2=Currently Reading)"
            )

        # If already marked as completed (status_id=3), just update progress
        if current_status_id == 3:
            self.logger.info(f"✅ {title} already completed, updating progress only")
            # Extract ISBN for progress tracking
            isbn = self._extract_isbn_from_abs_book(abs_book)
            return self._sync_progress_to_hardcover(
                {"id": user_book_id}, edition, progress_percent, title, isbn
            )

        # If not completed, mark as completed
        self.logger.info(f"🎯 Marking {title} as completed for the first time")
        return self._mark_book_completed(user_book_id, edition, title)

    def _handle_progress_status(
        self,
        user_book_id: int,
        edition: Dict,
        title: str,
        progress_percent: float,
        abs_book: Dict,
    ) -> Dict[str, Any]:
        """
        Handle progress status for books below 95% progress

        Checks if book was previously completed and updates status back to "Currently Reading" if needed.
        """
        self.logger.info(f"📚 Progress check for {title}: {progress_percent:.1f}%")

        # Check current status in Hardcover
        current_progress = self.hardcover.get_book_current_progress(user_book_id)
        current_status_id = None

        if current_progress and current_progress.get("user_book"):
            current_status_id = current_progress["user_book"].get("status_id")
            self.logger.debug(
                f"Current status for {title}: {current_status_id} (3=Read, 2=Currently Reading)"
            )

        # If currently marked as completed (status_id=3) but progress is below 95%, change back to "Currently Reading"
        if current_status_id == 3:
            self.logger.info(
                f"🔄 {title} was completed but progress is now {progress_percent:.1f}%, changing back to 'Currently Reading'"
            )

            if not self.dry_run:
                success = self.hardcover.update_book_status(
                    user_book_id, 2
                )  # 2 = Currently Reading
                if not success:
                    self.logger.warning(f"Failed to update status for {title}")
            else:
                self.logger.info(
                    f"Would change {title} status from 'Read' to 'Currently Reading' (dry run)"
                )

        # Sync regular progress
        # Extract ISBN for progress tracking
        isbn = self._extract_isbn_from_abs_book(abs_book)
        return self._sync_progress_to_hardcover(
            {"id": user_book_id}, edition, progress_percent, title, isbn
        )

    def get_cache_stats(self) -> Dict[str, int]:
        """Get edition cache statistics"""
        return self.edition_cache.get_cache_stats()

    def clear_edition_cache(self) -> None:
        """Clear the edition mapping cache"""
        self.edition_cache.clear_cache()

    def clear_progress_cache(self) -> None:
        """Clear the progress tracking cache"""
        self.progress_cache.clear_cache()

    def clear_all_caches(self) -> None:
        """Clear both edition and progress caches"""
        self.edition_cache.clear_cache()
        self.progress_cache.clear_cache()
