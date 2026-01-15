#!/usr/bin/env python3
"""
Batch cover download tool.
Download cover images for multiple albums.

Usage:
    # Download covers for specific albums
    python scripts/download_covers.py --ids 123456,789012,345678
    
    # Download covers from file
    python scripts/download_covers.py --file album_ids.txt
    
    # Specify output directory
    python scripts/download_covers.py --ids 123456,789012 --output ./covers
"""

import argparse
import sys
from pathlib import Path

try:
    from jmcomic_ai.core import JmcomicService
except ImportError:
    print("❌ Error: jmcomic_ai not found. Please ensure the package is installed.")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Batch download JMComic album covers")
    
    # Input mode
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--ids", type=str, help="Comma-separated album IDs")
    input_group.add_argument("--file", type=str, help="File containing album IDs (one per line)")
    
    # Options
    parser.add_argument("--output", type=str, help="Output directory (default: ./covers)")
    parser.add_argument("--option", type=str, help="Path to option.yml file")
    
    return parser.parse_args()


def load_album_ids(args) -> list[str]:
    """Load album IDs from arguments"""
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


def download_covers(service: JmcomicService, album_ids: list[str], output_dir: Path) -> tuple[int, list[str]]:
    """Download covers for multiple albums"""
    # Temporarily override the cover directory
    original_base_dir = service.option.dir_rule.base_dir
    service.option.dir_rule.base_dir = str(output_dir.parent)
    
    success_count = 0
    failed_ids = []
    
    for i, album_id in enumerate(album_ids, 1):
        print(f"[{i}/{len(album_ids)}] Downloading cover for album {album_id}...")
        
        try:
            # download_cover saves to base_dir/covers/
            service.download_cover(album_id)
            print(f"✅ Success")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed_ids.append(album_id)
    
    # Restore original base_dir
    service.option.dir_rule.base_dir = original_base_dir
    
    return success_count, failed_ids


def main():
    args = parse_args()
    album_ids = load_album_ids(args)
    
    if not album_ids:
        print("❌ Error: No album IDs provided")
        sys.exit(1)
    
    # Determine output directory
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = Path.cwd() / "covers"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🖼️ Batch Cover Download Tool")
    print(f"{'='*50}")
    print(f"Total covers to download: {len(album_ids)}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*50}\n")
    
    # Initialize service
    service = JmcomicService(option_path=args.option)
    
    # Download covers
    success_count, failed_ids = download_covers(service, album_ids, output_dir)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Download Summary:")
    print(f"✅ Successful: {success_count}/{len(album_ids)}")
    print(f"❌ Failed: {len(failed_ids)}/{len(album_ids)}")
    
    if failed_ids:
        print(f"\nFailed album IDs:")
        for aid in failed_ids:
            print(f"  - {aid}")
    
    print(f"\n📂 Covers saved to: {output_dir}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
