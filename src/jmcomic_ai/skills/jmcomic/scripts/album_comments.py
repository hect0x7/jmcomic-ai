#!/usr/bin/env python3
"""Fetch one page of album comments, including replies and spoiler flags."""

import argparse
import json
import sys
from pathlib import Path

try:
    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    missing_module = getattr(exc, "name", None)
    if isinstance(exc, ModuleNotFoundError) and missing_module == "jmcomic_ai":
        message = "Error: jmcomic_ai not found. Please ensure the package is installed."
    elif isinstance(exc, ModuleNotFoundError) and missing_module:
        message = f"Error: failed to load jmcomic_ai because dependency '{missing_module}' is unavailable."
    else:
        message = f"Error: failed to import JmcomicService: {exc}"
    print(message, file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch JMComic album comments")
    parser.add_argument("--id", required=True, help="Album ID")
    parser.add_argument("--page", type=int, default=1, help="Comment page number (default: 1)")
    parser.add_argument("--output", help="Output JSON file (default: print to console)")
    parser.add_argument("--option", help="Path to option.yml file")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        service = JmcomicService(option_path=args.option)
        result = service.get_album_comments(args.id, page=args.page)
    except Exception as e:
        print(f"Error: failed to fetch comments for album {args.id}: {e}", file=sys.stderr)
        sys.exit(1)

    output_text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(f"{output_text}\n", encoding="utf-8")
            resolved_output_path = output_path.resolve()
        except OSError as e:
            print(f"Error: failed to export comments to {output_path}: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Exported comments to {resolved_output_path}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
