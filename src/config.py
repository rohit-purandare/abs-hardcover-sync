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

        # Load secrets from config/secrets.env file
        if os.path.exists("config/secrets.env"):
            load_dotenv("config/secrets.env")
            self.logger.info("Loaded secrets from config/secrets.env")

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

        # Default to True unless explicitly set to a "falsey" value
        dry_run_env = os.getenv("DRY_RUN", "true").lower()
        self.DRY_RUN = dry_run_env not in ("false", "0", "no", "n")

        self.MIN_PROGRESS_THRESHOLD = float(os.getenv("MIN_PROGRESS_THRESHOLD", "5.0"))

        # Logging settings
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.LOG_FILE = os.getenv("LOG_FILE", "abs_hardcover_sync.log")

        # Rate limiting and retry settings
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        self.RETRY_DELAY = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

        # Performance optimization settings
        # Default to True unless explicitly set to a "falsey" value
        enable_parallel_env = os.getenv("ENABLE_PARALLEL", "true").lower()
        self.ENABLE_PARALLEL = enable_parallel_env not in ("false", "0", "no", "n")

        self.MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3"))

        # Cron settings
        self.SYNC_SCHEDULE = os.getenv("SYNC_SCHEDULE", "0 * * * *")
        self.TIMEZONE = os.getenv("TIMEZONE", "UTC")

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
            "min_progress_threshold": self.MIN_PROGRESS_THRESHOLD,
        }

    def get_cron_config(self) -> dict:
        """Get cron configuration as dictionary"""
        return {
            "schedule": self.SYNC_SCHEDULE,
            "timezone": self.TIMEZONE,
        }

    def __str__(self) -> str:
        """String representation of config (without sensitive data)"""
        return f"""Configuration:
  Audiobookshelf URL: {self.AUDIOBOOKSHELF_URL}
  Audiobookshelf Token: {'[SET]' if self.AUDIOBOOKSHELF_TOKEN else '[NOT SET]'}
  Hardcover Token: {'[SET]' if self.HARDCOVER_TOKEN else '[NOT SET]'}
  Sync Interval: {self.DEFAULT_SYNC_INTERVAL} hours
  Dry Run: {self.DRY_RUN}
  Min Progress Threshold: {self.MIN_PROGRESS_THRESHOLD}%
  Log Level: {self.LOG_LEVEL}
  Max Retries: {self.MAX_RETRIES}
  Retry Delay: {self.RETRY_DELAY} seconds
  Sync Schedule: {self.SYNC_SCHEDULE}
  Timezone: {self.TIMEZONE}"""
