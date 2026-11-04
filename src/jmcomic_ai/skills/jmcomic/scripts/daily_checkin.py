#!/usr/bin/env python3
"""Perform daily check-in for the authenticated JMComic account and output JSON."""

import argparse
import json
import sys
from pathlib import Path

_reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
if callable(_reconfigure_stdout):
    _reconfigure_stdout(encoding="utf-8", errors="replace")

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic_ai", "Please ensure the package is installed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Perform daily check-in for JMComic account")
    parser.add_argument(
        "--user-id",
        default="",
        help="Numeric user ID (only needed for API client with raw Cookie-only authentication)",
    )
    parser.add_argument("--output", help="Output JSON file (default: print to console)")
    parser.add_argument("--option", help="Path to option.yml file")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        service = JmcomicService(option_path=args.option)
        result = service.daily_checkin(user_id=args.user_id)
    except Exception as exc:
        print(f"Error: failed to perform daily check-in: {exc}", file=sys.stderr)
        sys.exit(1)

    output_text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(f"{output_text}\n", encoding="utf-8")
            resolved_output_path = output_path.resolve()
        except OSError as exc:
            print(f"Error: failed to export daily check-in result to {output_path}: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Exported daily check-in result to {resolved_output_path}")
    else:
        print(output_text)

    if result.get("status") not in ("checked_in", "already_checked_in"):
        sys.exit(1)


if __name__ == "__main__":
    main()
