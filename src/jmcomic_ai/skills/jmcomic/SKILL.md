---
name: jmcomic
description: Search, browse, and download manga from JMComic (18comic). Use for manga discovery, ranking, downloads, and configuration management.
license: MIT
metadata:
  version: "0.0.9"
  dependencies: python>=3.10
---

# JMComic Skill

This skill enables you to interact with JMComic (18comic), a popular manga platform, to search, browse, and download manga content.

## When to Use This Skill

Activate this skill when the user wants to:
- Search for manga by keyword or category
- Browse popular manga rankings (daily, weekly, monthly)
- Download entire albums or specific chapters (**Returns structured dict with status, paths, and metadata**)
- Get detailed information about a manga album
- Configure download settings (paths, concurrency, proxies)
- **NEW**: Post-process downloaded content (Zip, PDF, LongImage) with **native parameters or `dir_rule`**

### 📥 Download Tools Return Structured Data

Both `download_album` and `download_photo` now return structured dictionaries:

**`download_album(album_id: str, ctx: Context = None)`** returns:
```python
{
    "status": "success" | "failed",
    "album_id": str,
    "title": str,
    "download_path": str,  # Absolute path to download directory
    "error": str | None
}
```

**`download_photo(photo_id: str, ctx: Context = None)`** returns:
```python
{
    "status": "success" | "failed",
    "photo_id": str,
    "image_count": int,
    "download_path": str,  # Absolute path to download directory
    "error": str | None
}
```

**Real-time Progress Tracking**: Both methods accept an optional `ctx: Context` parameter (automatically injected by FastMCP). When provided, progress updates are sent via MCP notifications in real-time, allowing AI agents to monitor download progress.

## Core Capabilities

### 🛠️ Post-Processing (New in 0.0.6)

This skill supports advanced post-processing of downloaded manga. It returns structured data including the **output path** of the generated file.

- **📦 Zip Compression**: Pack an entire album or individual chapters into a ZIP file.
- **📄 PDF Conversion**: Merge all images of an album into a single PDF document.
- **🖼️ Long Image Merging**: Combine all pages of a chapter into one continuous long image.

**`post_process(album_id: str, process_type: str, params: dict = None)`** returns:
```python
{
    "status": "success" | "error",
    "process_type": str,  # Process type used
    "album_id": str,  # Album ID processed
    "output_path": str,  # Absolute path to generated file/directory (empty string on error)
    "is_directory": bool,  # True if output is a directory (e.g., photo-level zip), False on error
    "message": str  # Success/error message
}
```

**All fields are always present**. On error, `output_path` will be an empty string and `is_directory` will be `False`.

**Output Control**: Use `dir_rule` for custom output paths. If omitted, files are saved in the configured default directory.

### 🧩 Post-Process `dir_rule` Examples

The `dir_rule` parameter takes a dictionary: `{"rule": "DSL_STRING", "base_dir": "BASE_PATH"}`. 
- **`Bd`**: Refers to `base_dir`.
- **`Axxx`**: Album attributes (e.g., `Aid`, `Atitle`, `Aauthor`).
- **`Pxxx`**: Photo/Chapter attributes (e.g., `Pid`, `Ptitle`, `Pindex`).
- **`{attr}`**: Python string format support for any metadata attribute.

#### 1. ZIP Compression (`process_type="zip"`)
*   **Album Level (Single ZIP for entire manga)**:
    `{"level": "album", "dir_rule": {"rule": "Bd/{Atitle}.zip", "base_dir": "D:/Comics/Archives"}}`
*   **Photo Level (Individual ZIP for each chapter)**:
    `{"level": "photo", "dir_rule": {"rule": "Bd/{Atitle}/{Pindex}.zip", "base_dir": "D:/Comics/Exports"}}`

#### 2. PDF Conversion (`process_type="img2pdf"`)
*   **Album Level (One PDF for all chapters combined)**:
    `{"level": "album", "dir_rule": {"rule": "Bd/{Aauthor}-{Atitle}.pdf", "base_dir": "D:/Comics/PDFs"}}`
*   **Photo Level (One PDF per chapter)**:
    `{"level": "photo", "dir_rule": {"rule": "Bd/{Atitle}/{Pindex}.pdf", "base_dir": "D:/Comics/Chapters"}}`

#### 3. Long Image Merging (`process_type="long_img"`)
*   **Album Level (All pages combined into one huge image)**:
    `{"level": "album", "dir_rule": {"rule": "Bd/{Atitle}_Full.png", "base_dir": "D:/Comics/Long"}}`
*   **Photo Level (One long image per chapter)**:
    `{"level": "photo", "dir_rule": {"rule": "Bd/{Atitle}/{Pindex}.png", "base_dir": "D:/Comics/Long"}}`

> ⚠️ **Best Practice - Avoiding Overwrites**: 
> When processing multiple different albums (e.g., in a loop) into the same `base_dir`, ALWAYS include unique identifiers like `{Aid}` or `{Atitle}` in your `rule`. Using a static rule like `"Bd/output.pdf"` will cause subsequent albums to overwrite previous ones.

**Workflow Suggestion**: Use `download_album` first to ensure source images exist, then call `post_process`. The tool returns the **actual predicted path** of the result.
 
This skill provides command-line utilities for JMComic operations. All tools are Python scripts located in the `scripts/` directory and should be executed using Python.
 
### Data Structure Notes

Most search and browsing tools (e.g., `search_album`, `browse_albums`) return a consistent structure that supports pagination:

```json
{
  "albums": [ ... ],
  "total_count": 1234
}
```

**`total_count`** provides the total number of items available across all pages, allowing you to calculate the number of remaining pages and decide if further searching is needed.

#### Important: Browse Albums Data Limitations

**`browse_albums`** is the unified tool for browsing albums by category, time range, and sorting criteria. It combines the functionality of ranking and category browsing into a single, flexible interface.

The response **does NOT include detailed statistical data** (likes, views, author, etc.). Each album in the list contains only:
- `id`: Album ID
- `title`: Album title
- `tags`: Tag list
- `cover_url`: Cover image URL

To get detailed information including likes/views/author for albums, you must call **`get_album_detail(album_id)`** for each album individually.

**Supported Sorting Options (`order_by`):**
- `latest`: Latest updates (default)
- `likes`: Most liked
- `views`: Most viewed
- `pictures`: Most pictures
- `score`: Highest rated
- `comments`: Most comments

**Common Use Cases:**

1. **Rankings (day/week/month)**: Set `time_range` + `order_by`
   ```python
   # Monthly top liked albums
   browse_albums(time_range="month", order_by="likes")
   
   # Weekly most viewed albums
   browse_albums(time_range="week", order_by="views")
   
   # Today's trending albums
   browse_albums(time_range="today", order_by="views")
   ```

2. **Category Browsing**: Set `category` + `order_by`
   ```python
   # Browse doujin manga (latest)
   browse_albums(category="doujin", order_by="latest")
   
   # Browse Korean comics (latest)
   browse_albums(category="hanman", order_by="latest")
   ```

3. **Combined Queries**: Set `category` + `time_range` + `order_by`
   ```python
   # This month's hottest doujin manga
   browse_albums(category="doujin", time_range="month", order_by="views")
   
   # This week's most liked Korean comics
   browse_albums(category="hanman", time_range="week", order_by="likes")
   ```

**Example workflow for getting top 10 albums with details:**
```python
# 1. Get ranking list (sorted by likes, but no likes data in response)
ranking = browse_albums(time_range="month", order_by="likes", page=1)

# 2. Get detailed info for top 10
for album in ranking["albums"][:10]:
    detail = get_album_detail(album["id"])
    # Now you have: detail["likes"], detail["views"], detail["author"], etc.
```


## Configuration Reference


For detailed configuration options, refer to:
- **`references/reference.md`**: Human-readable configuration guide
- **`assets/option_schema.json`**: JSON Schema for validation

Common configuration examples:

```yaml
# Change download directory
dir_rule:
  base_dir: "/path/to/downloads"
  rule: "Bd / Ptitle"

# Adjust concurrency
download:
  threading:
    image: 30  # Max concurrent image downloads
    photo: 5   # Max concurrent chapter downloads

# Set proxy
client:
  postman:
    meta_data:
      proxies:
        http: "http://proxy.example.com:8080"
        https: "https://proxy.example.com:8080"

# Or use system proxy
client:
  postman:
    meta_data:
      proxies: system

# Configure login cookies
client:
  postman:
    meta_data:
      cookies:
        AVS: "your_avs_cookie_value"

# Use plugins
plugins:
  after_album:
    - plugin: zip
      kwargs:
        level: photo
        suffix: zip
        delete_original_file: true
```

## Available Command-Line Tools

The `scripts/` directory provides utility tools for common tasks. All tools support the `--help` flag for detailed usage information.

### 🏥 `doctor.py` - Environment Diagnostics

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

### 📦 `batch_download.py` - Batch Album Downloads

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
- ✅ Download multiple albums in sequence
- ✅ Progress tracking with success/failure counts
- ✅ Error handling and summary report

### 📷 `download_photo.py` - Batch Chapter Downloads

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

### ✅ `validate_config.py` - Configuration Validation

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

### 🔍 `search_export.py` - Search and Export

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

### 📖 `album_info.py` - Album Information Query

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

### 🖼️ `download_covers.py` - Batch Cover Downloads

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

### 📊 `ranking_tracker.py` - Ranking Tracker

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

### 🛠️ `post_process.py` - Post-Processing (Zip, PDF, LongImg)

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

## Script Parameters ↔ MCP Tools Mapping

The following table clarifies how script CLI parameters map to MCP tools.

| Script | Target Tool | Mapping Level | Notes |
| :--- | :--- | :--- | :--- |
| `search_export.py` | `search_album` / `browse_albums` | Partial | `--keyword` maps to `search_album`; `--ranking` / `--category` maps to `browse_albums`. Ranking is a convenience mode based on `time_range` + configurable sort, not a separate backend API. |
| `post_process.py` | `post_process` | High | `--id`→`album_id`, `--type`→`process_type`, optional flags to `params`. `--dir-rule` + `--base-dir` map to `params.dir_rule`. |
| `album_info.py` | `get_album_detail` | Partial | Batch wrapper over repeated single-album calls; output format is script-defined. |
| `download_covers.py` | `download_cover` | Partial | Batch wrapper over repeated cover calls. |
| `ranking_tracker.py` | `browse_albums` | Partial | Uses time-range/category browse semantics and exports snapshots. |
| `batch_download.py` | (non-MCP direct download flow) | None | Designed for installable skill runtime; does not guarantee MCP tool return shape/progress contract. |
| `download_photo.py` | `download_photo` (conceptual) | Partial | Script behavior focuses on batch orchestration and CLI outputs. |
| `validate_config.py` | `update_option` (adjacent) | None | Validation/format conversion utility; not a direct MCP tool wrapper. |

### Mapping Policy

- **MCP tools are the source of truth** for agent-facing contracts (name, args, return structure).
- **Scripts are operational helpers** for local/installed skill workflows and may expose different output formatting.
- If strict schema guarantees are required, prefer calling MCP tools directly instead of scripts.

## Important Notes

- **Legal Compliance**: Ensure you have the right to download content
- **Rate Limiting**: The platform may rate-limit requests; adjust threading if needed
- **Storage**: Downloads can be large; ensure sufficient disk space
- **Configuration**: Default config is at `~/.jmcomic/option.yml`

## Troubleshooting

- **Connection errors**: Try updating the domain list in client config
- **Slow downloads**: Reduce threading concurrency
- **Scrambled images**: Ensure `download.image.decode` is set to `true`
