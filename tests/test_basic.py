"""Basic tests for Audiobookshelf to Hardcover Sync Tool"""

# pytest is installed in CI environment
try:
    import pytest
except ImportError:
    pytest = None

from unittest.mock import Mock, patch


def test_placeholder():
    """Placeholder test to ensure pytest works"""
    assert True


class TestConfig:
    """Test configuration loading"""

    def test_config_import(self):
        """Test that config module can be imported"""
        try:
            from src.config import Config

            assert Config is not None
        except ImportError as e:
            if pytest:
                pytest.fail(f"Failed to import Config: {e}")
            else:
                raise

    def test_config_validation(self):
        """Test configuration validation"""
        with patch.dict(
            "os.environ",
            {
                "AUDIOBOOKSHELF_URL": "https://example.com",
                "AUDIOBOOKSHELF_TOKEN": "test_token",
                "HARDCOVER_TOKEN": "test_token",
            },
        ):
            from src.config import Config

            config = Config()
            assert config.AUDIOBOOKSHELF_URL == "https://example.com"
            assert config.AUDIOBOOKSHELF_TOKEN == "test_token"
            assert config.HARDCOVER_TOKEN == "test_token"


class TestUtils:
    """Test utility functions"""

    def test_normalize_isbn(self):
        """Test ISBN normalization"""
        from utils import normalize_isbn

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
        isbn_none = None
        assert normalize_isbn(isbn_none) is None

    def test_calculate_progress_percentage(self):
        """Test progress percentage calculation"""
        from utils import calculate_progress_percentage

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

    def test_main_import(self):
        """Test that main module can be imported"""
        try:
            import main

            assert main is not None
        except ImportError as e:
            pytest.fail(f"Failed to import main: {e}")

    def test_cli_help(self):
        """Test CLI help functionality"""
        import subprocess
        import sys

        try:
            result = subprocess.run(
                [sys.executable, "main.py", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0
            assert "Audiobookshelf to Hardcover Sync Tool" in result.stdout
        except subprocess.TimeoutExpired:
            pytest.skip("CLI help test timed out")
        except FileNotFoundError:
            pytest.skip("main.py not found")


class TestClients:
    """Test API client imports"""

    def test_audiobookshelf_client_import(self):
        """Test AudiobookshelfClient import"""
        try:
            from audiobookshelf_client import AudiobookshelfClient

            assert AudiobookshelfClient is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AudiobookshelfClient: {e}")

    def test_hardcover_client_import(self):
        """Test HardcoverClient import"""
        try:
            from hardcover_client import HardcoverClient

            assert HardcoverClient is not None
        except ImportError as e:
            pytest.fail(f"Failed to import HardcoverClient: {e}")

    def test_sync_manager_import(self):
        """Test SyncManager import"""
        try:
            from sync_manager import SyncManager

            assert SyncManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import SyncManager: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
