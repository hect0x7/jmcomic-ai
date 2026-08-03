"""Validate that the release commit matches the package version source."""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def read_source_version() -> str:
    path = ROOT_DIR / "src" / "jmcomic_ai" / "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "__version__":
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise ValueError(f"Static __version__ assignment not found in {path}")


def read_release_version() -> str:
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    match = re.match(r"^v([^:]+):", subject)
    if match is None:
        raise ValueError(f"Release commit must start with v{{version}}:, got: {subject}")
    return match.group(1)


def main() -> int:
    source_version = read_source_version()
    release_version = read_release_version()

    if release_version != source_version:
        print(
            f"Version mismatch: __init__.py={source_version}, release commit={release_version}",
            file=sys.stderr,
        )
        return 1

    print(f"Version OK: {source_version} (source and release commit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
