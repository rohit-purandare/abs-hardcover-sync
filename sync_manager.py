"""
Sync Manager - Coordinates synchronization between Audiobookshelf and Hardcover
"""

import concurrent.futures
import json
import logging
import math
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

from audiobookshelf_client import AudiobookshelfClient
from hardcover_client import HardcoverClient
from utils import calculate_progress_percentage, normalize_isbn


class BookCache:
    """SQLite-based cache for storing book edition mappings and progress tracking"""

    def __init__(self, cache_file: str = ".book_cache.db"):
        self.cache_file = cache_file
        self.logger = logging.getLogger(__name__)
        self._init_database()
        self.logger.debug(f"SQLite cache initialized: {cache_file}")

    def _init_database(self) -> None:
        """Initialize SQLite database with schema"""
        try:
            with sqlite3.connect(self.cache_file) as conn:
                cursor = conn.cursor()

                # Create books table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        isbn TEXT NOT NULL,
                        title TEXT NOT NULL,
                        edition_id INTEGER,
                        progress_percent REAL,
                        last_synced TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(isbn, title)
                    )
                """
                )

                # Create indexes for fast lookups
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_isbn_title ON books(isbn, title)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_last_synced ON books(last_synced)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_progress ON books(progress_percent)"
                )

                conn.commit()
                self.logger.debug("Database schema initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(self.cache_file)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn

    def _create_cache_key(self, isbn: str, title: str) -> Tuple[str, str]:
        """Create normalized cache key for a book"""
        normalized_title = title.lower().strip()
        return isbn, normalized_title

    # Edition-related methods
    def get_edition_for_book(self, isbn: str, title: str) -> Optional[int]:
        """
        Get cached edition ID for a book

        Args:
            isbn: Normalized ISBN
            title: Book title

        Returns:
            Edition ID if found in cache, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT edition_id FROM books WHERE isbn = ? AND title = ?",
                    (isbn, title.lower().strip()),
                )
                result = cursor.fetchone()

                if result and result["edition_id"]:
                    self.logger.debug(
                        f"Cache hit for {title}: edition {result['edition_id']}"
                    )
                    return result["edition_id"]
                return None

        except Exception as e:
            self.logger.error(f"Error getting edition for {title}: {str(e)}")
            return None

    def store_edition_mapping(self, isbn: str, title: str, edition_id: int) -> None:
        """
        Store edition mapping in cache

        Args:
            isbn: Normalized ISBN
            title: Book title
            edition_id: Edition ID to cache
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                normalized_title = title.lower().strip()
                current_time = datetime.now().isoformat()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO books 
                    (isbn, title, edition_id, updated_at) 
                    VALUES (?, ?, ?, ?)
                """,
                    (isbn, normalized_title, edition_id, current_time),
                )

                conn.commit()
                self.logger.debug(
                    f"Cached edition mapping for {title}: {isbn} -> {edition_id}"
                )

        except Exception as e:
            self.logger.error(f"Error storing edition mapping for {title}: {str(e)}")

    # Progress-related methods
    def get_last_progress(self, isbn: str, title: str) -> Optional[float]:
        """
        Get last synced progress for a book

        Args:
            isbn: Normalized ISBN
            title: Book title

        Returns:
            Last synced progress percentage if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT progress_percent FROM books WHERE isbn = ? AND title = ?",
                    (isbn, title.lower().strip()),
                )
                result = cursor.fetchone()

                if result and result["progress_percent"] is not None:
                    progress = float(result["progress_percent"])
                    self.logger.debug(
                        f"Found last progress for {title}: {progress:.1f}%"
                    )
                    return progress
                return None

        except Exception as e:
            self.logger.error(f"Error getting progress for {title}: {str(e)}")
            return None

    def store_progress(self, isbn: str, title: str, progress_percent: float) -> None:
        """
        Store progress for a book

        Args:
            isbn: Normalized ISBN
            title: Book title
            progress_percent: Progress percentage to cache
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                normalized_title = title.lower().strip()
                current_time = datetime.now().isoformat()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO books 
                    (isbn, title, progress_percent, last_synced, updated_at) 
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        isbn,
                        normalized_title,
                        progress_percent,
                        current_time,
                        current_time,
                    ),
                )

                conn.commit()
                self.logger.debug(
                    f"Cached progress for {title}: {progress_percent:.1f}%"
                )

        except Exception as e:
            self.logger.error(f"Error storing progress for {title}: {str(e)}")

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

    # Cache management methods
    def clear_cache(self) -> None:
        """Clear all cached data"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM books")
                conn.commit()
                self.logger.info("Book cache cleared")
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get total books
                cursor.execute("SELECT COUNT(*) as total FROM books")
                total_books = cursor.fetchone()["total"]

                # Get books with editions
                cursor.execute(
                    "SELECT COUNT(*) as count FROM books WHERE edition_id IS NOT NULL"
                )
                books_with_editions = cursor.fetchone()["count"]

                # Get books with progress
                cursor.execute(
                    "SELECT COUNT(*) as count FROM books WHERE progress_percent IS NOT NULL"
                )
                books_with_progress = cursor.fetchone()["count"]

                # Get file size
                cache_file_size = (
                    os.path.getsize(self.cache_file)
                    if os.path.exists(self.cache_file)
                    else 0
                )

                return {
                    "total_books": total_books,
                    "books_with_editions": books_with_editions,
                    "books_with_progress": books_with_progress,
                    "cache_file_size": cache_file_size,
                }

        except Exception as e:
            self.logger.error(f"Error getting cache stats: {str(e)}")
            return {
                "total_books": 0,
                "books_with_editions": 0,
                "books_with_progress": 0,
                "cache_file_size": 0,
            }

    def migrate_from_old_caches(self) -> None:
        """Migrate data from old JSON cache files"""
        # Migrate edition cache
        edition_cache_file = ".edition_cache.json"
        if os.path.exists(edition_cache_file):
            try:
                with open(edition_cache_file, "r") as f:
                    old_edition_data = json.load(f)

                migrated_count = 0
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    current_time = datetime.now().isoformat()

                    for key, edition_data in old_edition_data.items():
                        # Parse key format: "isbn_title"
                        if "_" in key:
                            isbn = key.split("_", 1)[0]
                            title = key.split("_", 1)[1]

                            # Handle both old formats: direct edition_id or nested object
                            if isinstance(edition_data, dict):
                                edition_id = edition_data.get("edition_id")
                                # Use title from data if available, otherwise from key
                                title = edition_data.get("title", title)
                                isbn = edition_data.get("isbn", isbn)
                            else:
                                edition_id = edition_data

                            if edition_id:
                                cursor.execute(
                                    """
                                    INSERT OR REPLACE INTO books 
                                    (isbn, title, edition_id, created_at, updated_at) 
                                    VALUES (?, ?, ?, ?, ?)
                                """,
                                    (
                                        isbn,
                                        title,
                                        edition_id,
                                        current_time,
                                        current_time,
                                    ),
                                )
                                migrated_count += 1

                    conn.commit()

                self.logger.info(
                    f"Migrated {migrated_count} edition mappings from old cache"
                )

                # Remove old cache file
                os.remove(edition_cache_file)
                self.logger.info("Removed old edition cache file")

            except Exception as e:
                self.logger.warning(f"Failed to migrate edition cache: {str(e)}")

        # Migrate progress cache
        progress_cache_file = ".progress_cache.json"
        if os.path.exists(progress_cache_file):
            try:
                with open(progress_cache_file, "r") as f:
                    old_progress_data = json.load(f)

                migrated_count = 0
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    current_time = datetime.now().isoformat()

                    for key, progress_info in old_progress_data.items():
                        # Parse key format: "isbn_title"
                        if "_" in key:
                            isbn = key.split("_", 1)[0]
                            title = key.split("_", 1)[1]

                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO books 
                                (isbn, title, progress_percent, last_synced, created_at, updated_at) 
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    isbn,
                                    title,
                                    progress_info.get("progress_percent"),
                                    progress_info.get("last_synced"),
                                    current_time,
                                    current_time,
                                ),
                            )
                            migrated_count += 1

                    conn.commit()

                self.logger.info(
                    f"Migrated {migrated_count} progress records from old cache"
                )

                # Remove old cache file
                os.remove(progress_cache_file)
                self.logger.info("Removed old progress cache file")

            except Exception as e:
                self.logger.warning(f"Failed to migrate progress cache: {str(e)}")

    def export_to_json(self, filename: str = "book_cache_export.json") -> None:
        """Export cache data to JSON for backup/debugging"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM books ORDER BY isbn, title")
                rows = cursor.fetchall()

                export_data = {}
                for row in rows:
                    key = f"{row['isbn']}_{row['title']}"
                    export_data[key] = {
                        "edition_id": row["edition_id"],
                        "progress_percent": row["progress_percent"],
                        "last_synced": row["last_synced"],
                        "title": row["title"],
                        "isbn": row["isbn"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }

                with open(filename, "w") as f:
                    json.dump(export_data, f, indent=2)

                self.logger.info(f"Cache exported to {filename}")

        except Exception as e:
            self.logger.error(f"Error exporting cache: {str(e)}")


class SyncManager:
    """Manages synchronization between Audiobookshelf and Hardcover"""

    def __init__(self, config: Any, dry_run: bool = False) -> None:
        """Initialize SyncManager with configuration"""
        self.config = config
        self.dry_run = dry_run
        self.min_progress_threshold = config.MIN_PROGRESS_THRESHOLD
        self.logger = logging.getLogger(__name__)

        # Initialize API clients
        self.audiobookshelf = AudiobookshelfClient(
            config.AUDIOBOOKSHELF_URL, config.AUDIOBOOKSHELF_TOKEN
        )
        self.hardcover = HardcoverClient(config.HARDCOVER_TOKEN)

        # Initialize book cache and migrate from old caches
        self.book_cache = BookCache()
        self.book_cache.migrate_from_old_caches()

        # Get sync configuration
        self.sync_config = config.get_sync_config()

        # Performance optimization settings
        self.max_workers = getattr(
            config, "MAX_WORKERS", 3
        )  # Limit concurrent API calls
        self.enable_parallel = getattr(config, "ENABLE_PARALLEL", True)
        self.timing_data = {}  # Store timing information

        self.logger.info(
            f"SyncManager initialized (dry_run: {dry_run}, min_threshold: {self.min_progress_threshold}%, parallel: {self.enable_parallel}, workers: {self.max_workers})"
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
            sync_start_time = time.time()

            if self.enable_parallel and len(syncable_books) > 1:
                # Parallel processing
                self.logger.info(
                    f"Processing {len(syncable_books)} books in parallel with {self.max_workers} workers"
                )
                sync_results = self._sync_books_parallel(
                    syncable_books, isbn_to_hardcover, result
                )
            else:
                # Sequential processing with detailed timing
                self.logger.info(f"Processing {len(syncable_books)} books sequentially")
                sync_results = self._sync_books_sequential(
                    syncable_books, isbn_to_hardcover, result
                )

            # Process results and update counters
            for sync_result in sync_results:
                if sync_result["status"] == "synced":
                    result["books_synced"] += 1
                    self.logger.info(f"✓ Synced: {sync_result['title']}")
                elif sync_result["status"] == "completed":
                    result["books_completed"] += 1
                    self.logger.info(f"✓ Completed: {sync_result['title']}")
                elif sync_result["status"] == "auto_added":
                    result["books_auto_added"] += 1
                    self.logger.info(f"✓ Auto-added: {sync_result['title']}")
                elif sync_result["status"] == "skipped":
                    result["books_skipped"] += 1
                    self.logger.info(
                        f"⏭ Skipped: {sync_result['title']} - {sync_result['reason']}"
                    )
                elif sync_result["status"] == "failed":
                    self.logger.error(
                        f"✗ Failed: {sync_result['title']} - {sync_result['reason']}"
                    )

                result["details"].append(sync_result)

            sync_duration = time.time() - sync_start_time
            self.timing_data["sync_loop"] = sync_duration
            self.logger.info(f"Sync loop completed in {sync_duration:.2f}s")

            result["success"] = True

            # Print timing summary
            self.print_timing_summary()

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

    def _sync_books_sequential(
        self,
        syncable_books: List[Dict],
        isbn_to_hardcover: Dict[str, Dict],
        result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process books sequentially with detailed timing"""
        sync_results = []

        with tqdm(total=len(syncable_books), desc="Syncing books", unit="book") as pbar:
            for abs_book in syncable_books:
                book_start_time = time.time()
                result["books_processed"] += 1

                try:
                    # Get book title for progress display
                    title = (
                        abs_book.get("media", {})
                        .get("metadata", {})
                        .get("title", "Unknown")
                    )
                    progress_percent = abs_book.get("progress_percentage", 0)

                    # Update progress bar
                    pbar.set_description(
                        f"Syncing: {title[:30]}{'...' if len(title) > 30 else ''}"
                    )
                    pbar.set_postfix(
                        {
                            "progress": f"{progress_percent:.1f}%",
                            "processed": result["books_processed"],
                        }
                    )

                    # Sync the book
                    sync_result = self._sync_single_book(abs_book, isbn_to_hardcover)
                    sync_results.append(sync_result)

                    # Update progress bar with result
                    if sync_result["status"] == "synced":
                        pbar.set_postfix(
                            {
                                "status": "✓ Synced",
                                "progress": f"{progress_percent:.1f}%",
                            }
                        )
                    elif sync_result["status"] == "completed":
                        pbar.set_postfix(
                            {
                                "status": "✓ Completed",
                                "progress": f"{progress_percent:.1f}%",
                            }
                        )
                    elif sync_result["status"] == "auto_added":
                        pbar.set_postfix(
                            {
                                "status": "✓ Added",
                                "progress": f"{progress_percent:.1f}%",
                            }
                        )
                    elif sync_result["status"] == "skipped":
                        pbar.set_postfix(
                            {
                                "status": "⏭ Skipped",
                                "reason": sync_result["reason"][:20],
                            }
                        )
                    elif sync_result["status"] == "failed":
                        pbar.set_postfix(
                            {"status": "✗ Failed", "error": sync_result["reason"][:20]}
                        )

                except Exception as e:
                    error_msg = (
                        f"Error syncing {abs_book.get('title', 'Unknown')}: {str(e)}"
                    )
                    pbar.set_postfix({"status": "✗ Error", "error": str(e)[:20]})
                    self.logger.error(error_msg)
                    result["errors"].append(error_msg)
                    sync_results.append(
                        {"status": "failed", "title": "Unknown", "reason": error_msg}
                    )

                # Record timing for this book
                book_duration = time.time() - book_start_time
                self.timing_data[f"book_{title[:20]}"] = book_duration
                pbar.set_postfix({"time": f"{book_duration:.2f}s"})
                pbar.update(1)

        return sync_results

    def _sync_books_parallel(
        self,
        syncable_books: List[Dict],
        isbn_to_hardcover: Dict[str, Dict],
        result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process books in parallel with timing"""
        sync_results = []

        def sync_single_book_wrapper(abs_book: Dict) -> Dict[str, Any]:
            """Wrapper to time individual book syncs"""
            book_start_time = time.time()
            title = (
                abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
            )

            try:
                sync_result = self._sync_single_book(abs_book, isbn_to_hardcover)
                book_duration = time.time() - book_start_time
                self.timing_data[f"book_{title[:20]}"] = book_duration
                self.logger.debug(f"Book '{title}' synced in {book_duration:.2f}s")
                return sync_result
            except Exception as e:
                book_duration = time.time() - book_start_time
                self.timing_data[f"book_{title[:20]}"] = book_duration
                error_msg = f"Error syncing {title}: {str(e)}"
                self.logger.error(error_msg)
                return {"status": "failed", "title": title, "reason": error_msg}

        # Process books in parallel
        with tqdm(
            total=len(syncable_books), desc="Syncing books (parallel)", unit="book"
        ) as pbar:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                # Submit all books for processing
                future_to_book = {
                    executor.submit(sync_single_book_wrapper, book): book
                    for book in syncable_books
                }

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_book):
                    abs_book = future_to_book[future]
                    result["books_processed"] += 1

                    try:
                        sync_result = future.result()
                        sync_results.append(sync_result)

                        # Update progress bar
                        title = (
                            abs_book.get("media", {})
                            .get("metadata", {})
                            .get("title", "Unknown")
                        )
                        progress_percent = abs_book.get("progress_percentage", 0)
                        book_time = self.timing_data.get(f"book_{title[:20]}", 0)

                        if sync_result["status"] == "synced":
                            pbar.set_postfix(
                                {"status": "✓ Synced", "time": f"{book_time:.2f}s"}
                            )
                        elif sync_result["status"] == "completed":
                            pbar.set_postfix(
                                {"status": "✓ Completed", "time": f"{book_time:.2f}s"}
                            )
                        elif sync_result["status"] == "auto_added":
                            pbar.set_postfix(
                                {"status": "✓ Added", "time": f"{book_time:.2f}s"}
                            )
                        elif sync_result["status"] == "skipped":
                            pbar.set_postfix(
                                {"status": "⏭ Skipped", "time": f"{book_time:.2f}s"}
                            )
                        elif sync_result["status"] == "failed":
                            pbar.set_postfix(
                                {"status": "✗ Failed", "time": f"{book_time:.2f}s"}
                            )

                    except Exception as e:
                        error_msg = f"Error processing book: {str(e)}"
                        self.logger.error(error_msg)
                        result["errors"].append(error_msg)
                        sync_results.append(
                            {
                                "status": "failed",
                                "title": "Unknown",
                                "reason": error_msg,
                            }
                        )

                    pbar.update(1)

        return sync_results

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
            if not self.book_cache.has_progress_changed(isbn, title, progress_percent):
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
            cached_edition_id = self.book_cache.get_edition_for_book(isbn, title)

        # Select edition using enhanced logic with cache
        edition = self._select_edition_with_cache(
            abs_book, hardcover_match, cached_edition_id, title
        )

        # Store the selected edition in cache for future use
        if isbn and edition:
            self.book_cache.store_edition_mapping(isbn, title, edition["id"])

        # Check if we have cached progress and can skip API calls
        cached_progress = None
        if isbn:
            cached_progress = self.book_cache.get_last_progress(isbn, title)

        # If we have cached progress and it matches current progress, skip expensive API calls
        if (
            cached_progress is not None
            and abs(cached_progress - progress_percent) < 0.1
        ):
            self.logger.debug(
                f"Using cached progress for {title}: {progress_percent:.1f}%"
            )

            # Store the current progress in cache (in case it's slightly different)
            if isbn:
                self.book_cache.store_progress(isbn, title, progress_percent)

            return {
                "status": "skipped",
                "title": title,
                "reason": f"Using cached progress ({progress_percent:.1f}% same as last sync)",
            }

        # Only make API calls if we don't have cached data or progress has changed
        current_progress = self.hardcover.get_book_current_progress(user_book_id)
        current_user_book = None

        if current_progress and current_progress.get("user_book"):
            current_user_book = current_progress["user_book"]
            # Check if we need to update the book status based on progress threshold
            status_result = self._check_and_update_book_status(
                current_user_book, progress_percent, title
            )
            # Log status check result if there was a change
            if status_result["status"] in ["status_updated", "would_update_status"]:
                self.logger.info(f"Status check: {status_result['reason']}")

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

            # Skip progress sync for 0% progress to avoid API errors
            if progress_percent == 0.0:
                # Store the progress in cache even for 0% (for tracking purposes)
                if isbn:
                    self.book_cache.store_progress(isbn, title, progress_percent)

                return {
                    "status": "skipped",
                    "title": title,
                    "reason": "0% progress - no progress sync (cached)",
                }

            # Calculate current page from percentage
            current_page = max(1, int((progress_percent / 100) * total_pages))

            if not self.dry_run:
                # Check if we need to update the book status first
                status_result = self._check_and_update_book_status(
                    user_book, progress_percent, title
                )

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
                        self.book_cache.store_progress(isbn, title, progress_percent)

                    return {
                        "status": "synced",
                        "title": title,
                        "progress": f"{current_page}/{total_pages} pages ({progress_percent:.1f}%)",
                        "status_check": status_result,
                    }
                else:
                    return {
                        "status": "failed",
                        "title": title,
                        "reason": "Failed to update progress",
                        "status_check": status_result,
                    }
            else:
                # Check if we need to update the book status first
                status_result = self._check_and_update_book_status(
                    user_book, progress_percent, title
                )

                # Log dry-run sync details
                self.logger.info(
                    f"Would sync {title}: {progress_percent:.1f}% → page {current_page}/{total_pages} (edition {edition_id})"
                )
                return {
                    "status": "would_sync",
                    "title": title,
                    "progress": f"Would sync to {current_page}/{total_pages} pages ({progress_percent:.1f}%)",
                    "status_check": status_result,
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
        """Get cache statistics"""
        return self.book_cache.get_cache_stats()

    def clear_cache(self) -> None:
        """Clear the book cache"""
        self.book_cache.clear_cache()

    def migrate_from_old_caches(self) -> None:
        """Migrate data from old JSON cache files to SQLite"""
        self.book_cache.migrate_from_old_caches()

    def export_to_json(self, filename: str = "book_cache_export.json") -> None:
        """Export cache data to JSON for backup/debugging"""
        self.book_cache.export_to_json(filename)

    def _get_cached_book_status(self, user_book_id: int, title: str) -> Optional[Dict]:
        """Get cached book status to avoid API calls"""
        # For now, we'll always make the API call, but we could extend the cache
        # to store book status information as well
        return None

    def get_timing_data(self) -> Dict[str, float]:
        """Get timing data for performance analysis"""
        return self.timing_data.copy()

    def print_timing_summary(self) -> None:
        """Print a summary of timing data"""
        if not self.timing_data:
            self.logger.info("No timing data available")
            return

        self.logger.info("=" * 50)
        self.logger.info("📊 TIMING SUMMARY")
        self.logger.info("=" * 50)

        # Sort by duration (descending)
        sorted_timing = sorted(
            self.timing_data.items(), key=lambda x: x[1], reverse=True
        )
        total_time = sum(self.timing_data.values())

        for operation, duration in sorted_timing:
            percentage = (duration / total_time) * 100 if total_time > 0 else 0
            self.logger.info(f"{operation:30} {duration:8.3f}s ({percentage:5.1f}%)")

        self.logger.info(f"{'TOTAL':30} {total_time:8.3f}s")
        self.logger.info("=" * 50)

    def _check_and_update_book_status(
        self, user_book: Dict, progress_percent: float, title: str
    ) -> Dict[str, Any]:
        """
        Check if a book should be moved between "Want to Read" and "Currently Reading"
        based on progress threshold
        """
        user_book_id = user_book["id"]
        current_status_id = user_book.get("status_id")

        # Check if progress has crossed the threshold
        if progress_percent >= self.min_progress_threshold:
            # Move from "Want to Read" (1) to "Currently Reading" (2) if needed
            if current_status_id == 1:
                if not self.dry_run:
                    success = self.hardcover.update_book_status(user_book_id, 2)

                    if success:
                        self.logger.info(
                            f"🔄 Moved '{title}' from 'Want to Read' to 'Currently Reading' "
                            f"({progress_percent:.1f}% >= {self.min_progress_threshold}% threshold)"
                        )
                        return {
                            "status": "status_updated",
                            "title": title,
                            "reason": f"Moved to Currently Reading ({progress_percent:.1f}% >= {self.min_progress_threshold}% threshold)",
                        }
                    else:
                        return {
                            "status": "failed",
                            "title": title,
                            "reason": "Failed to update book status",
                        }
                else:
                    self.logger.info(
                        f"Would move '{title}' from 'Want to Read' to 'Currently Reading' "
                        f"({progress_percent:.1f}% >= {self.min_progress_threshold}% threshold)"
                    )
                    return {
                        "status": "would_update_status",
                        "title": title,
                        "reason": f"Would move to Currently Reading ({progress_percent:.1f}% >= {self.min_progress_threshold}% threshold)",
                    }
            else:
                return {
                    "status": "no_change",
                    "title": title,
                    "reason": "Already in appropriate status",
                }

        else:
            # Move from "Currently Reading" (2) to "Want to Read" (1) if below threshold
            if current_status_id == 2:
                if not self.dry_run:
                    success = self.hardcover.update_book_status(user_book_id, 1)

                    if success:
                        self.logger.info(
                            f"🔄 Moved '{title}' from 'Currently Reading' to 'Want to Read' "
                            f"({progress_percent:.1f}% < {self.min_progress_threshold}% threshold)"
                        )
                        return {
                            "status": "status_updated",
                            "title": title,
                            "reason": f"Moved to Want to Read ({progress_percent:.1f}% < {self.min_progress_threshold}% threshold)",
                        }
                    else:
                        return {
                            "status": "failed",
                            "title": title,
                            "reason": "Failed to update book status",
                        }
                else:
                    self.logger.info(
                        f"Would move '{title}' from 'Currently Reading' to 'Want to Read' "
                        f"({progress_percent:.1f}% < {self.min_progress_threshold}% threshold)"
                    )
                    return {
                        "status": "would_update_status",
                        "title": title,
                        "reason": f"Would move to Want to Read ({progress_percent:.1f}% < {self.min_progress_threshold}% threshold)",
                    }
            else:
                return {
                    "status": "no_change",
                    "title": title,
                    "reason": "Already in appropriate status",
                }

        return {
            "status": "no_change",
            "title": title,
            "reason": "No status change needed",
        }
