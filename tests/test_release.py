"""Tests for changelog-driven GitHub Release metadata."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_SCRIPT = PROJECT_ROOT / ".github" / "release.py"
SPEC = importlib.util.spec_from_file_location("jmcomic_ai_release", RELEASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load release script: {RELEASE_SCRIPT}")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class TestReleaseMetadata(unittest.TestCase):
    def create_project(self, root: Path, version: str, changelog: str) -> None:
        package_dir = root / "src" / "jmcomic_ai"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
        (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

    def test_builds_tag_and_body_from_matching_version_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_project(
                root,
                "1.2.3",
                """# Changelog

## [1.2.3] - 2026-08-05

### Added
- New release behavior.

## [1.2.2] - 2026-08-01

### Fixed
- Previous fix.
""",
            )

            tag, body = release.build_release_metadata(root)

            self.assertEqual(tag, "v1.2.3")
            self.assertEqual(body, "### Added\n- New release behavior.")

    def test_rejects_missing_or_undated_version_section(self):
        for changelog in (
            "# Changelog\n\n## [1.2.2] - 2026-08-01\n\n### Fixed\n- Old.\n",
            "# Changelog\n\n## [1.2.3]\n\n### Added\n- Missing date.\n",
        ):
            with self.subTest(changelog=changelog), self.assertRaisesRegex(ValueError, "section not found"):
                release.extract_release_body(changelog, "1.2.3")

    def test_rejects_duplicate_version_sections(self):
        changelog = """# Changelog

## [1.2.3] - 2026-08-05
- First.

## [1.2.3] - 2026-08-04
- Duplicate.
"""

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            release.extract_release_body(changelog, "1.2.3")

    def test_rejects_empty_version_section(self):
        changelog = """# Changelog

## [1.2.3] - 2026-08-05

## [1.2.2] - 2026-08-01
- Old.
"""

        with self.assertRaisesRegex(ValueError, "empty"):
            release.extract_release_body(changelog, "1.2.3")

    def test_main_writes_release_body_and_github_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_path = root / "github-output.txt"
            self.create_project(
                root,
                "1.2.3",
                "# Changelog\n\n## [1.2.3] - 2026-08-05\n\n### Fixed\n- Reliable release notes.\n",
            )

            with patch.object(release, "ROOT_DIR", root), patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                self.assertEqual(release.main(), 0)

            self.assertEqual((root / "release_body.txt").read_text(encoding="utf-8"), "### Fixed\n- Reliable release notes.\n")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "tag=v1.2.3\n")


class TestPublishWorkflow(unittest.TestCase):
    def test_workflow_uses_changelog_release_script_without_commit_body(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")

        self.assertIn("python .github/release.py", workflow)
        self.assertNotIn("commit_message=", workflow)
        self.assertNotIn("generate_release_notes:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)


if __name__ == "__main__":
    unittest.main()
