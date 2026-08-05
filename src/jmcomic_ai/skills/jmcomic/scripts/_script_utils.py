"""Shared helpers for JMComic Skill command-line scripts."""

import sys


def import_error_message(exc: ImportError, target_package: str, install_hint: str) -> str:
    """Describe whether the requested package or one of its dependencies failed."""
    missing_module = getattr(exc, "name", None)
    if isinstance(exc, ModuleNotFoundError) and missing_module == target_package:
        return f"Error: {target_package} not found. {install_hint}"
    if isinstance(exc, ModuleNotFoundError) and missing_module:
        return f"Error: failed to load {target_package} because dependency '{missing_module}' is unavailable."
    return f"Error: failed to import {target_package}: {exc}"


def exit_for_import_error(exc: ImportError, target_package: str, install_hint: str) -> None:
    """Print an actionable import error and terminate the script."""
    print(import_error_message(exc, target_package, install_hint), file=sys.stderr)
    raise SystemExit(1)
