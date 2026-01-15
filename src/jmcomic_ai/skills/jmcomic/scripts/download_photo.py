#!/usr/bin/env python3
"""
Batch photo/chapter download tool.
Download specific chapters from albums.

Usage:
    # Download specific chapters
    python scripts/download_photo.py --ids 123456,789012,345678
    
    # Download chapters from file
    python scripts/download_photo.py --file photo_ids.txt
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
    parser = argparse.ArgumentParser(description="Batch download JMComic chapters/photos")
    
    # Input mode
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--ids", type=str, help="Comma-separated photo/chapter IDs")
    input_group.add_argument("--file", type=str, help="File containing photo IDs (one per line)")
    
    # Options
    parser.add_argument("--option", type=str, help="Path to option.yml file")
    
    return parser.parse_args()


def load_photo_ids(args) -> list[str]:
    """Load photo IDs from arguments"""
    if args.ids:
        return [pid.strip() for pid in args.ids.split(",") if pid.strip()]
    
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ Error: File not found: {file_path}")
            sys.exit(1)
        
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    return []


def main():
    args = parse_args()
    photo_ids = load_photo_ids(args)
    
    if not photo_ids:
        print("❌ Error: No photo IDs provided")
        sys.exit(1)
    
    print(f"📷 Batch Photo Download Tool")
    print(f"{'='*50}")
    print(f"Total chapters to download: {len(photo_ids)}")
    print(f"{'='*50}\n")
    
    # Initialize service
    service = JmcomicService(option_path=args.option)
    
    # Download each photo
    success_count = 0
    failed_ids = []
    
    for i, photo_id in enumerate(photo_ids, 1):
        print(f"[{i}/{len(photo_ids)}] Downloading chapter {photo_id}...")
        try:
            service.download_photo(photo_id)
            print(f"✅ Successfully downloaded chapter {photo_id}")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed to download chapter {photo_id}: {e}")
            failed_ids.append(photo_id)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Download Summary:")
    print(f"✅ Successful: {success_count}/{len(photo_ids)}")
    print(f"❌ Failed: {len(failed_ids)}/{len(photo_ids)}")
    
    if failed_ids:
        print(f"\nFailed chapter IDs:")
        for pid in failed_ids:
            print(f"  - {pid}")
    
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
