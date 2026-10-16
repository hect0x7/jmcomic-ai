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
    from jmcomic_ai.download_cli import add_download_arguments

    add_download_arguments(parser)
    return parser.parse_args()


def load_album_ids(args) -> list[str]:
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
        album_ids = load_album_ids(args)
        if not album_ids:
            raise ValueError("No album IDs provided")
        if getattr(args, "details", False) and not getattr(args, "plan", False):
            raise ValueError("--details requires --plan")
        if getattr(args, "background", False):
            from jmcomic_ai.background import from_arguments

            result = from_arguments(args, album_ids, "album")
        else:
            task_dir = getattr(args, "task_dir", None)
            service = JmcomicService(option_path=args.option, **({"task_log_dir": task_dir} if task_dir else {}))
            result = await run_download(service, args, album_ids, "album")
    except (ValueError, OSError) as error:
        result = {"status": "error", "error": str(error)}
    script_exit(result, getattr(args, "json", False))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
