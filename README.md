# Audiobookshelf to Hardcover Sync Tool

**Sync your audiobook listening progress from [Audiobookshelf](https://www.audiobookshelf.org/) to [Hardcover](https://hardcover.app/) automatically.**

- 📚 Match books by ISBN and sync progress
- 🔄 Runs on a schedule, in the background
- 🐳 Production-ready Docker image (Alpine, healthcheck, non-root)
- 🛡️ Secure: no secrets in the image, no data sent to third parties
- 💾 Persistent SQLite cache for efficient syncing

---

## 🚀 Quick Start Script Block

The fastest way to get started:

```sh
curl -O https://raw.githubusercontent.com/rohit-purandare/audiobookshelf-hardcover-sync/main/docker-compose.yml
mkdir -p config data
curl -o config/secrets.env https://raw.githubusercontent.com/rohit-purandare/audiobookshelf-hardcover-sync/main/config/secrets.env.example
# Edit config/secrets.env with your API tokens
# Then start the service:
docker-compose up -d
```

## 🚀 Step by Step (Recommended: Docker Compose)

You **do not need to clone this repo** to use the tool! Just:

1. **Create a minimal `docker-compose.yml` in your project or config directory:**
   ```yaml
   version: '3.8'
   services:
     abs-hardcover-sync:
       image: ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest
       container_name: abs-hardcover-sync
       restart: unless-stopped
       user: "1000:1000"  # Run as current user to avoid permission issues
       environment:
         - PYTHONPATH=/app
       volumes:
         # Mount config files for persistence
         - ./config/secrets.env:/app/config/secrets.env:ro
         # Mount cache directory for persistence
         - ./data:/app/data
       # Interactive mode for CLI
       stdin_open: true
       tty: true
       # Use host network for potential local API access
       network_mode: host
       # Default command - can be overridden
       command: ["cron"]
       # Healthcheck for Compose-level monitoring
       healthcheck:
         test: ["CMD", "python", "src/main.py", "--version"]
         interval: 30s
         timeout: 10s
         retries: 3
         start_period: 10s
   ```

2. **Create your config and data directories:**
   ```bash
   mkdir -p config data
   curl -o config/secrets.env https://raw.githubusercontent.com/rohit-purandare/audiobookshelf-hardcover-sync/main/config/secrets.env.example
   ```

3. **Edit your secrets file with your API tokens and server info:**
   - Open `config/secrets.env` in a text editor and fill in the required values:
   - **Audiobookshelf URL:** The URL of your Audiobookshelf server (e.g., `http://localhost:13378` or your remote server).
   - **Audiobookshelf API token:**
     - Go to your Audiobookshelf web interface
     - Settings → Users & Sessions → API Tokens
     - Create a new token and copy it here.
   - **Hardcover API token:**
     - Go to [hardcover.app/account/api](https://hardcover.app/account/api)
     - Copy the token (do NOT include the "Bearer " prefix).
   
   Example `config/secrets.env`:
   ```env
   AUDIOBOOKSHELF_URL=https://your-audiobookshelf-server.com
   AUDIOBOOKSHELF_TOKEN=your_audiobookshelf_api_token
   HARDCOVER_TOKEN=your_hardcover_api_token

   # Optional: Customize sync schedule and behavior
   SYNC_SCHEDULE=0 * * * *   # every hour (default)
   TIMEZONE=UTC
   MIN_PROGRESS_THRESHOLD=5.0
   ```

4. **Start the sync tool:**
   ```bash
   docker-compose up -d
   ```
   - The container will run in the background and sync on the schedule set in `config/secrets.env` (default: every hour).
   - To view logs:
     ```bash
     docker-compose logs -f abs-hardcover-sync
     ```
   - To stop the service:
     ```bash
     docker-compose down
     ```

5. **Manual sync (optional):**
   ```bash
   # Run a one-time sync
   docker-compose run --rm abs-hardcover-sync sync
   
   # Run a dry-run sync (no changes made)
   docker-compose run --rm abs-hardcover-sync sync --dry-run
   ```

---

## Quick Start: Python (For Developers/Advanced Users)

1. **Clone the repo and install dependencies:**
   ```bash
   git clone https://github.com/rohit-purandare/audiobookshelf-hardcover-sync.git
   cd audiobookshelf-hardcover-sync
   pip install -e .
   ```
2. **Configure your secrets:**
   ```bash
   cp config/secrets.env.example config/secrets.env
   # Edit config/secrets.env with your API tokens and settings
   ```
3. **Run the tool:**
   ```bash
   python src/main.py sync
   # or run interactively
   python src/main.py
   ```

---

> **Note:** Docker Compose is the recommended and easiest way to run this tool in production or for scheduled syncs. Python CLI is best for development or advanced customization.

## How It Works & Features
- Fetches progress from Audiobookshelf
- Matches books in Hardcover by ISBN
- Converts percentage to page number
- Updates reading progress in Hardcover
- Auto-completes books at 95%+
- Skips books with no ISBN or 0% progress
- **SQLite cache for efficient syncing** - only syncs books with changed progress
- Parallel processing for speed
- Robust error handling and logging

## Cache System
The tool uses a SQLite database (`data/.book_cache.db`) to cache:
- **Book editions** - Maps ISBNs to Hardcover edition IDs for faster lookups
- **Progress values** - Only syncs books when progress has changed
- **Author information** - Caches author data to reduce API calls

**Benefits:**
- **First sync**: Full sync of all books with progress
- **Subsequent syncs**: Only books with changed progress are synced
- **Performance**: Significantly faster after the initial sync
- **Persistence**: Cache survives container restarts

## Requirements
- Audiobookshelf server (with API access)
- Hardcover account (with API token)
- Docker (recommended) or Python 3.11+

## Advanced Usage & Development
- For Python CLI or development, see the [Python Quick Start](#quick-start-python-for-developersadvanced-users) above.
- For details on cache, troubleshooting, or contributing, see the end of this file or open an issue.

## License
Open source. See LICENSE file for details.
