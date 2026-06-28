# Command-Line Tools Reference

Full usage details for the utility scripts in the `scripts/` directory. The SKILL.md "Available
Command-Line Tools" section summarizes these; this file carries the complete examples and feature
lists. All tools support the `--help` flag for detailed usage information.

> **Prerequisite**: These scripts import `jmcomic_ai`, so they must run in an environment where the
> `jmcomic-ai` package is installed (e.g. `pip install jmcomic-ai`, or `uv run python scripts/<name>.py`
> from a synced checkout). If `jmai` was installed into an isolated venv via `uv tool`/`pipx`, invoke
> the scripts with that same interpreter, or just use the MCP tools instead.

## 🏥 `doctor.py` - Environment Diagnostics

Comprehensive diagnostic tool that checks your entire setup:

```bash
python scripts/doctor.py
```

**What it checks**:
- ✅ Python version compatibility
- ✅ Required dependencies (jmcomic, jmcomic_ai)
- ✅ Configuration file status
- ✅ Network connectivity (discovers and tests available JMComic domains)

**Use this when**:
- Setting up the skill for the first time
- Troubleshooting any issues
- Verifying your environment is ready

## 📦 `batch_download.py` - Batch Album Downloads

Download multiple albums from a list of IDs:

```bash
# From command line
python scripts/batch_download.py --ids 123456,789012,345678

# From file (one ID per line)
python scripts/batch_download.py --file album_ids.txt

# With custom config
python scripts/batch_download.py --ids 123456,789012 --option /path/to/option.yml
```

**Features**:
- ✅ Download multiple albums concurrently
- ✅ Progress tracking with success/failure counts
- ✅ Error handling and summary report

## 📷 `download_photo.py` - Batch Chapter Downloads

Download specific chapters/photos from albums:

```bash
# Download specific chapters
python scripts/download_photo.py --ids 123456,789012,345678

# Download chapters from file
python scripts/download_photo.py --file photo_ids.txt

# With custom config
python scripts/download_photo.py --ids 123456,789012 --option /path/to/option.yml
```

**Features**:
- ✅ Download specific chapters without downloading entire albums
- ✅ Useful for selective chapter downloads
- ✅ Progress tracking and error handling

## ✅ `validate_config.py` - Configuration Validation

Validate and convert configuration files:

```bash
# Validate configuration
python scripts/validate_config.py ~/.jmcomic/option.yml

# Convert YAML to JSON
python scripts/validate_config.py option.yml --convert-to-json

# Specify output path
python scripts/validate_config.py option.yml --convert-to-json --output config.json
```

**Features**:
- ✅ Validate option.yml syntax and structure
- ✅ Display configuration summary (client, download, directory, proxy settings)
- ✅ Convert between YAML and JSON formats

## 🔍 `search_export.py` - Search and Export

Search albums and export results to CSV or JSON:

```bash
# Search by keyword
python scripts/search_export.py --keyword "搜索词" --output results.csv

# Get daily ranking
python scripts/search_export.py --ranking day --output ranking.json

# Browse category
python scripts/search_export.py --category doujin --output doujin.csv --max-pages 3
```

**Features**:
- ✅ Search by keyword, ranking, or category
- ✅ Multi-page support with `--max-pages`
- ✅ Export to CSV or JSON format
- ✅ Useful for building album catalogs and collections

## 📖 `album_info.py` - Album Information Query

Fetch detailed information for one or multiple albums:

```bash
# Single album (print to console)
python scripts/album_info.py --id 123456

# Multiple albums (export to JSON)
python scripts/album_info.py --ids 123456,789012,345678 --output details.json

# From file
python scripts/album_info.py --file album_ids.txt --output album_details.json --verbose
```

**Features**:
- ✅ Query single or multiple albums
- ✅ Display detailed metadata (title, author, likes, views, chapters, tags, description)
- ✅ Export to JSON or print formatted summary to console
- ✅ Error tracking for failed queries

## 🖼️ `download_covers.py` - Batch Cover Downloads

Download cover images for multiple albums:

```bash
# Download covers for specific albums
python scripts/download_covers.py --ids 123456,789012,345678

# Download covers from file
python scripts/download_covers.py --file album_ids.txt --output ./my_covers
```

**Features**:
- ✅ Batch download album covers
- ✅ Custom output directory
- ✅ Fast preview without downloading full albums
- ✅ Useful for creating cover galleries

## 📊 `ranking_tracker.py` - Ranking Tracker

Track and export ranking changes over time:

```bash
# Get current daily ranking
python scripts/ranking_tracker.py --period day --output daily_ranking.json

# Get multiple pages of weekly ranking
python scripts/ranking_tracker.py --period week --max-pages 3 --output weekly_top.csv

# Track all periods (day, week, month)
python scripts/ranking_tracker.py --all --output rankings/

# Add timestamp to filename
python scripts/ranking_tracker.py --period day --output ranking.json --add-timestamp
```

**Features**:
- ✅ Track daily, weekly, or monthly rankings
- ✅ Multi-page support
- ✅ Export to CSV or JSON with timestamps
- ✅ Track all periods at once with `--all`
- ✅ Useful for trend analysis and discovering popular content

## 🛠️ `post_process.py` - Post-Processing (Zip, PDF, LongImg)

Transform downloaded images into ZIP, PDF, or Long Images:

```bash
# Convert album to PDF
python scripts/post_process.py --id 123456 --type img2pdf

# Pack album into encrypted ZIP and delete original images
python scripts/post_process.py --id 123456 --type zip --password "my_secret" --delete

# Merge images into a long scroll image
python scripts/post_process.py --id 123456 --type long_img --outdir ./long_images

# Use native dir_rule DSL (recommended for precise output paths)
python scripts/post_process.py --id 123456 --type zip --dir-rule "Bd/{Atitle}/{Pindex}.zip" --base-dir "D:/Comics/Exports"
```

**Features**:
- ✅ Supports ZIP, PDF, and Long Image formats
- ✅ Option to encrypt output (Zip/PDF)
- ✅ Automatic cleanup of original files
- ✅ Custom output directories
