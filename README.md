# Audiobookshelf to Hardcover Sync Tool

**Sync your audiobook listening progress from [Audiobookshelf](https://www.audiobookshelf.org/) to [Hardcover](https://hardcover.app/)—automatically, reliably, and with zero manual effort.**

- 📚 Match books by ISBN and sync progress seamlessly
- 🔄 Runs on a schedule, in the background, with robust error handling
- 🐳 Production-ready Docker image (Alpine, healthcheck, non-root)
- 🛡️ Secure: no secrets in the image, no data sent to third parties

---

## 🚀 Quick Start (Recommended: Docker Compose)

You **do not need to clone this repo** to use the tool! Just:

1. **Create a minimal `docker-compose.yml` in your project or config directory:**
   ```yaml
   version: '3.8'
   services:
     abs-hardcover-sync:
       image: ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest
       container_name: abs-hardcover-sync
       restart: unless-stopped
       environment:
         - PYTHONPATH=/app
       volumes:
         - ./config/secrets.env:/app/config/secrets.env:ro
         - ./.progress_cache.json:/app/.progress_cache.json
         - ./.edition_cache.json:/app/.edition_cache.json
       healthcheck:
         test: ["CMD", "python", "src/main.py", "--version"]
         interval: 30s
         timeout: 10s
         retries: 3
         start_period: 10s
       command: ["cron"]
   ```

2. **Create your config directory and secrets file:**
   ```bash
   mkdir -p config
   curl -o config/secrets.env https://raw.githubusercontent.com/rohit-purandare/audiobookshelf-hardcover-sync/main/config/secrets.env.example
   # Edit config/secrets.env with your API tokens and settings
   ```

3. **Start the sync tool:**
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

---

## Quick Start: Docker CLI (Manual/Advanced)

1. **Pull the image:**
   ```bash
   docker pull ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest
   ```
2. **Create your config and secrets as above.**
3. **Run a one-time sync:**
   ```bash
   docker run --rm \
     -v $PWD/config/secrets.env:/app/config/secrets.env:ro \
     -v $PWD/.progress_cache.json:/app/.progress_cache.json \
     -v $PWD/.edition_cache.json:/app/.edition_cache.json \
     ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest sync
   ```
4. **Run in cron mode (scheduled syncs):**
   ```bash
   docker run -d --name abs-hardcover-sync \
     -v $PWD/config/secrets.env:/app/config/secrets.env:ro \
     -v $PWD/.progress_cache.json:/app/.progress_cache.json \
     -v $PWD/.edition_cache.json:/app/.edition_cache.json \
     ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest cron
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

## How It Works

The tool works by:

1. **Getting your progress** from Audiobookshelf
2. **Finding matching books** in your Hardcover library using ISBN
3. **Converting percentages to pages** (e.g., 71.5% of a 496-page book = page 354)
4. **Updating your reading progress** in Hardcover

### Example
```
Syncing Project Hail Mary: 71.5% → page 354/496
✓ Synced: Project Hail Mary
```

## Features

- **Simple Sync**: One command to sync all your audiobook progress
- **ISBN Matching**: Finds books in your Hardcover library using ISBN
- **Progress Conversion**: Converts listening percentages to page numbers
- **Auto-Complete**: Marks books as "Read" when you're 95%+ done
- **Dry Run Mode**: See what would be synced without making changes
- **Interactive Menu**: Easy-to-use menu system
- **Cache System**: Remembers your book editions for faster syncing
- **Progress Bars**: Visual feedback during syncing
- **Parallel processing for fast syncs:**
  - Audiobookshelf API calls (book details/progress) are fetched in parallel for up to 2x speedup
  - Hardcover API status/progress updates are performed in parallel with built-in rate limiting (max 50 requests/minute, 5 workers)
  - Typical syncs are now 2–4x faster than before
- **Robust error handling and detailed logging**
- **GitHub Actions CI/CD, security scanning, and pre-commit hooks**

## Requirements

- Python 3.11 or newer
- Audiobookshelf server (with API access)
- Hardcover account (with API token)
- Internet connection

## Project Structure

```
audiobookshelf-hardcover-sync/
├── src/                    # Application code
│   ├── main.py            # CLI entry point
│   ├── config.py          # Configuration management
│   ├── sync_manager.py    # Main sync logic
│   ├── audiobookshelf_client.py
│   ├── hardcover_client.py
│   └── utils.py
├── docker/                 # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── DOCKER.md
│   └── start-docker.sh
├── config/                 # Configuration files
│   ├── secrets.env         # Main secrets/config file
│   └── secrets.env.example # Example config
├── data/                   # Persistent data (created automatically)
└── ...
```

## Setup

### 1. Get Your API Tokens

**Audiobookshelf:**
- Go to your Audiobookshelf web interface
- Settings → Users & Sessions → API Tokens
- Create a new token

**Hardcover:**
- Visit [hardcover.app/account/api](https://hardcover.app/account/api)
- Copy your API token (do NOT include "Bearer " prefix)

### 2. Create Config File
```bash
cp config/secrets.env.example config/secrets.env
```

### 3. Add Your Tokens
Edit `config/secrets.env`:
```bash
# Your Audiobookshelf server
AUDIOBOOKSHELF_URL=https://your-audiobookshelf-server.com
AUDIOBOOKSHELF_TOKEN=your_audiobookshelf_api_token

# Your Hardcover token
HARDCOVER_TOKEN=your_hardcover_api_token

# Optional: Customize sync behavior
MIN_PROGRESS_THRESHOLD=5.0  # Only add to "Currently Reading" if 5%+ progress
```

### 4. Test Your Setup
```bash
python src/main.py config
```

## Usage

**Important:** Always run the CLI from the project root directory so it can find your `config/secrets.env` file:
```bash
cd /path/to/audiobookshelf-hardcover-sync
python src/main.py test
```
If you run the script from another directory, it may not find your config file and will report missing API tokens.

### Quick Start
```bash
# Run with interactive menu (default)
python src/main.py

# Test your connections
python src/main.py test

# Sync your progress
python src/main.py sync

# See what would be synced (no changes)
python src/main.py sync --dry-run
```

### Interactive Mode
```bash
# Run with menu (this is the default)
python src/main.py --interactive

# Force non-interactive mode
python src/main.py sync --no-interactive
```

### All Commands
```bash
python src/main.py sync      # Sync your progress
python src/main.py test      # Test connections
python src/main.py config    # Show your setup
python src/main.py --help    # Show all options
```

### Auto-Sync (Optional)
Set up automatic syncing with cron:
```bash
# Edit your crontab
crontab -e

# Sync every 6 hours
0 */6 * * * cd /path/to/sync-tool && python src/main.py sync
```

## Docker & Containerization

- **Alpine-based image:** The official Docker image is now based on `python:3.11-alpine` for a smaller, more secure, and efficient build.
- **Healthcheck:** The Docker image and Compose setup include a healthcheck for better container monitoring and reliability.
- **Non-root user:** The container runs as a non-root user for improved security.
- **.dockerignore:** The project uses a robust `.dockerignore` to keep images small and secure by excluding unnecessary files.

### Docker Deployment

#### Using GitHub Container Registry (Recommended)

The project automatically builds and publishes a minimal, Alpine-based Docker image to GitHub Container Registry:

```bash
# Pull the latest image (Alpine-based)
docker pull ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync:latest
```

- The image is based on `python:3.11-alpine` for reduced size and attack surface.
- Includes a built-in healthcheck for container monitoring.
- Runs as a non-root user for security.
- Uses a robust `.dockerignore` to keep images lean.

#### Using Docker Compose (Recommended for Scheduled Syncs)

```bash
# Start the sync tool in scheduled (cron) mode
docker-compose up -d
```

By default, the container will:
- Stay running in the background
- Sync your progress on the schedule you set in `config/secrets.env` (e.g., every hour)
- Restart automatically if stopped or after a reboot (due to `restart: unless-stopped`)

**To change the sync schedule:**  
Edit `config/secrets.env`:
```env
SYNC_SCHEDULE=0 * * * *   # every hour (default)
TIMEZONE=UTC              # or your preferred timezone
```

**To view logs:**
```bash
docker-compose logs -f abs-hardcover-sync
```

**To stop the service:**
```bash
docker-compose down
```

#### Building Locally

```bash
# Build the image (Alpine-based)
docker build -t abs-hardcover-sync:alpine -t abs-hardcover-sync:latest .

# Run the container
# (mount your config and cache files as needed)
docker run -it --rm \
  -v $PWD/config/secrets.env:/app/config/secrets.env:ro \
  -v $PWD/.progress_cache.json:/app/.progress_cache.json \
  -v $PWD/.edition_cache.json:/app/.edition_cache.json \
  abs-hardcover-sync:latest
```

**Configure sync schedule in `config/secrets.env`:**
```bash
# Sync every hour (default)
SYNC_SCHEDULE=0 * * * *

# Sync every 6 hours
SYNC_SCHEDULE=0 */6 * * *

# Sync daily at 9 AM
SYNC_SCHEDULE=0 9 * * *

# Timezone
TIMEZONE=UTC
```

See [docker/DOCKER.md](docker/DOCKER.md) for detailed Docker usage instructions.

## How It Works

### Book Matching
1. **Find your book** in Hardcover using ISBN
2. **Pick the best edition** (one with page count)
3. **Convert progress** from percentage to pages

### Progress Conversion
```
pages = (percentage / 100) × total_pages
```
Example: 71.5% of a 496-page book = page 354

### Progress Threshold
The tool uses a minimum progress threshold to keep your "Currently Reading" list clean:

- **Above threshold** (default: 5%): Added to "Currently Reading" + progress synced
- **Below threshold**: Added to "Want to Read" + progress synced
- **0% progress**: Added to "Want to Read" + no progress sync (avoids API errors)

**Smart Status Management:**
- Books automatically move from "Want to Read" to "Currently Reading" when they cross the threshold
- Books automatically move from "Currently Reading" to "Want to Read" when they drop below the threshold
- This keeps your active reading list focused while ensuring all started books are tracked

### Smart Features
- **Progress Threshold**: Only adds books to "Currently Reading" if you've made meaningful progress (default: 5%)
- **Auto-complete**: Books 95%+ done are marked "Read"
- **Cache**: Remembers your book editions for faster syncing
- **Progress bars**: Shows you what's happening

### Cache System

The tool remembers which book editions you use to sync faster:

- **Automatic**: Saves your choices automatically
- **Persistent**: Remembers between runs
- **Manageable**: View stats or clear via menu

**Managing Cache:**
```bash
python src/main.py --interactive
# Then select "Cache management"
```

## Development

### For Contributors

The project uses automated workflows for code quality:

- **CI/CD**: Tests code on Python 3.11 & 3.12
- **Security**: Scans for vulnerabilities weekly
- **Code Quality**: Checks formatting and types

### Local Setup
```bash
# Install dev tools
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
isort .
```

## Example Output

```bash
$ python src/main.py sync

🔍 Testing connections...
✅ All connections successful!

📚 Syncing your progress...
Syncing Project Hail Mary: 71.5% → page 354/496
✅ Synced: Project Hail Mary

📊 Summary: 2 books synced, 0 completed, 9 skipped
⏱️  Duration: 5.6s
```

## Troubleshooting

### Common Issues

**"No ISBN found":**
- Some audiobooks don't have ISBN data
- These books are skipped automatically

**"Failed to update progress":**
- Check your Hardcover API token
- Make sure the book exists in your library

**Connection errors:**
- Check your server URLs and tokens
- Try `python src/main.py test` to verify

### Getting Help

Run with verbose logging:
```bash
python src/main.py sync --verbose
```

Check logs in `abs_hardcover_sync.log` for details.

## Security

- Your API tokens are stored locally in `secrets.env`
- No data is sent to third parties
- All connections use HTTPS

## GitHub Actions Workflows

This project uses automated workflows to ensure code quality and security:

### CI/CD Pipeline
- **Runs on**: Every push and pull request
- **Tests**: Python 3.11 & 3.12 compatibility
- **Checks**: Code formatting, linting, and type checking
- **Coverage**: Generates test coverage reports

### Security Scanning
- **Runs on**: Every push, pull request, and weekly
- **Scans**: Code for security vulnerabilities
- **Checks**: Dependencies for known issues
- **Validates**: No hardcoded secrets or exposed credentials

### Container Registry
- **Runs on**: Every push to main and version tags
- **Builds**: Docker images automatically
- **Publishes**: To GitHub Container Registry (ghcr.io)
- **Tags**: Latest, version tags, and commit SHAs
- **Available**: `ghcr.io/rohit-purandare/audiobookshelf-hardcover-sync`

### Status Badges
You can see the workflow status in the repository:
- ✅ **CI/CD**: Ensures code quality
- 🔒 **Security**: Monitors for vulnerabilities
- 📊 **Coverage**: Tracks test coverage
- 🐳 **Container**: Builds and publishes Docker images

## License

Open source. See LICENSE file for details.
