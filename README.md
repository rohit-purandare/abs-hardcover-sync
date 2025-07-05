# Audiobookshelf to Hardcover Sync Tool

A simple Python CLI tool that syncs your audiobook listening progress from [Audiobookshelf](https://www.audiobookshelf.org/) to reading progress in [Hardcover](https://hardcover.app/).

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

## Requirements

- Python 3.11 or newer
- Audiobookshelf server (with API access)
- Hardcover account (with API token)
- Internet connection

## Installation

1. **Download the code**
   ```bash
   git clone https://github.com/rohit-purandare/abs-hardcover-sync.git
   cd abs-hardcover-sync
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   ```

## Setup

### 1. Get Your API Tokens

**Audiobookshelf:**
- Go to your Audiobookshelf web interface
- Settings → Users & Sessions → API Tokens
- Create a new token

**Hardcover:**
- Visit [hardcover.app/account/api](https://hardcover.app/account/api)
- Copy your API token

### 2. Create Config File
```bash
cp secrets.env.example secrets.env
```

### 3. Add Your Tokens
Edit `secrets.env`:
```bash
# Your Audiobookshelf server
AUDIOBOOKSHELF_URL=https://your-audiobookshelf-server.com
AUDIOBOOKSHELF_TOKEN=your_audiobookshelf_api_token

# Your Hardcover token
HARDCOVER_TOKEN=your_hardcover_api_token
```

### 4. Test Your Setup
```bash
python main.py config
```

## Usage

### Quick Start
```bash
# Run with interactive menu (default)
python main.py

# Test your connections
python main.py test

# Sync your progress
python main.py sync

# See what would be synced (no changes)
python main.py sync --dry-run
```

### Interactive Mode
```bash
# Run with menu (this is the default)
python main.py --interactive

# Force non-interactive mode
python main.py sync --no-interactive
```

### All Commands
```bash
python main.py sync      # Sync your progress
python main.py test      # Test connections
python main.py config    # Show your setup
python main.py --help    # Show all options
```

### Auto-Sync (Optional)
Set up automatic syncing with cron:
```bash
# Edit your crontab
crontab -e

# Sync every 6 hours
0 */6 * * * cd /path/to/sync-tool && python main.py sync
```

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

### Smart Features
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
python main.py --interactive
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
$ python main.py sync

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
- Try `python main.py test` to verify

### Getting Help

Run with verbose logging:
```bash
python main.py sync --verbose
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

### Status Badges
You can see the workflow status in the repository:
- ✅ **CI/CD**: Ensures code quality
- 🔒 **Security**: Monitors for vulnerabilities
- 📊 **Coverage**: Tracks test coverage

## License

Open source. See LICENSE file for details.
