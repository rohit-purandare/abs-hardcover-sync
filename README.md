# Audiobookshelf to Hardcover Sync Tool

**Sync your audiobook listening progress from [Audiobookshelf](https://www.audiobookshelf.org/) to [Hardcover](https://hardcover.app/) automatically.**

- 📚 Match books by ISBN and sync progress
- 🔄 Runs on a schedule, in the background
- 🐳 Production-ready Docker image (Alpine, healthcheck, non-root)
- 🛡️ Secure: no secrets in the image, no data sent to third parties
- 💾 Persistent SQLite cache for efficient syncing
- 👥 **Multi-user support**: sync multiple users in one run

---

## 🚀 Quick Start (Docker Compose)

### Production (GHCR Image)

1. **Download the latest `docker-compose.yml` and config example:**
   ```sh
   curl -O https://raw.githubusercontent.com/rohit-purandare/audiobookshelf-hardcover-sync/main/docker-compose.yml
   mkdir -p config data
   curl -o config/config.yaml.example https://raw.githubusercontent.com/rohit-purandare/audiobookshelf-hardcover-sync/main/config/config.yaml.example
   cp config/config.yaml.example config/config.yaml
   # Edit config/config.yaml with your user(s) and API tokens
   ```

2. **Edit your `config/config.yaml`:**
   - Add one or more users under the `users:` section, each with their own Audiobookshelf and Hardcover tokens.
   - Set global options (sync schedule, timezone, etc.) in the `global:` section.
   - Example:
     ```yaml
     global:
       min_progress_threshold: 5.0
       parallel: true
       workers: 3
       dry_run: false
       sync_schedule: "0 3 * * *"  # Every day at 3am
       timezone: "Etc/UTC"  # Default: UTC. Change to your local timezone if needed
     users:
       - id: alice
         abs_url: https://audiobookshelf.alice.com
         abs_token: <alice_abs_token>
         hardcover_token: <alice_hardcover_token>
       - id: bob
         abs_url: https://audiobookshelf.bob.com
         abs_token: <bob_abs_token>
         hardcover_token: <bob_hardcover_token>
     ```

3. **Start the sync tool:**
   ```sh
   docker-compose up -d
   ```
   - The container will run in the background and sync on the schedule set in `config.yaml` (default: every day at 3am UTC).
   - To view logs:
     ```sh
     docker-compose logs -f abs-hardcover-sync
     ```
   - To stop the service:
     ```sh
     docker-compose down
     ```

4. **Manual sync (optional):**
   ```sh
   # Run a one-time sync for all users
   docker-compose run --rm abs-hardcover-sync sync --all-users
   # Run a one-time sync for a specific user
   docker-compose run --rm abs-hardcover-sync sync --user alice
   # Run a dry-run sync (no changes made)
   docker-compose run --rm abs-hardcover-sync sync --all-users --dry-run
   ```

### Development (Local Build)

For local development and testing with your own code changes:

1. **Use the local compose file:**
   ```sh
   docker-compose -f docker-compose.local.yml up -d
   ```

2. **Or build and run manually:**
   ```sh
   docker-compose -f docker-compose.local.yml build --no-cache
   docker-compose -f docker-compose.local.yml up -d
   ```

3. **Test your changes:**
   ```sh
   # Test with local build
   docker-compose -f docker-compose.local.yml run --rm abs-hardcover-sync sync --dry-run
   ```

---

## 🛠️ Docker Compose Example

```yaml
services:
  abs-hardcover-sync:
    image: ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest
    container_name: abs-hardcover-sync
    restart: unless-stopped
    user: "1000:1000"
    environment:
      - PYTHONPATH=/app
      - TZ=Etc/UTC  # Set to UTC by default; change to your local timezone if needed
    volumes:
      - ./config/config.yaml:/app/config/config.yaml:ro
      - ./data:/app/data
    # network_mode: host  # Only if you need host networking
    command: ["cron"]
    healthcheck:
      test: ["CMD", "python", "src/main.py", "--version"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

---

## ⚙️ Configuration Overview

- **config/config.yaml** (YAML):
  - `global:` section for global settings (schedule, timezone, etc.)
  - `users:` list for each user (id, abs_url, abs_token, hardcover_token)
  - See `config/config.yaml.example` for a template.
- **Timezone:**
  - `TZ` in Docker Compose sets the system timezone (for logs, etc.)
  - `timezone` in `config.yaml` sets the app's scheduling timezone (cron, etc.)
  - Both default to UTC for consistency; change as needed.

---

## 🖥️ CLI Usage

- **Sync all users (default):**
  ```sh
  python3 -m src.main sync --all-users
  ```
- **Sync a specific user:**
  ```sh
  python3 -m src.main sync --user alice
  ```
- **Other options:**
  - `--dry-run` (show what would be synced, no changes)
  - `--verbose` (detailed logging)
  - `--interactive` (menu-driven mode)

---

## How It Works & Features
- Fetches progress from Audiobookshelf for each user
- Matches books in Hardcover by ISBN
- Converts percentage to page number
- Updates reading progress in Hardcover
- Auto-completes books at 95%+
- Skips books with no ISBN or 0% progress
- **SQLite cache for efficient syncing** (multi-user aware)
- Parallel processing for speed
- Robust error handling and per-user logging
- **Multi-user:** Each user's sync is isolated and errors are reported per user

## Cache System
The tool uses a SQLite database (`data/.book_cache.db`) to cache:
- **Book editions** - Maps ISBNs to Hardcover edition IDs for faster lookups
- **Progress values** - Only syncs books when progress has changed
- **Author information** - Caches author data to reduce API calls
- **User isolation** - All cache data is keyed by user_id

**Benefits:**
- **First sync**: Full sync of all books with progress
- **Subsequent syncs**: Only books with changed progress are synced
- **Performance**: Significantly faster after the initial sync
- **Persistence**: Cache survives container restarts
- **Multi-user:** Each user's data is isolated in the cache

## Requirements
- Audiobookshelf server (with API access)
- Hardcover account (with API token)
- Docker (recommended) or Python 3.11+

## Advanced Usage & Development
- For Python CLI or development, see the [CLI Usage](#cli-usage) above.
- For details on cache, troubleshooting, or contributing, see the end of this file or open an issue.

## License
Open source. See LICENSE file for details.
