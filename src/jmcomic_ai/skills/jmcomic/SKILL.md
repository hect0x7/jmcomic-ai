---
name: JMComic
description: Search, browse, and download manga from JMComic (18comic). Use for manga discovery, ranking, downloads, and configuration management.
dependencies: python>=3.8, jmcomic>=2.0
---

# JMComic Skill

This skill enables you to interact with JMComic (18comic), a popular manga platform, to search, browse, and download manga content.

## When to Use This Skill

Activate this skill when the user wants to:
- Search for manga by keyword or category
- Browse popular manga rankings (daily, weekly, monthly)
- Download entire albums or specific chapters
- Get detailed information about a manga album
- Configure download settings (paths, concurrency, proxies)

## Core Capabilities

### 1. Search & Discovery
- **Search by keyword**: Find manga matching specific search terms
- **Browse by category**: Explore manga by genre (同人, 韓漫, 單本, etc.)
- **View rankings**: See what's trending (day/week/month)

### 2. Album Information
- **Get album details**: Retrieve metadata including title, author, likes, views, category
- **List chapters**: View all available chapters for an album

### 3. Download Management
- **Download albums**: Download entire manga albums (all chapters)
- **Download chapters**: Download specific chapters (photos)
- **Download covers**: Save album cover images

### 4. Configuration
- **Update settings**: Modify download paths, threading, proxies, and more
- **View current config**: Check active configuration settings

## Available Tools

When this skill is active, you have access to these MCP tools:

- `search_album(keyword, page=1, main_tag=0, order_by="latest", time_range="all", category="all")` - Advanced search
- `get_ranking(period="day", page=1)` - Get rankings (day/week/month)
- `get_album_detail(album_id)` - Get detailed album information
- `get_category_list(category="0", page=1, sort_by="mr")` - Browse by category
- `download_album(album_id)` - Download entire album (async)
- `download_photo(photo_id)` - Download specific chapter
- `download_cover(album_id)` - Download album cover
- `update_option(option_updates)` - Update configuration
- `login(username, password)` - Authenticate user

## Configuration Reference

For detailed configuration options, refer to:
- **`resources/reference.md`**: Human-readable configuration guide
- **`option_schema.json`**: JSON Schema for validation

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

## Example Usage

See `scripts/usage_example.py` for code examples.

**Typical workflow**:
1. Search for manga: `search_album("keyword")`
2. Get details: `get_album_detail(album_id)`
3. Download: `download_album(album_id)`

## Important Notes

- **Legal Compliance**: Ensure you have the right to download content
- **Rate Limiting**: The platform may rate-limit requests; adjust threading if needed
- **Storage**: Downloads can be large; ensure sufficient disk space
- **Configuration**: Default config is at `~/.jmcomic/option.yml`

## Troubleshooting

- **Connection errors**: Try updating the domain list in client config
- **Slow downloads**: Reduce threading concurrency
- **Scrambled images**: Ensure `download.image.decode` is set to `true`
