# Debug Scripts

This folder contains various debug and utility scripts used during development and troubleshooting of the Audiobookshelf to Hardcover sync tool.

## Scripts Overview

### Core Debugging Tools
- **`debug_metadata.py`** - Examine Audiobookshelf metadata and ISBN extraction
- **`debug_hardcover.py`** - Examine Hardcover library data and ISBN extraction
- **`debug_edition_consistency.py`** - Debug edition consistency between progress records and sync editions
- **`debug_multiple_editions.py`** - Check for books with multiple progress records across different editions

### Cleanup Tools
- **`cleanup_duplicate_progress.py`** - Comprehensive cleanup script to consolidate duplicate progress records
- **`focused_cleanup.py`** - Targeted cleanup for specific duplicate progress issues

## Usage

These scripts are primarily for development and troubleshooting purposes. They require the same API credentials as the main sync tool.

Most scripts can be run directly:
```bash
python debug/debug_metadata.py
python debug/cleanup_duplicate_progress.py
```

## Important Notes

- **Backup your data** before running any cleanup scripts
- These scripts access live APIs and may make changes to your Hardcover data
- Review script output carefully before proceeding with destructive operations
- Some scripts include dry-run modes for safe testing

## Development History

These scripts were created during the development process to solve specific issues:
- ISBN matching problems
- Duplicate progress record cleanup
- Edition consistency verification
- Metadata extraction debugging

They remain here for future troubleshooting and development work.