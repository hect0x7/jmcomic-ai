#!/usr/bin/env python3
"""
Search and export tool for JMComic.
Search albums and export results to CSV or JSON format.

Usage:
    # Search by keyword
    python scripts/search_export.py --keyword "搜索词" --output results.csv

    # Get daily ranking
    python scripts/search_export.py --ranking day --output ranking.json

    # Browse category
    python scripts/search_export.py --category doujin --output doujin.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic_ai", "Please ensure the package is installed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Search and export JMComic albums")

    # Search mode selection (mutually exclusive)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--keyword", type=str, help="Search by keyword")
    mode.add_argument("--ranking", type=str, choices=["day", "week", "month"], help="Get ranking")
    mode.add_argument("--category", type=str, help="Browse by category (e.g., doujin, hanman, single)")

    # Common options
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum pages to fetch (default: 1)")
    parser.add_argument("--output", type=str, required=True, help="Output file path (.csv or .json)")
    parser.add_argument("--option", type=str, help="Path to option.yml file")

    # Search-specific options
    parser.add_argument("--order-by", type=str, default="latest", help="Sort order for search (default: latest)")
    parser.add_argument("--sort-by", type=str, default="latest", help="Sort order for category (latest, likes, views, pictures, score, comments)")
    parser.add_argument("--tags", type=str, default="",
                        help="Comma-separated tags; keep only albums having ALL of them (exact match, e.g. '明日方舟,触手')")
    parser.add_argument("--enrich", action="store_true",
                        help="Fetch per-album details (likes/views/pictures/author) after search; slower but stats are complete")

    return parser.parse_args()


def album_matches_tags(album: dict, required_tags: list[str]) -> bool:
    tags = album.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    lowered = {str(t).lower() for t in tags}
    return all(t.lower() in lowered for t in required_tags)


def fetch_results(service: JmcomicService, args) -> tuple[list[dict], int | None]:
    """Fetch search results based on mode. Returns (albums, total_count)."""
    all_results: dict[str, dict] = {}  # keyed by album id -> dedupe across pages
    total_count: int | None = None

    for page in range(args.page, args.page + args.max_pages):
        print(f"📄 Fetching page {page}...")

        response = {}
        if args.keyword:
            response = service.search_album(args.keyword, page=page, order_by=args.order_by)
        elif args.ranking:
            # Ranking mode: e.g. day -> time_range="day", order_by="likes" (assumed ranking impl)
            # Or use explicit ranking mapping if available.
            # browse_albums supports time_range & order_by
            response = service.browse_albums(time_range=args.ranking, order_by="likes", page=page)
        elif args.category:
            response = service.browse_albums(category=args.category, page=page, order_by=args.sort_by)
        else:
            response = {"albums": []}

        if total_count is None:
            total_count = response.get("total_count")

        results = response.get("albums", [])

        if not results:
            print(f"⚠️ No results on page {page}, stopping.")
            break

        before = len(all_results)
        for album in results:
            album_id = str(album.get("id") or "")
            if album_id and album_id not in all_results:
                all_results[album_id] = album

        print(f"✅ Found {len(results)} albums on page {page} "
              f"({len(all_results) - before} new, {len(all_results)} unique in total)")

    albums = list(all_results.values())

    if args.tags:
        required = [t.strip() for t in args.tags.split(",") if t.strip()]
        before = len(albums)
        albums = [a for a in albums if album_matches_tags(a, required)]
        print(f"🏷️ Tag filter {required}: {before} -> {len(albums)} albums")

    return albums, total_count


def enrich_results(service: JmcomicService, albums: list[dict]) -> list[dict]:
    """Fill in per-album stats (likes/views/pictures/author) via get_album_detail."""
    filled = []
    total = len(albums)
    for i, album in enumerate(albums, 1):
        album_id = album.get("id")
        if not album_id:
            filled.append(album)
            continue
        try:
            detail = service.get_album_detail(str(album_id))
            if isinstance(detail, dict) and detail.get("id"):
                merged = {**album, **{k: v for k, v in detail.items() if v not in (None, "", [])}}
                filled.append(merged)
                if i % 10 == 0 or i == total:
                    print(f"📥 Enriched {i}/{total}")
                continue
        except Exception as exc:
            print(f"⚠️ Failed to enrich album {album_id}: {exc}", file=sys.stderr)
        filled.append(album)
    return filled


def export_to_csv(results: list[dict], output_path: Path):
    """Export results to CSV format"""
    if not results:
        print("⚠️ No results to export")
        return

    core_fields = ["id", "title", "tags", "cover_url"]
    extra_fields = [
        key
        for result in results
        for key in result
        if key not in core_fields
    ]
    fieldnames = [*core_fields, *dict.fromkeys(extra_fields)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            # Convert tags list to string
            row = result.copy()
            row["tags"] = ", ".join(result.get("tags", []))
            writer.writerow(row)

    print(f"✅ Exported {len(results)} albums to {output_path}")


def export_to_json(albums: list[dict], output_path: Path, total_count: int | None = None):
    """Export results to JSON format, matching the documented {albums, total_count} schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"albums": albums, "total_count": total_count if total_count is not None else len(albums)}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✅ Exported {len(albums)} albums to {output_path}")


def main():
    args = parse_args()
    output_path = Path(args.output)

    # Determine export format
    if output_path.suffix.lower() not in [".csv", ".json"]:
        print("❌ Error: Output file must be .csv or .json")
        sys.exit(1)

    print("🔍 JMComic Search Export Tool")
    print(f"{'='*50}")

    # Initialize service
    service = JmcomicService(option_path=args.option)

    # Fetch results
    results, total_count = fetch_results(service, args)

    if not results:
        print("❌ No results found")
        sys.exit(1)

    if args.enrich:
        print(f"\n📥 Enriching {len(results)} albums with details...")
        results = enrich_results(service, results)

    print(f"\n📊 Total albums found: {len(results)}")

    # Export
    if output_path.suffix.lower() == ".csv":
        export_to_csv(results, output_path)
    else:
        export_to_json(results, output_path, total_count)

    print(f"{'='*50}")


if __name__ == "__main__":
    main()
