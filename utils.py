"""
Utility functions for the sync tool
"""

import logging
import re
from typing import Optional


def normalize_isbn(isbn: str) -> Optional[str]:
    """
    Normalize ISBN by removing hyphens, spaces, and other non-digit characters
    Returns clean ISBN or None if invalid
    """
    if not isbn:
        return None

    # Remove all non-digit and non-X characters (X can be in ISBN-10)
    clean_isbn = re.sub(r"[^0-9X]", "", isbn.upper())

    # Validate length
    if len(clean_isbn) not in [10, 13]:
        return None

    return clean_isbn


def calculate_progress_percentage(current_page: int, total_pages: int) -> float:
    """
    Calculate progress percentage from current page and total pages
    Returns percentage as float (0.0 to 100.0)
    """
    if total_pages <= 0:
        return 0.0

    if current_page <= 0:
        return 0.0

    if current_page >= total_pages:
        return 100.0

    return (current_page / total_pages) * 100.0


def calculate_current_page(progress_percentage: float, total_pages: int) -> int:
    """
    Calculate current page from progress percentage and total pages
    Returns page number as integer
    """
    if total_pages <= 0 or progress_percentage <= 0:
        return 0

    if progress_percentage >= 100:
        return total_pages

    # Use floor to be conservative with progress
    import math

    return math.floor((progress_percentage / 100) * total_pages)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def validate_isbn(isbn: str) -> bool:
    """
    Validate ISBN using checksum calculation
    Supports both ISBN-10 and ISBN-13
    """
    if not isbn:
        return False

    clean_isbn = normalize_isbn(isbn)
    if not clean_isbn:
        return False

    if len(clean_isbn) == 10:
        return _validate_isbn10(clean_isbn)
    elif len(clean_isbn) == 13:
        return _validate_isbn13(clean_isbn)

    return False


def _validate_isbn10(isbn: str) -> bool:
    """Validate ISBN-10 using checksum"""
    try:
        total = 0
        for i in range(9):
            total += int(isbn[i]) * (10 - i)

        # Handle check digit (can be X for 10)
        check_digit = isbn[9]
        if check_digit == "X":
            total += 10
        else:
            total += int(check_digit)

        return total % 11 == 0
    except (ValueError, IndexError):
        return False


def _validate_isbn13(isbn: str) -> bool:
    """Validate ISBN-13 using checksum"""
    try:
        total = 0
        for i in range(12):
            digit = int(isbn[i])
            if i % 2 == 0:
                total += digit
            else:
                total += digit * 3

        check_digit = int(isbn[12])
        calculated_check = (10 - (total % 10)) % 10

        return check_digit == calculated_check
    except (ValueError, IndexError):
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    # Remove invalid characters for filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Remove leading/trailing spaces and dots
    filename = filename.strip(" .")

    # Ensure it's not empty
    if not filename:
        filename = "unknown"

    return filename


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup logger with consistent formatting"""
    logger = logging.getLogger(name)

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create console handler if not already present
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def retry_on_failure(max_retries: int = 3, delay: int = 5):  # type: ignore
    """
    Decorator for retrying function calls on failure
    """

    def decorator(func):  # type: ignore
        def wrapper(*args, **kwargs):  # type: ignore
            logger = logging.getLogger(func.__module__)

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        # Last attempt, re-raise the exception
                        raise

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay} seconds..."
                    )

                    import time

                    time.sleep(delay)

        return wrapper

    return decorator
