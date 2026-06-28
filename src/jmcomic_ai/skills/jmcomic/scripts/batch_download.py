#!/usr/bin/env python3
"""
Batch download tool for JMComic albums.
Downloads multiple albums from a list of IDs.

Usage:
    python scripts/batch_download.py --ids 123456,789012,345678
    python scripts/batch_download.py --file album_ids.txt
"""

import argparse
import asyncio
import sys
from pathlib import Path

try:
    from jmcomic_ai.core import JmcomicService
except ImportError:
    print("❌ Error: jmcomic_ai not found. Please ensure the package is installed.")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Batch download JMComic albums")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--ids",
        type=str,
        help="Comma-separated album IDs (e.g., 123456,789012,345678)"
    )
    group.add_argument(
        "--file",
        type=str,
        help="Path to file containing album IDs (one per line)"
    )
    parser.add_argument(
        "--option",
        type=str,
        help="Path to option.yml file (default: ~/.jmcomic/option.yml)"
    )
    return parser.parse_args()


def load_album_ids(args) -> list[str]:
    """Load album IDs from command line or file"""
    if args.ids:
        return [aid.strip() for aid in args.ids.split(",") if aid.strip()]

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ Error: File not found: {file_path}")
            sys.exit(1)

        with open(file_path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]

    return []


async def main():
    args = parse_args()
    album_ids = load_album_ids(args)

    if not album_ids:
        print("❌ Error: No album IDs provided")
        sys.exit(1)

    print("📦 Batch Download Tool")
    print(f"{'='*50}")
    print(f"Total albums to download: {len(album_ids)}")
    print(f"{'='*50}\n")

    # Initialize service
    service = JmcomicService(option_path=args.option)

    # Download each album
    success_count = 0
    failed_ids = []

    print("Queuing downloads...")
    tasks = []
    for i, album_id in enumerate(album_ids, 1):
        tasks.append(service.download_album(album_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, (album_id, result) in enumerate(zip(album_ids, results), 1):
        if isinstance(result, Exception):
            print(f"❌ Failed to download album {album_id}: {result}")
            failed_ids.append(album_id)
        elif result.get("status") == "success":
            print(f"✅ Successfully downloaded album {album_id} ({result.get('title')})")
            print(f"   📂 {result.get('download_path')}")
            success_count += 1
        else:
            print(f"❌ Failed to download album {album_id}: {result.get('error')}")
            failed_ids.append(album_id)

    # Summary
    print(f"\n{'='*50}")
    print("📊 Download Summary:")
    print(f"✅ Successful: {success_count}/{len(album_ids)}")
    print(f"❌ Failed: {len(failed_ids)}/{len(album_ids)}")

    if failed_ids:
        print("\nFailed album IDs:")
        for aid in failed_ids:
            print(f"  - {aid}")

    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
