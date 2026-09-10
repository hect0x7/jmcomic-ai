#!/usr/bin/env python3
"""Fetch one page of favorite albums as JSON."""

import argparse
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
    parser = argparse.ArgumentParser(description="Browse JMComic favorite albums")
    parser.add_argument("--folder-id", default="0", help="Favorite folder ID (default: 0, all favorites)")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--order-by", default="favorite_time", help="Sort: favorite_time, update_time")
    parser.add_argument("--username", default="", help="Required for HTML queries with Cookie-only authentication")
    parser.add_argument("--output", help="Output JSON file (default: print to console)")
    parser.add_argument("--option", help="Path to option.yml file")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        service = JmcomicService(option_path=args.option)
        result = service.browse_favorite_albums(
            folder_id=args.folder_id,
            page=args.page,
            order_by=args.order_by,
            username=args.username,
        )
    except Exception as e:
        print(f"Error: failed to fetch favorite albums: {e}", file=sys.stderr)
        sys.exit(1)

    output_text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(f"{output_text}\n", encoding="utf-8")
            resolved_output_path = output_path.resolve()
        except OSError as e:
            print(f"Error: failed to export favorite albums to {output_path}: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Exported favorite albums to {resolved_output_path}")
    else:
        print(output_text)

    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
