"""
Configuration management for the sync tool
"""

import logging
import yaml
import os

class Config:
    """Configuration class that loads settings from config/config.yaml (YAML)"""

    def __init__(self, config_path="config/config.yaml") -> None:
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self._load_config()
        self._validate_config()

    def _load_config(self) -> None:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        self.global_config = config.get("global", {})
        self.users = config.get("users", [])
        self.logger.info(f"Loaded configuration from {self.config_path}")

    def _validate_config(self) -> None:
        errors = []
        # Validate global config
        required_globals = ["min_progress_threshold", "parallel", "workers", "dry_run", "sync_schedule", "timezone"]
        for key in required_globals:
            if key not in self.global_config:
                errors.append(f"Missing global config: {key}")
        # Validate users
        if not self.users:
            errors.append("No users defined in config")
        for user in self.users:
            for key in ["id", "abs_url", "abs_token", "hardcover_token"]:
                if key not in user:
                    errors.append(f"Missing user config: {key} for user {user.get('id', '[unknown]')}")
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        self.logger.info("Configuration validation passed")

    def get_global(self) -> dict:
        return self.global_config

    def get_users(self) -> list:
        return self.users

    def get_user(self, user_id: str) -> dict:
        for user in self.users:
            if user["id"] == user_id:
                return user
        raise KeyError(f"User not found: {user_id}")

    def get_cron_config(self) -> dict:
        """Get cron configuration from global settings"""
        return {
            "schedule": self.global_config.get("sync_schedule", "0 3 * * *"),
            "timezone": self.global_config.get("timezone", "Etc/UTC")
        }

    def __str__(self) -> str:
        users_str = ", ".join([user["id"] for user in self.users])
        return f"Config: users=[{users_str}], global={self.global_config}"
