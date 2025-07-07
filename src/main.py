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
from typing import Optional

import pytz
from croniter import croniter

try:
    from .config import Config
    from .sync_manager import SyncManager
except ImportError:
    # When running directly, use absolute imports
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


def sync_once(sync_manager: SyncManager) -> dict:
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

        # Return the full result for CLI summary
        return result

    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        return {"errors": [str(e)], "books_synced": 0, "books_completed": 0}


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
        result = sync_once(sync_manager)

        if result["errors"]:
            print("\n❌ Sync completed with errors. Check logs for details.")
            sys.exit(1)
        elif result["books_synced"] > 0 or result["books_completed"] > 0:
            print(
                f"\n✅ Sync completed successfully. {result['books_synced'] + result['books_completed']} books updated."
            )
            sys.exit(0)
        else:
            print("\n✅ Sync completed successfully. No changes needed.")
            sys.exit(0)

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

        # Migrate from old JSON caches if they exist
        sync_manager.migrate_from_old_caches()

        while True:
            print("\nCache Management Options:")
            print("1. 📊 Show cache statistics")
            print("2. 🗑️  Clear book cache")
            print("3. 🔄 Clear edition mappings (keep progress)")
            print("4. 📤 Export cache to JSON")
            print("5. 🔙 Back to main menu")

            choice = input("\nEnter your choice (1-5): ").strip()

            if choice == "1":
                # Show cache statistics
                cache_stats = sync_manager.get_cache_stats()

                print(f"\n📊 Book Cache Statistics:")
                print(f"   Total books: {cache_stats['total_books']}")
                print(f"   Books with editions: {cache_stats['books_with_editions']}")
                print(f"   Books with progress: {cache_stats['books_with_progress']}")
                print(f"   Cache file size: {cache_stats['cache_file_size']} bytes")

                if cache_stats["total_books"] > 0:
                    print(f"   📁 Cache file: .book_cache.db (SQLite)")
                else:
                    print("   📁 No book cache file exists yet")

                input("\nPress Enter to continue...")

            elif choice == "2":
                # Clear book cache
                confirm = (
                    input("🗑️  Are you sure you want to clear the book cache? (y/N): ")
                    .strip()
                    .lower()
                )
                if confirm in ["y", "yes"]:
                    sync_manager.clear_cache()
                    print("✅ Book cache cleared successfully!")
                else:
                    print("❌ Book cache clear cancelled.")
                input("\nPress Enter to continue...")

            elif choice == "3":
                # Clear edition mappings (keep progress)
                confirm = (
                    input(
                        "🔄 Are you sure you want to clear edition mappings? This will force re-syncing of editions and authors but keep progress data. (y/N): "
                    )
                    .strip()
                    .lower()
                )
                if confirm in ["y", "yes"]:
                    # Clear only edition mappings and author data
                    with sync_manager.book_cache._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE books SET edition_id = NULL, author = NULL"
                        )
                        affected_rows = cursor.rowcount
                        conn.commit()

                    print(f"✅ Edition mappings cleared for {affected_rows} books!")
                    print("📝 Next sync will re-fetch editions and author data.")
                else:
                    print("❌ Edition mapping clear cancelled.")
                input("\nPress Enter to continue...")

            elif choice == "4":
                # Export cache to JSON
                filename = input(
                    "Enter export filename (default: book_cache_export.json): "
                ).strip()
                if not filename:
                    filename = "book_cache_export.json"

                try:
                    sync_manager.export_to_json(filename)
                    print(f"✅ Cache exported to {filename}")
                except Exception as e:
                    print(f"❌ Export failed: {str(e)}")
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


def run_cron_mode(sync_manager: SyncManager, config: Config) -> None:
    """Run the sync tool in cron mode, continuously syncing based on schedule"""
    logger = logging.getLogger(__name__)

    # Get cron configuration
    cron_config = config.get_cron_config()
    schedule = cron_config["schedule"]
    timezone_name = cron_config["timezone"]

    # Set up timezone
    try:
        tz = pytz.timezone(timezone_name)
        logger.info(f"Using timezone: {timezone_name}")
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone: {timezone_name}. Using UTC.")
        tz = pytz.UTC

    # Create cron iterator
    try:
        cron = croniter(schedule, datetime.now(tz))
        logger.info(f"Cron schedule: {schedule}")
        logger.info(f"Next run: {cron.get_next(datetime)}")
    except Exception as e:
        logger.error(f"Invalid cron schedule '{schedule}': {str(e)}")
        return

    logger.info("🕐 Starting cron mode - sync will run automatically based on schedule")
    logger.info("Press Ctrl+C to stop")

    try:
        # Calculate time until next run
        now = datetime.now(tz)
        next_run = cron.get_next(datetime)
        time_until_next = (next_run - now).total_seconds()
        initial_time_until_next = time_until_next  # Save for startup log

        # Log at startup
        logger.info(
            f"⏰ Next sync in {time_until_next:.0f} seconds ({next_run.strftime('%Y-%m-%d %H:%M:%S')})"
        )

        while True:
            now = datetime.now(tz)
            time_until_next = (next_run - now).total_seconds()

            # Only log if <10 minutes to go
            if 0 < time_until_next <= 600:
                logger.info(
                    f"⏰ Next sync in {time_until_next:.0f} seconds ({next_run.strftime('%Y-%m-%d %H:%M:%S')})"
                )

            if time_until_next > 0:
                time.sleep(min(time_until_next, 60))
            else:
                # Time to sync
                logger.info("🔄 Running scheduled sync...")
                try:
                    result = sync_once(sync_manager)
                    if result["errors"]:
                        logger.warning(
                            f"Sync completed with {len(result['errors'])} errors"
                        )
                    else:
                        logger.info("✅ Scheduled sync completed successfully")
                except Exception as e:
                    logger.error(f"Scheduled sync failed: {str(e)}")

                # Update next run time
                cron = croniter(schedule, datetime.now(tz))
                next_run = cron.get_next(datetime)

    except KeyboardInterrupt:
        logger.info("🛑 Cron mode stopped by user")
    except Exception as e:
        logger.error(f"Cron mode failed: {str(e)}")


def main() -> None:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Sync reading progress between Audiobookshelf and Hardcover"
    )

    parser.add_argument(
        "command",
        nargs="?",  # Make command optional
        choices=["sync", "test", "config", "clear-cache", "clear-editions", "cron"],
        help="Command to execute: sync (one-time), test (connections), config (show configuration), clear-cache (clear all cache), clear-editions (clear edition mappings), or cron (continuous sync)",
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
            result = sync_once(sync_manager)
            if result["errors"]:
                print("\n❌ Sync completed with errors. Check logs for details.")
                sys.exit(1)
            elif result["books_synced"] > 0 or result["books_completed"] > 0:
                print(
                    f"\n✅ Sync completed successfully. {result['books_synced'] + result['books_completed']} books updated."
                )
                sys.exit(0)
            else:
                print("\n✅ Sync completed successfully. No changes needed.")
                sys.exit(0)

        elif args.command == "clear-cache":
            confirm = (
                input("🗑️  Are you sure you want to clear the book cache? (y/N): ")
                .strip()
                .lower()
            )
            if confirm in ["y", "yes"]:
                sync_manager.clear_cache()
                print("✅ Book cache cleared successfully!")
                print("📝 Next sync will be a full resync.")
            else:
                print("❌ Book cache clear cancelled.")
            sys.exit(0)

        elif args.command == "clear-editions":
            confirm = (
                input(
                    "🔄 Are you sure you want to clear edition mappings? This will force re-syncing of editions and authors but keep progress data. (y/N): "
                )
                .strip()
                .lower()
            )
            if confirm in ["y", "yes"]:
                with sync_manager.book_cache._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE books SET edition_id = NULL, author = NULL")
                    affected_rows = cursor.rowcount
                    conn.commit()

                print(f"✅ Edition mappings cleared for {affected_rows} books!")
                print("📝 Next sync will re-fetch editions and author data.")
            else:
                print("❌ Edition mapping clear cancelled.")
            sys.exit(0)

        elif args.command == "cron":
            run_cron_mode(sync_manager, config)
            sys.exit(0)

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
