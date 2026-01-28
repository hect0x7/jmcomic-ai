#!/usr/bin/env python3
"""
Album information query tool.
Fetch detailed information for one or multiple albums.

Usage:
    # Single album
    python scripts/album_info.py --id 123456
    
    # Multiple albums
    python scripts/album_info.py --ids 123456,789012,345678
    
    # From file
    python scripts/album_info.py --file album_ids.txt --output album_details.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from jmcomic_ai.core import JmcomicService
except ImportError:
    print("❌ Error: jmcomic_ai not found. Please ensure the package is installed.")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Query JMComic album details")
    
    # Input mode
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--id", type=str, help="Single album ID")
    input_group.add_argument("--ids", type=str, help="Comma-separated album IDs")
    input_group.add_argument("--file", type=str, help="File containing album IDs (one per line)")
    
    # Options
    parser.add_argument("--output", type=str, help="Output JSON file (default: print to console)")
    parser.add_argument("--option", type=str, help="Path to option.yml file")
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress")
    
    return parser.parse_args()


def load_album_ids(args) -> list[str]:
    """Load album IDs from arguments"""
    if args.id:
        return [args.id]
    
    if args.ids:
        return [aid.strip() for aid in args.ids.split(",") if aid.strip()]
    
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ Error: File not found: {file_path}")
            sys.exit(1)
        
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    return []


def fetch_album_details(service: JmcomicService, album_ids: list[str], verbose: bool = False) -> tuple[list[dict], list[dict]]:
    """Fetch details for multiple albums"""
    results = []
    failed = []
    
    for i, album_id in enumerate(album_ids, 1):
        if verbose:
            print(f"[{i}/{len(album_ids)}] Fetching album {album_id}...")
        
        try:
            detail = service.get_album_detail(album_id)
            results.append(detail)
            if verbose:
                print(f"✅ {detail['title']}")
        except Exception as e:
            if verbose:
                print(f"❌ Failed: {e}")
            failed.append({"id": album_id, "error": str(e)})
    
    return results, failed


def print_album_summary(album: dict):
    """Print a single album summary"""
    print(f"\n{'='*60}")
    print(f"📚 {album['title']}")
    print(f"{'='*60}")
    print(f"ID: {album['id']}")
    print(f"Author: {album['author']}")
    print(f"Likes: {album['likes']:,} | Views: {album['views']:,}")
    print(f"Chapters: {album['chapter_count']}")
    print(f"Updated: {album['update_time']}")
    print(f"Tags: {', '.join(album['tags'][:5])}")
    if album['description']:
        desc = album['description'][:100] + "..." if len(album['description']) > 100 else album['description']
        print(f"Description: {desc}")


def main():
    args = parse_args()
    album_ids = load_album_ids(args)
    
    if not album_ids:
        print("❌ Error: No album IDs provided")
        sys.exit(1)
    
    print(f"📖 Album Information Query Tool")
    print(f"{'='*60}")
    print(f"Total albums to query: {len(album_ids)}")
    
    # Initialize service
    service = JmcomicService(option_path=args.option)
    
    # Fetch details
    results, failed = fetch_album_details(service, album_ids, verbose=args.verbose)
    
    # Output results
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "success_count": len(results),
            "failed_count": len(failed),
            "albums": results,
            "failed": failed
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Exported {len(results)} album details to {output_path}")
    else:
        # Print to console
        for album in results:
            print_album_summary(album)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Summary:")
    print(f"✅ Success: {len(results)}/{len(album_ids)}")
    print(f"❌ Failed: {len(failed)}/{len(album_ids)}")
    
    if failed and not args.output:
        print(f"\nFailed IDs:")
        for item in failed:
            print(f"  - {item['id']}: {item['error']}")
    
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
