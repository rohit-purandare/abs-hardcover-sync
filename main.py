#!/usr/bin/env python3
"""
Audiobookshelf to Hardcover Reading Progress Sync Tool

A CLI tool that synchronizes reading progress between Audiobookshelf and Hardcover
using ISBN matching and progress percentage to current_page conversion.
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

from config import Config
from sync_manager import SyncManager


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration with controlled verbosity"""
    # Set up root logger with clean format
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatters
    detailed_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    clean_format = "%(asctime)s - %(levelname)s - %(message)s"

    # File handler (always detailed for debugging)
    file_handler = logging.FileHandler("abs_hardcover_sync.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(detailed_format))

    # Console handler (clean unless verbose)
    console_handler = logging.StreamHandler(sys.stdout)
    if verbose:
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(detailed_format))
    else:
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(clean_format))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress chatty third-party loggers unless in verbose mode
    if not verbose:
        # Suppress HTTP requests debug logs
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)

        # Suppress our own chatty client logs
        logging.getLogger("audiobookshelf_client").setLevel(logging.WARNING)
        logging.getLogger("hardcover_client").setLevel(logging.WARNING)


def sync_once(sync_manager: SyncManager) -> bool:
    """Perform a one-time synchronization"""
    logger = logging.getLogger(__name__)
    logger.info("Starting one-time sync...")

    start_time = time.time()

    try:
        result = sync_manager.sync_progress()

        # Log summary with visual formatting
        duration = time.time() - start_time
        logger.info("=" * 50)
        logger.info("📚 SYNC SUMMARY")
        logger.info("=" * 50)
        logger.info(f"⏱️  Duration: {duration:.1f}s")
        logger.info(f"📖 Books processed: {result['books_processed']}")
        logger.info(f"✅ Books synced: {result['books_synced']}")
        logger.info(f"🎯 Books completed: {result['books_completed']}")
        logger.info(f"➕ Books auto-added: {result['books_auto_added']}")
        logger.info(f"⏭ Books skipped: {result['books_skipped']}")

        if result["errors"]:
            logger.warning(f"❌ Errors encountered: {len(result['errors'])}")
            for error in result["errors"]:
                logger.error(f"  - {error}")
        else:
            logger.info("🎉 No errors encountered!")

        logger.info("=" * 50)

        return bool(result["books_synced"] > 0 or result["books_completed"] > 0)

    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        return False


def test_connections(sync_manager: SyncManager) -> bool:
    """Test connections to both APIs"""
    logger = logging.getLogger(__name__)
    logger.info("🔍 Testing API connections...")

    abs_status = False
    hc_status = False

    try:
        logger.info("📚 Testing Audiobookshelf connection...")
        abs_status = sync_manager.audiobookshelf.test_connection()
        if abs_status:
            logger.info("✅ Audiobookshelf connection: Success")
        else:
            logger.error("❌ Audiobookshelf connection: Failed")
    except Exception as e:
        logger.error(f"❌ Audiobookshelf connection failed: {str(e)}")
        abs_status = False

    try:
        logger.info("📖 Testing Hardcover connection...")
        hc_status = sync_manager.hardcover.test_connection()
        if hc_status:
            logger.info("✅ Hardcover connection: Success")
        else:
            logger.error("❌ Hardcover connection: Failed")
    except Exception as e:
        logger.error(f"❌ Hardcover connection failed: {str(e)}")
        hc_status = False

    # Summary
    logger.info("=" * 40)
    if abs_status and hc_status:
        logger.info("🎉 All connections successful!")
    else:
        logger.error("❌ Some connections failed!")
    logger.info("=" * 40)

    return abs_status and hc_status


def show_config(config: Config) -> bool:
    """Show configuration status and help"""
    logger = logging.getLogger(__name__)

    logger.info("=== Configuration Status ===")

    # Check secrets configuration
    secrets_status = []
    required_secrets = [
        ("AUDIOBOOKSHELF_URL", config.AUDIOBOOKSHELF_URL),
        ("AUDIOBOOKSHELF_TOKEN", config.AUDIOBOOKSHELF_TOKEN),
        ("HARDCOVER_TOKEN", config.HARDCOVER_TOKEN),
    ]

    for name, value in required_secrets:
        if value and value.strip():
            secrets_status.append(f"✓ {name}: Configured")
        else:
            secrets_status.append(f"✗ {name}: Missing")

    logger.info("Configuration Status:")
    for status in secrets_status:
        logger.info(f"  {status}")

    # Show configuration instructions
    missing_secrets = [
        name for name, value in required_secrets if not (value and value.strip())
    ]

    if missing_secrets:
        logger.info("\n=== Setup Instructions ===")
        logger.info("To configure missing secrets:")
        logger.info("1. Create/edit secrets.env file")
        logger.info("2. Add the missing values:")
        for secret in missing_secrets:
            if secret == "AUDIOBOOKSHELF_URL":
                logger.info(f"   {secret}=http://your-audiobookshelf-server:13378")
            else:
                logger.info(f"   {secret}=your_value_here")
    else:
        logger.info("✓ All secrets configured successfully!")

    return len(missing_secrets) == 0


def clear_screen() -> None:
    """Clear the terminal screen"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header() -> None:
    """Print the application header"""
    print(
        """
🔧 Audiobookshelf to Hardcover Sync Tool
========================================
"""
    )


def print_menu_options() -> None:
    """Print the main menu options"""
    print(
        """
What would you like to do?

1. 🔄 Sync books (one-time)
2. 🧪 Test API connections  
3. ⚙️  Show configuration status
4. 🔍 Sync with dry-run (test mode)
5. 📊 Sync with verbose logging
6. 🗂️  Cache management
7. ❓ Show help
8. 🚪 Exit

"""
    )


def show_help() -> None:
    """Show help information"""
    print(
        """
❓ Help - Audiobookshelf to Hardcover Sync Tool
===============================================

This tool synchronizes your audiobook listening progress from Audiobookshelf 
to reading progress in Hardcover.

COMMANDS:
• Sync books: Updates reading progress in Hardcover based on Audiobookshelf data
• Test connections: Verifies API access to both services
• Configuration: Shows current setup and helps with configuration

OPTIONS:
• Dry-run: Shows what would be synced without making changes
• Verbose: Provides detailed logging for troubleshooting

SETUP:
1. Copy secrets.env.example to secrets.env
2. Add your API tokens to secrets.env
3. Run 'Test connections' to verify setup

For more information, see the README.md file.
"""
    )
    input("\nPress Enter to continue...")


def run_interactive_mode() -> None:
    """Run the application in interactive mode"""
    while True:
        try:
            clear_screen()
            print_header()
            print_menu_options()

            choice = input("Enter your choice (1-8): ").strip()

            if choice == "1":
                # Sync books
                run_sync_interactive()
            elif choice == "2":
                # Test connections
                run_test_interactive()
            elif choice == "3":
                # Show configuration
                run_config_interactive()
            elif choice == "4":
                # Dry-run sync
                run_sync_interactive(dry_run=True)
            elif choice == "5":
                # Verbose sync
                run_sync_interactive(verbose=True)
            elif choice == "6":
                # Cache management
                run_cache_interactive()
            elif choice == "7":
                # Show help
                show_help()
            elif choice == "8":
                # Exit
                print("\n👋 Goodbye!")
                break
            else:
                print("\n❌ Invalid choice. Please try again.")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            input("Press Enter to continue...")


def run_sync_interactive(dry_run: bool = False, verbose: bool = False) -> None:
    """Run sync in interactive mode"""
    print(f"\n🔄 Starting sync...")
    if dry_run:
        print("🧪 DRY RUN MODE - No changes will be made")
    if verbose:
        print("📊 VERBOSE MODE - Detailed logging enabled")

    # Setup logging
    setup_logging(verbose=verbose)
    logger = logging.getLogger(__name__)

    try:
        config = Config()
        sync_manager = SyncManager(config, dry_run=dry_run)
        success = sync_once(sync_manager)

        if success:
            print("\n✅ Sync completed successfully!")
        else:
            print("\n❌ Sync completed with errors. Check logs for details.")

        input("\nPress Enter to continue...")

    except Exception as e:
        print(f"\n❌ Sync failed: {str(e)}")
        input("Press Enter to continue...")


def run_test_interactive() -> None:
    """Run connection test in interactive mode"""
    print("\n🧪 Testing API connections...")

    # Setup logging
    setup_logging(verbose=False)
    logger = logging.getLogger(__name__)

    try:
        config = Config()
        sync_manager = SyncManager(config, dry_run=False)
        success = test_connections(sync_manager)

        if success:
            print("\n✅ All connections successful!")
        else:
            print("\n❌ Some connections failed. Check your configuration.")

        input("\nPress Enter to continue...")

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        input("Press Enter to continue...")


def run_config_interactive() -> None:
    """Run configuration check in interactive mode"""
    print("\n⚙️  Checking configuration...")

    # Setup logging
    setup_logging(verbose=False)
    logger = logging.getLogger(__name__)

    try:
        config = Config()
        show_config(config)
        input("\nPress Enter to continue...")

    except Exception as e:
        print(f"\n❌ Configuration check failed: {str(e)}")
        input("Press Enter to continue...")


def run_cache_interactive() -> None:
    """Run cache management in interactive mode"""
    print("\n🗂️  Cache Management")
    print("=" * 40)

    # Setup logging
    setup_logging(verbose=False)
    logger = logging.getLogger(__name__)

    try:
        config = Config()
        sync_manager = SyncManager(
            config, dry_run=True
        )  # Use dry_run to avoid actual sync

        while True:
            print("\nCache Management Options:")
            print("1. 📊 Show cache statistics")
            print("2. 🗑️  Clear edition cache")
            print("3. 🗑️  Clear progress cache")
            print("4. 🗑️  Clear all caches")
            print("5. 🔙 Back to main menu")

            choice = input("\nEnter your choice (1-5): ").strip()

            if choice == "1":
                # Show cache statistics
                edition_stats = sync_manager.get_cache_stats()
                progress_stats = sync_manager.progress_cache.get_cache_stats()

                print(f"\n📊 Edition Cache Statistics:")
                print(f"   Total mappings: {edition_stats['total_mappings']}")
                print(f"   Cache file size: {edition_stats['cache_file_size']} bytes")

                if edition_stats["total_mappings"] > 0:
                    print(f"   📁 Cache file: .edition_cache.json")
                else:
                    print("   📁 No edition cache file exists yet")

                print(f"\n📊 Progress Cache Statistics:")
                print(f"   Total records: {progress_stats['total_records']}")
                print(f"   Cache file size: {progress_stats['cache_file_size']} bytes")

                if progress_stats["total_records"] > 0:
                    print(f"   📁 Cache file: .progress_cache.json")
                else:
                    print("   📁 No progress cache file exists yet")

                input("\nPress Enter to continue...")

            elif choice == "2":
                # Clear edition cache
                confirm = (
                    input(
                        "🗑️  Are you sure you want to clear the edition cache? (y/N): "
                    )
                    .strip()
                    .lower()
                )
                if confirm in ["y", "yes"]:
                    sync_manager.clear_edition_cache()
                    print("✅ Edition cache cleared successfully!")
                else:
                    print("❌ Edition cache clear cancelled.")
                input("\nPress Enter to continue...")

            elif choice == "3":
                # Clear progress cache
                confirm = (
                    input(
                        "🗑️  Are you sure you want to clear the progress cache? (y/N): "
                    )
                    .strip()
                    .lower()
                )
                if confirm in ["y", "yes"]:
                    sync_manager.clear_progress_cache()
                    print("✅ Progress cache cleared successfully!")
                else:
                    print("❌ Progress cache clear cancelled.")
                input("\nPress Enter to continue...")

            elif choice == "4":
                # Clear all caches
                confirm = (
                    input("🗑️  Are you sure you want to clear ALL caches? (y/N): ")
                    .strip()
                    .lower()
                )
                if confirm in ["y", "yes"]:
                    sync_manager.clear_all_caches()
                    print("✅ All caches cleared successfully!")
                else:
                    print("❌ Cache clear cancelled.")
                input("\nPress Enter to continue...")

            elif choice == "5":
                # Back to main menu
                break
            else:
                print("❌ Invalid choice. Please try again.")
                input("Press Enter to continue...")

    except Exception as e:
        print(f"\n❌ Cache management failed: {str(e)}")
        input("Press Enter to continue...")


def main() -> None:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Sync reading progress between Audiobookshelf and Hardcover"
    )

    parser.add_argument(
        "command",
        nargs="?",  # Make command optional
        choices=["sync", "test", "config"],
        help="Command to execute: sync (one-time), test (connections), or config (show configuration)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without making changes",
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode with menu selection",
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Force non-interactive mode (useful for automation)",
    )

    args = parser.parse_args()

    # Determine if we should run in interactive mode
    run_interactive = args.interactive or (not args.no_interactive and not args.command)

    if run_interactive:
        run_interactive_mode()
        return

    # CLI mode - require command
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Setup logging first
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = Config()

        # Handle config command separately
        if args.command == "config":
            show_config(config)
            return

        # Create sync manager
        sync_manager = SyncManager(config, dry_run=args.dry_run)

        # Execute command
        if args.command == "test":
            success = test_connections(sync_manager)
            sys.exit(0 if success else 1)

        elif args.command == "sync":
            success = sync_once(sync_manager)
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        if args.verbose:
            logger.exception("Full error details:")
        sys.exit(1)


if __name__ == "__main__":
    main()
