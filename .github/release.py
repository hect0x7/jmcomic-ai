"""Build GitHub Release metadata from the package version and changelog."""

import ast
import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = Path("src/jmcomic_ai/__init__.py")
CHANGELOG_FILE = Path("CHANGELOG.md")
RELEASE_BODY_FILE = Path("release_body.txt")
VERSION_HEADING_PATTERN = re.compile(
    r"^## \[(?P<version>[^]]+)] - (?P<date>\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)


def read_source_version(path: Path) -> str:
    """Read the static ``__version__`` assignment from the package source."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "__version__":
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise ValueError(f"Static __version__ assignment not found in {path}")


def extract_release_body(changelog: str, version: str) -> str:
    """Extract one non-empty, dated changelog section for ``version``."""
    matches = [match for match in VERSION_HEADING_PATTERN.finditer(changelog) if match.group("version") == version]
    if not matches:
        raise ValueError(f"Changelog section not found: ## [{version}] - YYYY-MM-DD")
    if len(matches) > 1:
        raise ValueError(f"Duplicate changelog sections found for version {version}")

    match = matches[0]
    next_heading = re.search(r"^## \[", changelog[match.end():], re.MULTILINE)
    section_end = match.end() + next_heading.start() if next_heading else len(changelog)
    body = changelog[match.end():section_end].strip()
    if not body:
        raise ValueError(f"Changelog section for version {version} is empty")
    return body


def build_release_metadata(root_dir: Path | None = None) -> tuple[str, str]:
    """Return the release tag and body derived from repository files."""
    root_dir = root_dir or ROOT_DIR
    version = read_source_version(root_dir / VERSION_FILE)
    changelog = (root_dir / CHANGELOG_FILE).read_text(encoding="utf-8")
    return f"v{version}", extract_release_body(changelog, version)


def add_output(key: str, value: str, output_path: str | None = None) -> None:
    """Write a single-line value to GitHub Actions output when available."""
    output_path = output_path or os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        print(f"{key}={value}")
        return
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"{key}={value}\n")


def main() -> int:
    try:
        tag, body = build_release_metadata()
        (ROOT_DIR / RELEASE_BODY_FILE).write_text(f"{body}\n", encoding="utf-8")
        add_output("tag", tag)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"Release metadata error: {exc}", file=sys.stderr)
        return 1

    print(f"Release metadata ready: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
