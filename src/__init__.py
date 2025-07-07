"""
Audiobookshelf to Hardcover Sync Tool

A Python CLI tool that synchronizes audiobook listening progress from Audiobookshelf 
to reading progress in Hardcover using ISBN matching and progress conversion.
"""

__version__ = "1.0.0"
__author__ = "Rohit Purandare"

from .audiobookshelf_client import AudiobookshelfClient
from .config import Config
from .hardcover_client import HardcoverClient
from .main import main
from .sync_manager import SyncManager

__all__ = [
    "main",
    "Config",
    "SyncManager",
    "AudiobookshelfClient",
    "HardcoverClient",
]
