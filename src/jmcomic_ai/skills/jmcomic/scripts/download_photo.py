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
import asyncio
import sys

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic import JmcomicException, JmcomicText
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic", "Please install: pip install jmcomic")

try:
    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic_ai", "Please ensure the package is installed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Batch download JMComic chapters/photos")

    # Input mode
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--ids", type=str, help="Comma-separated photo/chapter IDs")
    input_group.add_argument("--file", type=str, help="File containing photo IDs (one per line)")

    # Options
    parser.add_argument("--option", type=str, help="Path to option.yml file")

    from jmcomic_ai.download_cli import add_download_arguments

    add_download_arguments(parser)
    return parser.parse_args()


def load_photo_ids(args) -> list[str]:
    """Load the shared UTF-8/BOM-aware ID list and preserve upstream parsing."""
    from jmcomic_ai.download_cli import read_ids

    try:
        return [JmcomicText.parse_to_jm_id(value) for value in read_ids(args.ids, args.file)]
    except JmcomicException as error:
        raise ValueError(str(error)) from error


async def main():
    args = parse_args()
    from jmcomic_ai.download_cli import run_download, script_exit

    try:
        photo_ids = load_photo_ids(args)
        if not photo_ids:
            raise ValueError("No photo IDs provided")
        if getattr(args, "details", False) and not getattr(args, "plan", False):
            raise ValueError("--details requires --plan")
        if getattr(args, "background", False):
            from jmcomic_ai.background import from_arguments

            result = from_arguments(args, photo_ids, "photo")
        else:
            task_dir = getattr(args, "task_dir", None)
            service = JmcomicService(option_path=args.option, **({"task_log_dir": task_dir} if task_dir else {}))
            result = await run_download(service, args, photo_ids, "photo")
    except (ValueError, OSError) as error:
        result = {"status": "error", "error": str(error)}
    script_exit(result, getattr(args, "json", False))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
