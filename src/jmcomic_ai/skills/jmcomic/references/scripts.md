# Command-Line Tools Reference

Full usage details for the utility scripts in the `scripts/` directory. The SKILL.md "Available
Command-Line Tools" section summarizes these; this file carries the complete examples and feature
lists. All tools support the `--help` flag for detailed usage information.

> **Prerequisite**: Most scripts import `jmcomic_ai`, so they must run in an environment where the
> `jmcomic-ai` package is installed (e.g. `pip install jmcomic-ai`, or `uv run python scripts/<name>.py`
> from a synced checkout). If `jmai` was installed into an isolated venv via `uv tool`/`pipx`, invoke
> the scripts with that same interpreter, or just use the MCP tools instead.

The APK helper remains a `jmcomic-ai` script. Local reading is different: run upstream `jms --help`
first, then invoke `jms` directly as described in `references/ecosystem.md`; there is no
`jmcomic-ai` reader wrapper.

Output file paths follow the current working directory. Export scripts automatically create missing
parent directories before writing. Commands that finish with any failed item return a non-zero process
exit code, so shell scripts and agents can reliably distinguish complete success from partial failure.

## 📱 `download_latest_apk.py` - Latest Android APK

Download the single `.apk` asset from the latest public `hect0x7/JMComic-APK` GitHub Release:

```bash
# Download to the current directory
python scripts/download_latest_apk.py

# Select an output directory and return machine-readable JSON
python scripts/download_latest_apk.py /path/to/output --json

# Replace an existing APK with the same filename
python scripts/download_latest_apk.py /path/to/output --force
```

**Parameters**:

| Parameter | Description |
| :--- | :--- |
| `output_dir` | Optional download directory; defaults to the current directory. |
| `--force` | Replace an existing APK with the same filename. |
| `--json` | Print a machine-readable JSON result. |

The script creates the output directory when needed, downloads atomically, validates the published
size and SHA-256 digest when available, and reports the release metadata plus absolute local path.
Run `python scripts/download_latest_apk.py --help` for the current parameters.

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
- ✅ Print each download's dedicated task log path on success or failure

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
- ✅ Print each download's dedicated task log path on success or failure

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
- ✅ Export to CSV or JSON format (JSON uses the documented `{albums, total_count}` shape)
- ✅ Cross-page de-duplication by album id, with `total_count` propagated to the export
- ✅ `--tags` keeps only albums carrying every given tag (exact, case-insensitive match)
- ✅ `--enrich` fills per-album stats (likes/views/pictures/author) via `get_album_detail`
- ✅ CSV columns include every field returned across the fetched result set
- ✅ Create missing parent directories for output files
- ✅ Useful for building album catalogs and collections

```bash
# Keep only albums that carry every given tag (exact match)
python scripts/search_export.py --keyword "搜索词" --tags "tag-a,tag-b" --output filtered.csv

# Enrich each album with likes / views / pictures / author (one extra request per album)
python scripts/search_export.py --keyword "搜索词" --enrich --output enriched.json
```

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
- ✅ Create missing parent directories for JSON output
- ✅ Error tracking for failed queries

## 💬 `album_comments.py` - Album Comments Query

Fetch one page of album comments as structured JSON:

```bash
# First comment page (print JSON to console)
python scripts/album_comments.py --id 302820

# Select another page
python scripts/album_comments.py --id 302820 --page 2

# Export the MCP-compatible response to a JSON file
python scripts/album_comments.py --id 302820 --output comments.json
```

**Features**:
- ✅ Includes recursive nested replies
- ✅ Preserves `is_spoiler` for content filtering
- ✅ Includes `total`, `page_count`, `page_size`, and current-page `comment_count`
- ✅ Read-only; does not post comments or replies

## 🌐 `forum_comments.py` - Site-Wide Comments Query

Fetch one page of the latest site-wide comments as structured JSON:

```bash
# First page (print JSON to console)
python scripts/forum_comments.py

# Select another page and export it
python scripts/forum_comments.py --page 2 --output forum-comments.json
```

Each comment includes its source `album_id`. The HTML client does not expose global `total` or
`page_count`, so those fields may be `null`; the API client provides them when available. This tool
is read-only and does not post comments or replies.

## Favorites

These scripts require valid authentication in `option.yml` (configured cookies or a login plugin).
They do not inherit login state from a separate MCP session. All four support `--option` and print
JSON results. The folder and album browsing scripts also accept `--output` to export their query
results, creating missing parent directories. Service or export failures exit non-zero, as do
structured error results.

### `favorite_folders.py` - Favorite Folder Directory

```bash
python scripts/favorite_folders.py
python scripts/favorite_folders.py --username YOUR_USERNAME --output folders.json
```

Returns `{"folders": [{"id": "123", "name": "My folder"}]}`. For HTML clients authenticated only
by Cookie, `--username` is required; API clients ignore it and query the logged-in account.
The folder directory may be empty, and the special all-favorites ID `"0"` may be absent.

### `favorite_albums.py` - Browse Favorites

```bash
# Browse all favorites
python scripts/favorite_albums.py

# Browse one folder with a Cookie-authenticated HTML client
python scripts/favorite_albums.py --folder-id 123 --page 2 --order-by favorite_time --username YOUR_USERNAME --output favorites.json
```

| Parameter | Tool argument | Default |
| :--- | :--- | :--- |
| `--folder-id` | `folder_id` | `"0"` (all favorites) |
| `--page` | `page` | `1` |
| `--order-by` | `order_by` | `favorite_time` |
| `--username` | `username` | Empty; required for HTML Cookie-only queries |

Returns `albums`, `total_count`, `page`, and `folder_id`, preserving the MCP response. Sorting accepts
`favorite_time` and `update_time`. Invalid page, folder, or sort parameters produce an
`error` field and exit code 1. An empty collection is a successful result.

### `add_favorite_album.py` - Add a Favorite

```bash
python scripts/add_favorite_album.py --id 123456
python scripts/add_favorite_album.py --id JM123456 --option /path/to/option.yml
```

`--id` maps to `album_id` and accepts a numeric ID, JM-prefixed ID, or album URL. The script saves the
album to the account's default favorites placement and prints `status`, `album_id`, `title`, and
`message` as JSON to stdout. An album that is already saved returns `status="error"` and stays unchanged;
`status="error"` exits with code 1.

### `delete_favorite_album.py` - Delete a Favorite

```bash
python scripts/delete_favorite_album.py --id 123456
python scripts/delete_favorite_album.py --id JM123456 --option /path/to/option.yml
```

`--id` maps to `album_id` and accepts a numeric ID, JM-prefixed ID, or album URL. The script removes
the album from the account's favorites and prints `status`, `album_id`, `title`, and `message` as JSON
to stdout. An album that is not saved returns `status="error"` and stays unchanged; `status="error"` exits
with code 1.

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
- ✅ CSV columns include every field returned across the fetched result set
- ✅ Create missing parent directories for output files
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
- ✅ `--outdir` writes into the given directory using a type-aware filename rule (`Bd/{name}.{ext}`) instead of resolving to the directory itself
- ✅ Custom output directories
- ✅ Missing optional dependencies (img2pdf / Pillow) are pre-checked and auto-installed; `--no-install-deps` opts out
