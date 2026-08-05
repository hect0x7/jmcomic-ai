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
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic import JmcomicText

    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic_ai", "Please ensure the package is installed.")


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
        return [JmcomicText.parse_to_jm_id(aid.strip()) for aid in args.ids.split(",") if aid.strip()]

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ Error: File not found: {file_path}")
            sys.exit(1)

        with open(file_path, encoding="utf-8") as f:
            values = (line.strip() for line in f)
            return [JmcomicText.parse_to_jm_id(value) for value in values if value and not value.startswith("#")]

    return []


def download_covers(service: JmcomicService, album_ids: list[str], output_dir: Path) -> tuple[int, list[str]]:
    """Download covers for multiple albums"""
    success_count = 0
    failed_ids = []

    for i, album_id in enumerate(album_ids, 1):
        print(f"[{i}/{len(album_ids)}] Downloading cover for album {album_id}...")

        try:
            message = service.download_cover(album_id, output_dir=str(output_dir))
            print(f"✅ {message}")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed_ids.append(album_id)

    return success_count, failed_ids


def main():
    args = parse_args()
    album_ids = load_album_ids(args)

    if not album_ids:
        print("❌ Error: No album IDs provided")
        sys.exit(1)

    # Determine output directory
    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    else:
        output_dir = Path.cwd() / "covers"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("🖼️ Batch Cover Download Tool")
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
    print("📊 Download Summary:")
    print(f"✅ Successful: {success_count}/{len(album_ids)}")
    print(f"❌ Failed: {len(failed_ids)}/{len(album_ids)}")

    if failed_ids:
        print("\nFailed album IDs:")
        for aid in failed_ids:
            print(f"  - {aid}")

    print(f"\n📂 Covers saved to: {output_dir}")
    print(f"{'='*50}")

    if failed_ids:
        sys.exit(1)


if __name__ == "__main__":
    main()
