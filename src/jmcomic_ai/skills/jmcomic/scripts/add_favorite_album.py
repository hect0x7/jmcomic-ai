#!/usr/bin/env python3
"""Add one album to the current account's favorites."""

import argparse
import json
import sys

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic_ai", "Please ensure the package is installed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Add a JMComic album to favorites")
    parser.add_argument("--id", required=True, help="Album ID, JM-prefixed ID, or album URL")
    parser.add_argument("--option", help="Path to option.yml file")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        service = JmcomicService(option_path=args.option)
        result = service.add_favorite_album(args.id)
    except Exception as e:
        print(f"Error: failed to add favorite album: {e}", file=sys.stderr)
        sys.exit(1)

    output_text = json.dumps(result, indent=2, ensure_ascii=False)
    print(output_text)

    if result.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
