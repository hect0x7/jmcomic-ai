---
name: jmcomic
description: Search, browse, and download manga from JMComic (18comic). Use for manga discovery, ranking, downloads, and configuration management.
license: MIT
metadata:
  version: "0.0.10"
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

**Output Control**: Use `dir_rule` (a `{"rule": "DSL_STRING", "base_dir": "BASE_PATH"}` dict) for custom output paths. If omitted, files are saved in the configured default directory. The DSL supports `Bd` (base_dir), `Axxx`/`Pxxx` album/photo attributes, and `{attr}` Python format placeholders. When looping over albums into one `base_dir`, include `{Aid}` or `{Atitle}` to avoid overwrites.

For the full set of ZIP/PDF/LongImg × album/photo `dir_rule` examples, see `references/post_process.md`.

This skill provides command-line utilities for JMComic operations. All utilities are Python scripts located in the `scripts/` directory and should be executed using Python.
 
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

**`browse_albums`** is the unified tool for browsing albums by `category`, `time_range`, and `order_by` (ranking + category browsing in one interface). Its response is lightweight — each album has only `id`, `title`, `tags`, and `cover_url`, and **no** stats (likes/views/author). To get those, call **`get_album_detail(album_id)`** per album.

`order_by` accepts: `latest` (default), `likes`, `views`, `pictures`, `score`, `comments`. For the full enumeration, use-case recipes (rankings, category browsing, combined queries), and the "top 10 with details" workflow, see `references/browse_albums.md`.


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

The `scripts/` directory provides utility tools for common tasks. All tools support the `--help` flag for detailed usage. The table below summarizes each script; for full per-script examples and feature lists, see `references/scripts.md`.

| Script | Purpose |
| :--- | :--- |
| `doctor.py` | Environment diagnostics: Python version, deps, config status, network/domain checks. |
| `batch_download.py` | Download multiple albums from a list of IDs (CLI or file) with progress/error summary. |
| `download_photo.py` | Download specific chapters/photos without fetching whole albums. |
| `validate_config.py` | Validate `option.yml` and convert between YAML and JSON. |
| `search_export.py` | Search by keyword/ranking/category and export to CSV or JSON (multi-page). |
| `album_info.py` | Query detailed metadata for one or many albums; print or export to JSON. |
| `download_covers.py` | Batch download album cover images to a custom output directory. |
| `ranking_tracker.py` | Track day/week/month rankings over time; export snapshots with timestamps. |
| `post_process.py` | Convert downloads to ZIP/PDF/LongImg, with optional encryption and `dir_rule` DSL. |

## Script Parameters ↔ MCP Tools Mapping

The following table clarifies how script CLI parameters map to MCP tools.

| Script | Target Tool | Mapping Level | Notes |
| :--- | :--- | :--- | :--- |
| `search_export.py` | `search_album` / `browse_albums` | Partial | `--keyword` maps to `search_album`; `--ranking` / `--category` maps to `browse_albums`. Ranking is a convenience mode based on `time_range` + configurable sort, not a separate backend API. |
| `post_process.py` | `post_process` | High | `--id`→`album_id`, `--type`→`process_type`, optional flags to `params`. `--dir-rule` + `--base-dir` map to `params.dir_rule`. |
| `album_info.py` | `get_album_detail` | Partial | Batch wrapper over repeated single-album calls; output format is script-defined. |
| `download_covers.py` | `download_cover` | Partial | Batch wrapper over repeated cover calls. |
| `ranking_tracker.py` | `browse_albums` | Partial | Uses time-range/category browse semantics and exports snapshots. |
| `batch_download.py` | (non-MCP direct download flow) | None | Designed for installed package runtime; does not guarantee MCP tool return shape/progress contract. |
| `download_photo.py` | `download_photo` (conceptual) | Partial | Script behavior focuses on batch orchestration and CLI outputs. |
| `validate_config.py` | `update_option` (adjacent) | None | Validation/format conversion utility; not a direct MCP tool wrapper. |

### Mapping Policy

- **MCP tools are the source of truth** for agent-facing contracts (name, args, return structure).
- **Scripts are operational helpers** for local package workflows and may expose different output formatting.
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
