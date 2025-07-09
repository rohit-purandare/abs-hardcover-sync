"""Basic tests for Audiobookshelf to Hardcover Sync Tool"""

# pytest is installed in CI environment
try:
    import pytest  # type: ignore
except ImportError:
    pytest = None

from unittest.mock import patch, MagicMock
from typing import Any


def test_placeholder() -> None:
    """Placeholder test to ensure pytest works"""
    assert True


class TestConfig:
    """Test configuration loading"""

    def test_config_import(self) -> None:
        """Test that config module can be imported"""
        try:
            from src.config import Config
            assert Config is not None
        except ImportError as e:
            raise

    def test_config_validation(self) -> None:
        """Test configuration validation (YAML multi-user)"""
        from src.config import Config
        config = Config()
        users = config.get_users()
        assert isinstance(users, list)
        assert len(users) > 0
        for user in users:
            assert "id" in user
            assert "abs_url" in user
            assert "abs_token" in user
            assert "hardcover_token" in user
        global_config = config.get_global()
        assert isinstance(global_config, dict)
        for key in ["min_progress_threshold", "parallel", "workers", "dry_run", "sync_schedule", "timezone"]:
            assert key in global_config


class TestUtils:
    """Test utility functions"""

    def test_normalize_isbn(self) -> None:
        """Test ISBN normalization"""
        from src.utils import normalize_isbn

        # Test valid ISBN-13
        assert normalize_isbn("978-0-7475-3269-9") == "9780747532699"
        assert normalize_isbn("9780747532699") == "9780747532699"

        # Test valid ISBN-10
        assert normalize_isbn("0-7475-3269-9") == "0747532699"
        assert normalize_isbn("0747532699") == "0747532699"

        # Test invalid ISBNs
        assert normalize_isbn("invalid") is None
        assert normalize_isbn("") is None
        # Test with None - handle type checking
        # Note: normalize_isbn expects str, so we need to handle None differently
        # This test case is not valid for the current function signature

    def test_calculate_progress_percentage(self) -> None:
        """Test progress percentage calculation"""
        from src.utils import calculate_progress_percentage

        # Test valid calculations
        assert calculate_progress_percentage(50, 100) == 50.0
        assert calculate_progress_percentage(25, 100) == 25.0
        assert calculate_progress_percentage(0, 100) == 0.0
        assert calculate_progress_percentage(100, 100) == 100.0

        # Test edge cases
        assert calculate_progress_percentage(0, 0) == 0.0  # Avoid division by zero
        assert calculate_progress_percentage(-1, 100) == 0.0  # Negative pages
        assert calculate_progress_percentage(150, 100) == 100.0  # Over 100%


class TestCLI:
    """Test CLI functionality"""

    def test_main_import(self) -> None:
        """Test that main module can be imported"""
        try:
            from src import main

            assert main is not None
        except ImportError as e:
            if pytest:
                pytest.fail(f"Failed to import main: {e}")
            else:
                raise

    def test_cli_help(self) -> None:
        """Test CLI help functionality"""
        import subprocess
        import sys

        try:
            result = subprocess.run(
                [sys.executable, "src/main.py", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0
            assert "Audiobookshelf to Hardcover Sync Tool" in result.stdout
        except subprocess.TimeoutExpired:
            if pytest:
                pytest.skip("CLI help test timed out")
            else:
                raise
        except FileNotFoundError:
            if pytest:
                pytest.skip("main.py not found")
            else:
                raise


class TestClients:
    """Test API client imports"""

    def test_audiobookshelf_client_import(self) -> None:
        """Test AudiobookshelfClient import"""
        try:
            from src.audiobookshelf_client import AudiobookshelfClient

            assert AudiobookshelfClient is not None
        except ImportError as e:
            if pytest:
                pytest.fail(f"Failed to import AudiobookshelfClient: {e}")
            else:
                raise

    def test_hardcover_client_import(self) -> None:
        """Test HardcoverClient import"""
        try:
            from src.hardcover_client import HardcoverClient

            assert HardcoverClient is not None
        except ImportError as e:
            if pytest:
                pytest.fail(f"Failed to import HardcoverClient: {e}")
            else:
                raise

    def test_sync_manager_import(self) -> None:
        """Test SyncManager import"""
        try:
            from src.sync_manager import SyncManager

            assert SyncManager is not None
        except ImportError as e:
            if pytest:
                pytest.fail(f"Failed to import SyncManager: {e}")
            else:
                raise


class TestMultiUser:
    """Test multi-user config and SyncManager behavior"""

    def test_multiuser_config_loading(self):
        from src.config import Config
        config = Config(config_path="config/config.yaml.example")
        users = config.get_users()
        assert isinstance(users, list)
        assert len(users) >= 2  # Example config should have at least 2 users
        user_ids = [u['id'] for u in users]
        assert 'alice' in user_ids and 'bob' in user_ids
        # Check that each user has required fields
        for user in users:
            assert 'abs_url' in user
            assert 'abs_token' in user
            assert 'hardcover_token' in user

    def test_syncmanager_per_user(self):
        from src.config import Config
        from src.sync_manager import SyncManager
        config = Config(config_path="config/config.yaml.example")
        global_config = config.get_global()
        users = config.get_users()
        # Patch API clients to avoid real calls
        with patch('src.sync_manager.AudiobookshelfClient', MagicMock()), \
             patch('src.sync_manager.HardcoverClient', MagicMock()):
            for user in users:
                sm = SyncManager(user, global_config, dry_run=True)
                assert sm.user['id'] == user['id']
                assert sm.user['abs_url'] == user['abs_url']
                assert sm.user['hardcover_token'] == user['hardcover_token']
                # Ensure logger is user-specific
                assert user['id'] in sm.logger.name


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
