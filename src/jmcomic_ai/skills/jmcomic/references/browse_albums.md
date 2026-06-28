# `browse_albums` Reference

Full sorting options and use-case recipes for `browse_albums`. The SKILL.md summary points
here; this file carries the enumerations and worked examples (which also mirror the tool docstring).

## Overview

**`browse_albums`** is the unified tool for browsing albums by category, time range, and sorting
criteria. It combines the functionality of ranking and category browsing into a single, flexible
interface.

The response **does NOT include detailed statistical data** (likes, views, author, etc.). Each
album in the list contains only:
- `id`: Album ID
- `title`: Album title
- `tags`: Tag list
- `cover_url`: Cover image URL

To get detailed information including likes/views/author for albums, you must call
**`get_album_detail(album_id)`** for each album individually.

## Supported Sorting Options (`order_by`)

- `latest`: Latest updates (default)
- `likes`: Most liked
- `views`: Most viewed
- `pictures`: Most pictures
- `score`: Highest rated
- `comments`: Most comments

## Common Use Cases

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

## Example: Top 10 Albums with Details

```python
# 1. Get ranking list (sorted by likes, but no likes data in response)
ranking = browse_albums(time_range="month", order_by="likes", page=1)

# 2. Get detailed info for top 10
for album in ranking["albums"][:10]:
    detail = get_album_detail(album["id"])
    # Now you have: detail["likes"], detail["views"], detail["author"], etc.
```
