"""
Configuration management for the sync tool
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv


class Config:
    """Configuration class that loads settings from environment variables"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._load_config()
        self._validate_config()

    def _load_config(self) -> None:
        """Load configuration from environment variables"""

        # Load secrets from secrets.env file
        if os.path.exists("secrets.env"):
            load_dotenv("secrets.env")
            self.logger.info("Loaded secrets from secrets.env")

        # Load additional settings from .env file
        if os.path.exists(".env"):
            load_dotenv(".env")
            self.logger.debug("Loaded additional configuration from .env")

        # Audiobookshelf settings
        self.AUDIOBOOKSHELF_URL = os.getenv(
            "AUDIOBOOKSHELF_URL", "http://localhost:13378"
        )
        self.AUDIOBOOKSHELF_TOKEN = os.getenv("AUDIOBOOKSHELF_TOKEN", "")

        # Hardcover settings
        self.HARDCOVER_TOKEN = os.getenv("HARDCOVER_TOKEN", "")

        # Sync settings
        self.DEFAULT_SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_HOURS", "6"))
        self.DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("true", "1", "yes")

        # Logging settings
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.LOG_FILE = os.getenv("LOG_FILE", "abs_hardcover_sync.log")

        # Rate limiting and retry settings
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        self.RETRY_DELAY = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

        self.logger.info("Configuration loaded from environment variables")

    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        errors = []

        if not self.AUDIOBOOKSHELF_TOKEN:
            errors.append("AUDIOBOOKSHELF_TOKEN is required")

        if not self.HARDCOVER_TOKEN:
            errors.append("HARDCOVER_TOKEN is required")

        if not self.AUDIOBOOKSHELF_URL:
            errors.append("AUDIOBOOKSHELF_URL is required")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"- {error}" for error in errors
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self.logger.info("Configuration validation passed")

    def get_audiobookshelf_config(self) -> dict:
        """Get Audiobookshelf configuration as dictionary"""
        return {"url": self.AUDIOBOOKSHELF_URL, "token": self.AUDIOBOOKSHELF_TOKEN}

    def get_hardcover_config(self) -> dict:
        """Get Hardcover configuration as dictionary"""
        return {"token": self.HARDCOVER_TOKEN}

    def get_sync_config(self) -> dict:
        """Get sync configuration as dictionary"""
        return {
            "interval_hours": self.DEFAULT_SYNC_INTERVAL,
            "dry_run": self.DRY_RUN,
            "max_retries": self.MAX_RETRIES,
            "retry_delay": self.RETRY_DELAY,
        }

    def __str__(self) -> str:
        """String representation of config (without sensitive data)"""
        return f"""Configuration:
  Audiobookshelf URL: {self.AUDIOBOOKSHELF_URL}
  Audiobookshelf Token: {'[SET]' if self.AUDIOBOOKSHELF_TOKEN else '[NOT SET]'}
  Hardcover Token: {'[SET]' if self.HARDCOVER_TOKEN else '[NOT SET]'}
  Sync Interval: {self.DEFAULT_SYNC_INTERVAL} hours
  Dry Run: {self.DRY_RUN}
  Log Level: {self.LOG_LEVEL}
  Max Retries: {self.MAX_RETRIES}
  Retry Delay: {self.RETRY_DELAY} seconds"""
