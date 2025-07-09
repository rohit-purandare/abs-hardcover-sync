"""
Sync Manager - Coordinates synchronization between Audiobookshelf and Hardcover
"""

import concurrent.futures
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

from src.audiobookshelf_client import AudiobookshelfClient
from src.hardcover_client import HardcoverClient
from src.utils import normalize_isbn, normalize_asin

if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


class BookCache:
    """SQLite-based cache for storing book edition mappings and progress tracking, now multi-user aware"""

    def __init__(self, cache_file: str = "data/.book_cache.db"):
        self.cache_file = cache_file
        self.logger = logging.getLogger(__name__)
        import os
        abs_path = os.path.abspath(self.cache_file)
        self.logger.info(f"BookCache: Database file path: {self.cache_file} (absolute: {abs_path})")
        try:
            self._init_database()
            self.logger.debug(f"SQLite cache initialized: {self.cache_file}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database at {self.cache_file}: {str(e)}")
            raise

    def _init_database(self) -> None:
        """Initialize SQLite database with schema, now with user_id column"""
        try:
            import os
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir and not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
                self.logger.info(f"Created cache directory: {cache_dir}")

            with sqlite3.connect(self.cache_file) as conn:
                cursor = conn.cursor()
                # Create books table with user_id
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        identifier TEXT NOT NULL,
                        identifier_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        edition_id INTEGER,
                        author TEXT,
                        last_progress REAL DEFAULT 0.0,
                        progress_percent REAL DEFAULT 0.0,
                        last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, identifier, title)
                    )
                """)
                # Add user_id column if missing (for migration)
                try:
                    cursor.execute("ALTER TABLE books ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON books(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_identifier ON books(identifier)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_identifier_type ON books(identifier_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON books(title)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_edition_id ON books(edition_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_author ON books(author)")
                conn.commit()
                self.logger.info(f"Database schema initialized successfully at {self.cache_file}")
        except Exception as e:
            self.logger.error(f"Database initialization failed: {str(e)}")
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
    def get_edition_for_book(self, user_id: int, identifier: str, title: str, identifier_type: str = "isbn") -> Optional[int]:
        """
        Get cached edition ID for a book

        Args:
            user_id: The user ID for which to fetch the cache.
            identifier: Normalized identifier (ISBN or ASIN)
            title: Book title
            identifier_type: Type of identifier ('isbn' or 'asin')

        Returns:
            Edition ID if found in cache, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT edition_id FROM books WHERE user_id = ? AND identifier = ? AND identifier_type = ? AND title = ?",
                    (user_id, identifier, identifier_type, title.lower().strip()),
                )
                result = cursor.fetchone()

                if result and result["edition_id"]:
                    self.logger.debug(
                        f"Cache hit for {title}: edition {result['edition_id']} (using {identifier_type.upper()})"
                    )
                    return int(result["edition_id"])
                return None

        except Exception as e:
            self.logger.error(f"Error getting edition for {title}: {str(e)}")
            return None

    def store_edition_mapping(
        self, user_id: int, identifier: str, title: str, edition_id: int, identifier_type: str = "isbn", author: Optional[str] = None
    ) -> None:
        """
        Store edition mapping in cache
        Only updates edition_id, author, and updated_at if the row exists, does not overwrite progress_percent.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                normalized_title = title.lower().strip()
                current_time = datetime.now().isoformat()

                # Check if the row exists
                cursor.execute(
                    "SELECT 1 FROM books WHERE user_id = ? AND identifier = ? AND identifier_type = ? AND title = ?",
                    (user_id, identifier, identifier_type, normalized_title),
                )
                exists = cursor.fetchone()

                if exists:
                    # Only update edition_id, author, updated_at
                    cursor.execute(
                        """
                        UPDATE books SET edition_id = ?, author = ?, updated_at = ?
                        WHERE user_id = ? AND identifier = ? AND identifier_type = ? AND title = ?
                        """,
                        (edition_id, author, current_time, user_id, identifier, identifier_type, normalized_title),
                    )
                else:
                    # Insert a new row, progress_percent will be default (0.0)
                    cursor.execute(
                        """
                        INSERT INTO books (user_id, identifier, identifier_type, title, author, edition_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, identifier, identifier_type, normalized_title, author, edition_id, current_time),
                    )

                conn.commit()
                self.logger.debug(
                    f"Cached edition mapping for {title}: {identifier} ({identifier_type.upper()}) -> {edition_id} (author: {author})"
                )

        except Exception as e:
            self.logger.error(f"Error storing edition mapping for {title}: {str(e)}")

    # Progress-related methods
    def get_last_progress(self, user_id: int, identifier: str, title: str, identifier_type: str = "isbn") -> Optional[float]:
        """
        Get last synced progress for a book
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                normalized_title = title.lower().strip()
                self.logger.info(f"[CACHE READ] user_id={user_id}, identifier={identifier}, identifier_type={identifier_type}, normalized_title='{normalized_title}'")
                cursor.execute(
                    "SELECT progress_percent FROM books WHERE user_id = ? AND identifier = ? AND identifier_type = ? AND title = ?",
                    (user_id, identifier, identifier_type, normalized_title),
                )
                result = cursor.fetchone()

                if result and result["progress_percent"] is not None:
                    progress = float(result["progress_percent"])
                    self.logger.debug(
                        f"Found last progress for {title}: {progress:.1f}% (using {identifier_type.upper()})"
                    )
                    return progress
                else:
                    self.logger.debug(f"No cached progress found for {title} ({identifier_type.upper()}: {identifier})")
                return None

        except Exception as e:
            self.logger.error(f"Error getting progress for {title}: {str(e)}")
            return None

    def store_progress(self, user_id: int, identifier: str, title: str, progress_percent: float, identifier_type: str = "isbn") -> None:
        """
        Store progress for a book
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                normalized_title = title.lower().strip()
                current_time = datetime.now().isoformat()
                self.logger.info(f"[CACHE WRITE] user_id={user_id}, identifier={identifier}, identifier_type={identifier_type}, normalized_title='{normalized_title}', progress_percent={progress_percent}")
                import traceback
                caller = traceback.extract_stack()[-2]

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO books 
                    (user_id, identifier, identifier_type, title, progress_percent, last_synced, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        identifier,
                        identifier_type,
                        normalized_title,
                        progress_percent,
                        current_time,
                        current_time,
                    ),
                )

                conn.commit()
                self.logger.debug(
                    f"Cached progress for {title}: {progress_percent:.1f}% (using {identifier_type.upper()}: {identifier})"
                )

        except Exception as e:
            self.logger.error(f"Error storing progress for {title}: {str(e)}")

    def has_progress_changed(
        self, user_id: int, identifier: str, title: str, current_progress: float, identifier_type: str = "isbn"
    ) -> bool:
        """
        Check if progress has changed since last sync

        Args:
            user_id: The user ID for which to check the cache.
            identifier: Normalized identifier (ISBN or ASIN)
            title: Book title
            current_progress: Current progress percentage
            identifier_type: Type of identifier ('isbn' or 'asin')

        Returns:
            True if progress has changed, False otherwise
        """
        last_progress = self.get_last_progress(user_id, identifier, title, identifier_type)
        
        if last_progress is None:
            self.logger.info(f"🔍 No previous progress found for {title} ({identifier_type}: {identifier}), considering as changed")
            return True

        # Check if progress has changed significantly (more than 0.1%)
        progress_diff = abs(current_progress - last_progress)
        has_changed = progress_diff > 0.1

        if has_changed:
            self.logger.info(
                f"🔍 Progress changed for {title}: {last_progress:.3f}% -> {current_progress:.3f}% (diff: {progress_diff:.3f}%)"
            )
        else:
            self.logger.info(
                f"🔍 No progress change for {title}: {current_progress:.3f}% (same as last sync: {last_progress:.3f}%)"
            )

        return has_changed

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

    def export_to_json(self, filename: str = "book_cache_export.json") -> None:
        """Export cache data to JSON for backup/debugging"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM books ORDER BY identifier, title")
                rows = cursor.fetchall()

                export_data = {}
                for row in rows:
                    key = f"{row['identifier']}_{row['title']}"
                    export_data[key] = {
                        "edition_id": row["edition_id"],
                        "progress_percent": row["progress_percent"],
                        "last_synced": row["last_synced"],
                        "title": row["title"],
                        "identifier": row["identifier"],
                        "identifier_type": row["identifier_type"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }

                with open(filename, "w") as f:
                    json.dump(export_data, f, indent=2)

                self.logger.info(f"Cache exported to {filename}")

        except Exception as e:
            self.logger.error(f"Error exporting cache: {str(e)}")

    def get_books_by_author(self, user_id: int, author_name: str) -> List[Dict[str, Any]]:
        """
        Get all books by a specific author

        Args:
            user_id: The user ID for which to fetch the cache.
            author_name: Name of the author to search for

        Returns:
            List of book records with author, title, isbn, and progress info
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT identifier, title, author, edition_id, progress_percent, last_synced
                    FROM books 
                    WHERE user_id = ? AND author = ?
                    ORDER BY title
                """,
                    (user_id, author_name),
                )
                results = cursor.fetchall()

                books = []
                for row in results:
                    books.append(
                        {
                            "identifier": row["identifier"],
                            "title": row["title"],
                            "author": row["author"],
                            "edition_id": row["edition_id"],
                            "progress_percent": row["progress_percent"],
                            "last_synced": row["last_synced"],
                        }
                    )

                self.logger.debug(f"Found {len(books)} books by {author_name}")
                return books

        except Exception as e:
            self.logger.error(f"Error getting books by author {author_name}: {str(e)}")
            return []


class SyncManager:
    """Manages synchronization between Audiobookshelf and Hardcover"""

    def __init__(self, user: dict, global_config: dict, dry_run: bool = False) -> None:
        """Initialize SyncManager with user dict and global config"""
        self.user = user
        self.global_config = global_config
        self.dry_run = dry_run
        self.min_progress_threshold = global_config["min_progress_threshold"]
        self.user_id = user['id']
        self.logger = logging.getLogger(f"SyncManager.{user['id']}")
        self.logger.setLevel(logging.DEBUG)

        # Performance optimization settings (set before initializing clients)
        self.max_workers = global_config.get("workers", 3)
        self.enable_parallel = global_config.get("parallel", True)
        self.timing_data: Dict[str, float] = {}  # Store timing information

        # Initialize API clients with user credentials
        self.audiobookshelf = AudiobookshelfClient(
            user["abs_url"], user["abs_token"], max_workers=self.max_workers
        )
        self.hardcover = HardcoverClient(user["hardcover_token"])

        # Initialize book cache (can be extended for per-user cache if needed)
        self.logger.info("Creating BookCache instance...")
        self.book_cache = BookCache()
        self.logger.info(f"BookCache created with cache_file: {self.book_cache.cache_file}")

        self.logger.info(
            f"SyncManager initialized for user {user['id']} (dry_run: {dry_run}, min_threshold: {self.min_progress_threshold}%, parallel: {self.enable_parallel}, workers: {self.max_workers})"
        )

    def _is_zero_progress(self, progress_value) -> bool:
        """
        Robustly check if a progress value represents 0% progress
        Handles various formats: None, 0, 0.0, "0", "0.0", etc.
        """
        if progress_value is None:
            return True
        try:
            return float(progress_value) == 0.0
        except (ValueError, TypeError):
            return True  # treat invalid values as zero

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

            # Create identifier lookup for Hardcover books (using editions data)
            self.logger.info("Creating identifier lookup table...")
            identifier_lookup = self._create_identifier_lookup(hardcover_books)

            # Pre-filter books with identifiers to reduce noise
            self.logger.info("Filtering books with identifiers and nonzero progress...")
            syncable_books = []
            books_without_identifiers = 0
            books_with_zero_progress = 0

            with tqdm(
                total=len(abs_progress), desc="Checking identifiers", unit="book"
            ) as pbar:
                for abs_book in abs_progress:
                    title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
                    progress = abs_book.get("progress_percentage", 0)
                    self.logger.info(f"[PREFILTER] Book: {title}, progress: {progress} (type: {type(progress)})")
                    # Comprehensive 0% check
                    if self._is_zero_progress(progress):
                        self.logger.info(f"[PREFILTER SKIP] Skipping {title} due to 0% progress (value: {progress})")
                        books_with_zero_progress += 1
                        pbar.update(1)
                        continue
                    identifiers = self._extract_book_identifier(abs_book)
                    if identifiers and (identifiers.get("asin") or identifiers.get("isbn")):
                        syncable_books.append(abs_book)
                    else:
                        books_without_identifiers += 1
                    pbar.update(1)

            self.logger.info(
                f"Found {len(syncable_books)} books with identifiers and nonzero progress, {books_without_identifiers} without identifiers, {books_with_zero_progress} with zero progress"
            )

            if not syncable_books:
                self.logger.warning("No books with identifiers and nonzero progress found for syncing")
                result["success"] = True
                return result

            # Sync books using the new identifier system
            sync_start_time = time.time()
            
            if self.enable_parallel:
                sync_results = self._sync_books_parallel(
                    syncable_books, identifier_lookup, result
                )
            else:
                sync_results = self._sync_books_sequential(
                    syncable_books, identifier_lookup, result
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

    def _create_identifier_lookup(self, hardcover_books: List[Dict]) -> Dict[str, Dict]:
        """
        Create lookup for both ASIN and ISBN identifiers
        Prioritizes ASIN for audiobooks, with ISBN as fallback
        """
        identifier_lookup = {}

        for user_book in hardcover_books:
            # Extract identifiers from editions - note the correct structure: user_book.book.editions
            book_data = user_book.get("book", {})
            editions = book_data.get("editions", [])
            if not editions:
                continue

            for edition in editions:
                # Add ASIN first (primary for audiobooks)
                asin = edition.get("asin") or edition.get("ASIN")
                if asin:
                    asin_normalized = normalize_asin(asin)
                    if asin_normalized:
                        identifier_lookup[asin_normalized] = {
                            "book": user_book,  # Store the full user_book record
                            "edition": edition,
                            "identifier_type": "asin",
                            "identifier_raw": asin,
                        }

                # Add ISBN-10 and ISBN-13 as fallback
                isbn_10 = edition.get("isbn_10")
                isbn_13 = edition.get("isbn_13")

                for isbn_raw in [isbn_10, isbn_13]:
                    if isbn_raw:
                        isbn_normalized = normalize_isbn(isbn_raw)
                        if isbn_normalized:
                            identifier_lookup[isbn_normalized] = {
                                "book": user_book,  # Store the full user_book record
                                "edition": edition,
                                "identifier_type": "isbn",
                                "identifier_raw": isbn_raw,
                            }

        self.logger.info(f"Created identifier lookup with {len(identifier_lookup)} entries")
        return identifier_lookup

    def _create_isbn_lookup(self, hardcover_books: List[Dict]) -> Dict[str, Dict]:
        """
        Create ISBN lookup (legacy method for backward compatibility)
        Now delegates to _create_identifier_lookup
        """
        return self._create_identifier_lookup(hardcover_books)

    def _sync_books_sequential(
        self,
        syncable_books: List[Dict],
        identifier_lookup: Dict[str, Dict],
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
                    sync_result = self._sync_single_book(abs_book, identifier_lookup)
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
        identifier_lookup: Dict[str, Dict],
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
                sync_result = self._sync_single_book(abs_book, identifier_lookup)
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

                    # The wrapper function catches exceptions and returns a dict,
                    # so we don't need a try/except block here.
                    sync_result = future.result()
                    sync_results.append(sync_result)

                    # Update progress bar
                    title = (
                        abs_book.get("media", {})
                        .get("metadata", {})
                        .get("title", "Unknown")
                    )
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

                    pbar.update(1)

        return sync_results

    def _sync_single_book(
        self, abs_book: Dict, identifier_lookup: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Sync progress for a single book using identifier matching (ASIN priority, ISBN fallback)"""

        title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
        progress_percent = abs_book.get("progress_percentage", 0)
        self.logger.debug(f"[SYNC CHECK] Book: {title}, progress_percent: {progress_percent} (type: {type(progress_percent)})")

        if self._is_zero_progress(progress_percent):
            self.logger.debug(f"[SYNC SKIP] Skipping {title} due to 0% progress (value: {progress_percent}, type: {type(progress_percent)})")
            return {"status": "skipped", "title": title, "reason": f"0% progress, not syncing or adding (value: {progress_percent}, type: {type(progress_percent)})"}

        identifiers = self._extract_book_identifier(abs_book)
        if not identifiers or (not identifiers.get("asin") and not identifiers.get("isbn")):
            return {"status": "skipped", "title": title, "reason": "No identifiers found"}

        asin = identifiers.get("asin")
        isbn = identifiers.get("isbn")
        hardcover_match = None
        identifier_used = None

        # 1. Try ASIN in user library
        if asin:
            hardcover_match = identifier_lookup.get(asin)
            if hardcover_match:
                identifier_used = "ASIN"
                if progress_percent >= self.min_progress_threshold:
                    return self._sync_existing_book(abs_book, hardcover_match)
                else:
                    return {"status": "skipped", "title": title, "reason": f"Progress {progress_percent:.1f}% below threshold for ASIN match"}
            # 2. If not in user library, search global
            search_results = self.hardcover.search_books_by_asin(asin)
            if search_results:
                if progress_percent >= self.min_progress_threshold:
                    # Add to library and sync
                    book_data = search_results[0]
                    edition = book_data["editions"][0]
                    user_book = self.hardcover.add_book_to_library(book_data["id"], 2, edition["id"])
                    if user_book:
                        return self._sync_progress_to_hardcover(user_book, edition, progress_percent, title, isbn, abs_book)
                    else:
                        return {"status": "failed", "title": title, "reason": "Failed to add ASIN edition to library"}
                else:
                    return {"status": "skipped", "title": title, "reason": f"Progress {progress_percent:.1f}% below threshold for global ASIN match"}
            # 3. If not found globally, fallback to ISBN

        # 4. Try ISBN in user library
        if isbn:
            hardcover_match = identifier_lookup.get(isbn)
            if hardcover_match:
                identifier_used = "ISBN"
                if progress_percent >= self.min_progress_threshold:
                    return self._sync_existing_book(abs_book, hardcover_match)
                else:
                    return {"status": "skipped", "title": title, "reason": f"Progress {progress_percent:.1f}% below threshold for ISBN match"}
            # 5. If not in user library, search global
            search_results = self.hardcover.search_books_by_isbn(isbn)
            if search_results:
                if progress_percent >= self.min_progress_threshold:
                    book_data = search_results[0]
                    edition = book_data["editions"][0]
                    user_book = self.hardcover.add_book_to_library(book_data["id"], 2, edition["id"])
                    if user_book:
                        return self._sync_progress_to_hardcover(user_book, edition, progress_percent, title, isbn, abs_book)
                    else:
                        return {"status": "failed", "title": title, "reason": "Failed to add ISBN edition to library"}
                else:
                    return {"status": "skipped", "title": title, "reason": f"Progress {progress_percent:.1f}% below threshold for global ISBN match"}
        # 6. If not found globally, skip
        return {"status": "skipped", "title": title, "reason": "No matching ASIN or ISBN found in user library or globally"}

    def _try_auto_add_book(self, abs_book: Dict, identifiers: Dict[str, Optional[str]]) -> Dict[str, Any]:
        """Try to automatically add book to Hardcover library"""
        title = abs_book.get("media", {}).get("metadata", {}).get("title", "Unknown")
        progress_percent = abs_book.get("progress_percentage", 0)
        self.logger.debug(f"[AUTO-ADD CHECK] Book: {title}, progress_percent: {progress_percent} (type: {type(progress_percent)})")

        # Comprehensive 0% check: skip add entirely
        if self._is_zero_progress(progress_percent):
            self.logger.info(f"[AUTO-ADD SKIP] Skipping {title} due to 0% progress (value: {progress_percent}, type: {type(progress_percent)})")
            return {"status": "skipped", "title": title, "reason": f"0% progress, not adding to Hardcover at all (auto-add path)"}

        # Skip if no identifiers
        if not identifiers or (not identifiers.get("asin") and not identifiers.get("isbn")):
            return {"status": "skipped", "title": title, "reason": "No identifiers found (auto-add path)"}

        try:
            # Search for book in Hardcover database by ISBN (fallback to ASIN if needed)
            isbn = identifiers.get("isbn")
            search_results = []
            
            if isbn:
                search_results = self.hardcover.search_books_by_isbn(isbn)
            
            # If no results with ISBN, try ASIN if available
            if not search_results:
                asin = identifiers.get("asin")
                if asin:
                    # Note: Hardcover API might not support ASIN search directly
                    self.logger.debug(f"No ISBN results for {title}, ASIN available: {asin}")

            if not search_results:
                return {
                    "status": "skipped",
                    "title": title,
                    "reason": "Book not found in Hardcover database (auto-add path)",
                }

            # Use the first search result
            book_data = search_results[0]
            editions = book_data.get("editions", [])

            if not editions:
                return {
                    "status": "skipped",
                    "title": title,
                    "reason": "No editions found for book (auto-add path)",
                }

            # Find the edition that matches the ISBN we searched for
            matching_edition = None
            for ed in editions:
                if (ed.get("isbn_10") == isbn or ed.get("isbn_13") == isbn):
                    matching_edition = ed
                    break
            
            # If no exact match found, use the first edition as fallback
            if not matching_edition:
                self.logger.warning(f"No exact ISBN match found for {title}, using first edition as fallback")
                matching_edition = editions[0]
            else:
                self.logger.info(f"Found exact ISBN match for {title}: edition {matching_edition['id']}")
            
            edition = matching_edition

            if not self.dry_run:
                # Add book to library with the specific edition
                user_book = self.hardcover.add_book_to_library(book_data["id"], 2 if progress_percent >= self.min_progress_threshold else 1, edition["id"])

                if user_book:
                    # Update progress
                    if progress_percent >= self.min_progress_threshold:
                        return self._sync_progress_to_hardcover(
                            user_book, edition, progress_percent, title, isbn, abs_book
                        )
                    else:
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

        # Extract identifiers for cache lookup
        identifiers = self._extract_book_identifier(abs_book)

        # Check cache first for edition preference (ASIN first, then ISBN)
        cached_edition_id = None
        asin = identifiers.get("asin") if identifiers else None
        isbn = identifiers.get("isbn") if identifiers else None
        if asin:
            cached_edition_id = self.book_cache.get_edition_for_book(self.user_id, asin, title, "asin")
        if not cached_edition_id and isbn:
            cached_edition_id = self.book_cache.get_edition_for_book(self.user_id, isbn, title, "isbn")

        # Select edition using enhanced logic with cache
        edition = self._select_edition_with_cache(
            abs_book, hardcover_match, cached_edition_id, title
        )

        # Store the selected edition in cache for future use (ASIN and ISBN if both exist)
        author = self._extract_author_from_data(abs_book, hardcover_match)
        if identifiers:
            if asin:
                self.book_cache.store_edition_mapping(self.user_id, asin, title, edition["id"], "asin", author)
            if isbn:
                self.book_cache.store_edition_mapping(self.user_id, isbn, title, edition["id"], "isbn", author)

        # Check if we have cached progress and can skip API calls (ASIN first, then ISBN)
        cached_progress = None
        if asin:
            cached_progress = self.book_cache.get_last_progress(self.user_id, asin, title, "asin")
        if cached_progress is None and isbn:
            cached_progress = self.book_cache.get_last_progress(self.user_id, isbn, title, "isbn")

        # If we have cached progress and it matches current progress, skip expensive API calls
        if cached_progress is not None and abs(cached_progress - progress_percent) < 0.1:
            self.logger.info(
                f"⏭ Skipping {title}: progress unchanged ({progress_percent:.1f}% cached: {cached_progress:.1f}%)"
            )

            # Store the current progress in cache for all identifiers (ASIN and ISBN)

            if identifiers:
                if asin:
                    self.book_cache.store_progress(self.user_id, asin, title, progress_percent, "asin")
                if isbn:
                    self.book_cache.store_progress(self.user_id, isbn, title, progress_percent, "isbn")

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
            result = self._handle_completion_status(
                user_book_id, edition, title, progress_percent, abs_book
            )
        else:
            # Check if book was previously completed but now below 95%
            result = self._handle_progress_status(
                user_book_id, edition, title, progress_percent, abs_book
            )

        # After a successful sync, update the cache for all identifiers (ASIN and ISBN)
        if result.get("status") in ["synced", "completed"] and identifiers:
            if asin:
                self.book_cache.store_progress(self.user_id, asin, title, progress_percent, "asin")
            if isbn:
                self.book_cache.store_progress(self.user_id, isbn, title, progress_percent, "isbn")

        return result

    def _is_audiobook(self, edition: Dict) -> bool:
        """Detect if an edition is an audiobook based on available fields"""
        # Check for audio_seconds (most reliable indicator)
        if edition.get("audio_seconds") and edition["audio_seconds"] > 0:
            return True
        
        # Check physical_format for audio indicators
        physical_format = edition.get("physical_format")
        if physical_format and isinstance(physical_format, str):
            physical_format_lower = physical_format.lower()
            if any(audio_indicator in physical_format_lower for audio_indicator in ["audio", "cd", "mp3", "aac"]):
                return True
        
        # Check reading_format for audio indicators
        reading_format = edition.get("reading_format", {})
        if isinstance(reading_format, dict):
            format_value = reading_format.get("format")
            if format_value and isinstance(format_value, str):
                format_lower = format_value.lower()
                if any(audio_indicator in format_lower for audio_indicator in ["audio", "audiobook"]):
                    return True
        
        return False

    def _sync_progress_to_hardcover(
        self,
        user_book: Dict,
        edition: Dict,
        progress_percent: float,
        title: str,
        isbn: Optional[str],
        abs_book: Dict,
    ) -> Dict[str, Any]:
        """Sync progress percentage to Hardcover, using audio seconds for audiobooks or pages for other formats"""

        try:
            user_book_id = user_book["id"]
            edition_id = edition["id"]
            
            # Debug logging for progress tracking
    
            
            # Extract identifiers using ASIN-first logic for cache operations
            identifiers = self._extract_book_identifier(abs_book)
            asin = identifiers.get("asin") if identifiers else None
            # Use provided isbn parameter, but fall back to extracted one if needed
            cache_isbn = isbn or identifiers.get("isbn") if identifiers else None
            
            # Detect if this is an audiobook
            is_audiobook = self._is_audiobook(edition)
            
            if is_audiobook:
                # Handle audiobook progress sync
                total_audio_seconds = edition.get("audio_seconds", 0)
                # Use currentTime from ABS if available
                abs_current_time = None
                # Try to get currentTime from Audiobookshelf book data
                media_metadata = abs_book.get("media", {}).get("metadata", {})
                if "currentTime" in media_metadata:
                    abs_current_time = media_metadata["currentTime"]
                elif "currentTime" in abs_book:
                    abs_current_time = abs_book["currentTime"]
                elif "progress" in abs_book and isinstance(abs_book["progress"], dict):
                    abs_current_time = abs_book["progress"].get("currentTime")
                # Fallback to calculated value if not present
                if abs_current_time is not None:
                    current_audio_seconds = int(abs_current_time)
                else:
                    current_audio_seconds = max(1, int((progress_percent / 100) * total_audio_seconds))
                sync_method = "audio_seconds"
                sync_details = f"{current_audio_seconds}/{total_audio_seconds} seconds"
            else:
                # Handle print/ebook progress sync
                total_pages = edition.get("pages", 0)
                
                if not total_pages:
                    return {
                        "status": "skipped",
                        "title": title,
                        "reason": "No page count available",
                    }
                
                current_page = max(1, int((progress_percent / 100) * total_pages))
                sync_method = "pages"
                sync_details = f"page {current_page}/{total_pages}"

            # Skip progress sync for 0% progress to avoid API errors
            if progress_percent == 0.0:
                self.logger.info(f"[PROGRESS DEBUG] Skipping 0% progress for '{title}' - storing 0.0 in cache")
                # Store the progress in cache even for 0% (for tracking purposes)
                # Store for both ASIN and ISBN if available
                if asin:
                    self.book_cache.store_progress(self.user_id, asin, title, progress_percent, "asin")
                if cache_isbn:
                    self.book_cache.store_progress(self.user_id, cache_isbn, title, progress_percent, "isbn")

                return {
                    "status": "skipped",
                    "title": title,
                    "reason": "0% progress - no progress sync (cached)",
                }

            if not self.dry_run:
                # Check if we need to update the book status first
                status_result = self._check_and_update_book_status(
                    user_book, progress_percent, title
                )

                # Log the sync details before attempting
                self.logger.info(
                    f"Syncing {title} ({'audiobook' if is_audiobook else 'print/ebook'}): "
                    f"{progress_percent:.1f}% → {sync_details} (edition {edition_id})"
                )

                # Update progress in Hardcover
                # Use progress_seconds for audiobooks, progress_pages for print/ebook
                use_seconds = bool(is_audiobook and edition.get("audio_seconds"))
                success = self.hardcover.update_reading_progress(
                    user_book_id, current_audio_seconds if use_seconds else current_page, progress_percent, edition_id, use_seconds
                )

                if success:
                    # Store the synced progress in cache (for both above and below threshold)
                    # Store for both ASIN and ISBN if available
    
                    if asin:
                        self.book_cache.store_progress(self.user_id, asin, title, progress_percent, "asin")
                    if cache_isbn:
                        self.book_cache.store_progress(self.user_id, cache_isbn, title, progress_percent, "isbn")

                    return {
                        "status": "synced",
                        "title": title,
                        "progress": f"{sync_details} ({progress_percent:.1f}%)",
                        "sync_method": sync_method,
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
                    f"Would sync {title} ({'audiobook' if is_audiobook else 'print/ebook'}): "
                    f"{progress_percent:.1f}% → {sync_details} (edition {edition_id})"
                )
                
                # Store the progress in cache even in dry-run mode
                # Store for both ASIN and ISBN if available
                if asin:
                    self.book_cache.store_progress(self.user_id, asin, title, progress_percent, "asin")
                if cache_isbn:
                    self.book_cache.store_progress(self.user_id, cache_isbn, title, progress_percent, "isbn")
                
                return {
                    "status": "would_sync",
                    "title": title,
                    "progress": f"Would sync to {sync_details} ({progress_percent:.1f}%)",
                    "sync_method": sync_method,
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

    def _extract_book_identifier(self, abs_book: Dict) -> Optional[Dict[str, Optional[str]]]:
        """
        Extract both ASIN and ISBN from Audiobookshelf book data
        Prioritizes ASIN for audiobooks, with ISBN as fallback
        """
        # Try to get identifiers from the correct metadata location: media.metadata
        media_metadata = abs_book.get("media", {}).get("metadata", {})

        # Try ASIN first (primary for audiobooks)
        asin = None
        asin_fields = ["asin", "ASIN", "amazon_asin", "amazon_asin_id"]
        for field in asin_fields:
            value = media_metadata.get(field)
            if value:
                normalized = normalize_asin(value)
                if normalized:
                    asin = normalized
                    break

        # Try ISBN as fallback
        isbn = None
        isbn_fields = ["isbn", "isbn13", "isbn10", "ISBN", "ISBN13", "ISBN10"]
        for field in isbn_fields:
            value = media_metadata.get(field)
            if value:
                normalized = normalize_isbn(value)
                if normalized:
                    isbn = normalized
                    break

        # Fallback: check top-level metadata (legacy support)
        if not asin and not isbn:
            metadata = abs_book.get("metadata", {})
            
            # Try ASIN in top-level metadata
            for field in asin_fields:
                value = metadata.get(field)
                if value:
                    normalized = normalize_asin(value)
                    if normalized:
                        asin = normalized
                        break

            # Try ISBN in top-level metadata
            for field in isbn_fields:
                value = metadata.get(field)
                if value:
                    normalized = normalize_isbn(value)
                    if normalized:
                        isbn = normalized
                        break

        # Return both if available
        if asin or isbn:
            return {"asin": asin, "isbn": isbn}

        return None

    def _extract_isbn_from_abs_book(self, abs_book: Dict) -> Optional[str]:
        """
        Extract ISBN from Audiobookshelf book data (legacy method)
        Now delegates to _extract_book_identifier for consistency
        """
        identifiers = self._extract_book_identifier(abs_book)
        return identifiers.get("isbn") if identifiers else None

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
        If already completed, just updates progress if it has changed.
        """
        self.logger.info(
            f"\U0001f4d6 Book completion check for {title}: {progress_percent:.1f}%"
        )

        # Check current status in Hardcover
        current_progress = self.hardcover.get_book_current_progress(user_book_id)
        current_status_id = None

        if current_progress and current_progress.get("user_book"):
            current_status_id = current_progress["user_book"].get("status_id")
            self.logger.debug(
                f"Current status for {title}: {current_status_id} (3=Read, 2=Currently Reading)"
            )

        # If already marked as completed (status_id=3), only update progress if it has changed
        if current_status_id == 3:
            # Extract identifiers using ASIN-first logic
            identifiers = self._extract_book_identifier(abs_book)
            asin = identifiers.get("asin") if identifiers else None
            isbn = identifiers.get("isbn") if identifiers else None
            
            # Debug logging to understand cache behavior
            self.logger.info(f"🔍 Cache check for {title}: ASIN={asin}, ISBN={isbn}, progress={progress_percent:.1f}%")
            
            # Check if progress has changed using the cache (ASIN first, then ISBN)
            progress_unchanged = False
            if asin and not self.book_cache.has_progress_changed(self.user_id, asin, title, progress_percent, "asin"):
                progress_unchanged = True
            elif isbn and not self.book_cache.has_progress_changed(self.user_id, isbn, title, progress_percent, "isbn"):
                progress_unchanged = True
            
            if progress_unchanged:
                self.logger.info(
                    f"✅ {title} already completed, progress unchanged, skipping update"
                )
                return {
                    "status": "skipped",
                    "title": title,
                    "reason": f"Already completed, no progress change ({progress_percent:.1f}%)",
                }
            
            # Progress has changed, update it
            self.logger.info(f"✅ {title} already completed, updating progress only")
            return self._sync_progress_to_hardcover(
                {"id": user_book_id}, edition, progress_percent, title, isbn, abs_book
            )

        # If not completed, mark as completed
        self.logger.info(f"\U0001f3af Marking {title} as completed for the first time")
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
        # Extract identifiers using ASIN-first logic
        identifiers = self._extract_book_identifier(abs_book)
        isbn = identifiers.get("isbn") if identifiers else None
        return self._sync_progress_to_hardcover(
            {"id": user_book_id}, edition, progress_percent, title, isbn, abs_book
        )

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return self.book_cache.get_cache_stats()

    def clear_cache(self) -> None:
        """Clear the book cache"""
        self.book_cache.clear_cache()

    def export_to_json(self, filename: str = "book_cache_export.json") -> None:
        """Export cache data to JSON for backup/debugging"""
        self.book_cache.export_to_json(filename)

    def get_books_by_author(self, user_id: int, author_name: str) -> List[Dict[str, Any]]:
        """Get all books by a specific author from the cache"""
        return self.book_cache.get_books_by_author(user_id, author_name)

    def _get_cached_book_status(self, user_book_id: int, title: str) -> Optional[Dict[str, Any]]:
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

    def _extract_author_from_data(
        self, abs_book: Dict, hardcover_match: Dict
    ) -> Optional[str]:
        """
        Extract author information from Hardcover data (primary) or Audiobookshelf data (fallback)

        Args:
            abs_book: Audiobookshelf book data
            hardcover_match: Hardcover book match data

        Returns:
            Author name if found, None otherwise
        """
        # Try to get author from Hardcover data first (better quality)
        try:
            book_data = hardcover_match.get("book", {})
            contributions = book_data.get("contributions", [])

            if contributions and len(contributions) > 0:
                # Get the first author (primary author)
                author_data = contributions[0].get("author")
                if author_data and author_data.get("name"):
                    author_name = author_data["name"]
                    self.logger.debug(f"Extracted author from Hardcover: {author_name}")
                    return str(author_name)
        except Exception as e:
            self.logger.debug(f"Could not extract author from Hardcover data: {str(e)}")

        # Fallback to Audiobookshelf data
        try:
            metadata = abs_book.get("media", {}).get("metadata", {})
            authors = metadata.get("authors", [])

            if authors and len(authors) > 0:
                # Get the first author (primary author)
                author = authors[0].get("name")
                if author:
                    self.logger.debug(
                        f"Extracted author from Audiobookshelf (fallback): {author}"
                    )
                    return str(author)
        except Exception as e:
            self.logger.debug(
                f"Could not extract author from Audiobookshelf data: {str(e)}"
            )

        return None
