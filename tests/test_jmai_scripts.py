"""Regression tests for search_export / post_process Skill script fixes.

Covers:
- post_process `--outdir` must resolve to a file rule (not the bare "Bd" directory)
- post_process optional dependency pre-check (auto-install / clear error / opt-out)
- search_export cross-page de-duplication and total_count propagation
- search_export exact tag filtering and the documented JSON wrapper schema
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jmcomic_ai.skills.jmcomic.scripts import post_process, search_export


class TestPostProcessOutdir(unittest.TestCase):
    def _run_main(self, argv):
        service = Mock()
        service.post_process.return_value = {"status": "success"}
        with (
            patch("sys.argv", ["script", *argv]),
            patch.object(post_process, "ensure_dependencies"),
            patch.object(post_process, "JmcomicService", return_value=service),
        ):
            post_process.main()
        return service.post_process.call_args[0][2]

    def test_outdir_resolves_to_file_rule_not_directory(self):
        for process_type, ext in (("zip", "zip"), ("img2pdf", "pdf"), ("long_img", "png")):
            with self.subTest(process_type=process_type):
                params = self._run_main(
                    ["--id", "123", "--type", process_type, "--outdir", "/tmp/out"]
                )
                rule = params["dir_rule"]["rule"]
                self.assertNotEqual(rule, "Bd")
                self.assertTrue(rule.endswith(f".{ext}"))
                self.assertEqual(params["dir_rule"]["base_dir"], "/tmp/out")

    def test_album_level_uses_album_title_and_photo_level_uses_photo_index(self):
        album_params = self._run_main(
            ["--id", "123", "--type", "zip", "--outdir", "/tmp/out", "--level", "album"]
        )
        self.assertIn("{Atitle}", album_params["dir_rule"]["rule"])

        photo_params = self._run_main(
            ["--id", "123", "--type", "zip", "--outdir", "/tmp/out", "--level", "photo"]
        )
        self.assertIn("{Pindex}", photo_params["dir_rule"]["rule"])

    def test_explicit_dir_rule_is_kept_and_conflicts_are_rejected(self):
        params = self._run_main(
            [
                "--id", "123", "--type", "zip",
                "--dir-rule", "Bd/custom/{Atitle}.zip", "--base-dir", "/tmp/base",
            ]
        )
        self.assertEqual(params["dir_rule"]["rule"], "Bd/custom/{Atitle}.zip")
        self.assertEqual(params["dir_rule"]["base_dir"], "/tmp/base")

        with (
            patch("sys.argv", [
                "script", "--id", "1", "--type", "zip",
                "--outdir", "/x", "--dir-rule", "Bd/a.zip", "--base-dir", "/y",
            ]),
            self.assertRaises(SystemExit),
        ):
            post_process.main()


class TestPostProcessDependencies(unittest.TestCase):
    def test_dependency_is_skipped_when_already_installed(self):
        with (
            patch.object(post_process.importlib.util, "find_spec", return_value=object()),
            patch.object(post_process.subprocess, "check_call") as check_call,
        ):
            post_process.ensure_dependencies("img2pdf")
        check_call.assert_not_called()

    def test_missing_dependency_is_auto_installed(self):
        with (
            patch.object(post_process.importlib.util, "find_spec", return_value=None),
            patch.object(post_process.shutil, "which", return_value="python"),
            patch.object(post_process.subprocess, "check_call") as check_call,
        ):
            post_process.ensure_dependencies("img2pdf", auto_install=True)
        check_call.assert_called_once()

    def test_missing_dependency_without_install_exits_with_hint(self):
        with patch.object(post_process.importlib.util, "find_spec", return_value=None):
            with self.assertRaises(SystemExit):
                post_process.ensure_dependencies("img2pdf", auto_install=False)

    def test_stdlib_backed_type_needs_no_dependency(self):
        with patch.object(post_process.importlib.util, "find_spec") as find_spec:
            post_process.ensure_dependencies("zip")
        find_spec.assert_not_called()


class TestSearchExportDedupe(unittest.TestCase):
    @staticmethod
    def _args(**overrides):
        base = {
            "keyword": "x", "ranking": None, "category": None,
            "page": 1, "max_pages": 1,
            "order_by": "latest", "sort_by": "latest",
            "tags": "", "enrich": False,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_dedupes_across_pages_and_returns_total_count(self):
        service = Mock()
        service.search_album.side_effect = [
            {"albums": [{"id": "1"}, {"id": "2"}], "total_count": 3},
            {"albums": [{"id": "2"}, {"id": "3"}], "total_count": 3},
            {"albums": [], "total_count": 3},
        ]
        albums, total_count = search_export.fetch_results(
            service, self._args(max_pages=3)
        )
        self.assertEqual([a["id"] for a in albums], ["1", "2", "3"])
        self.assertEqual(total_count, 3)

    def test_keeps_only_albums_having_all_required_tags(self):
        service = Mock()
        service.search_album.return_value = {
            "albums": [
                {"id": "1", "tags": ["明日方舟", "触手"]},
                {"id": "2", "tags": ["明日方舟"]},
            ],
            "total_count": 2,
        }
        albums, _ = search_export.fetch_results(
            service, self._args(tags="明日方舟,触手")
        )
        self.assertEqual([a["id"] for a in albums], ["1"])

    def test_json_export_wraps_albums_and_total_count(self):
        albums = [{"id": "1", "title": "Album"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "results.json"
            search_export.export_to_json(albums, output_path, 7)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload, {"albums": albums, "total_count": 7})

    def test_json_export_falls_back_to_album_count(self):
        albums = [{"id": "1"}, {"id": "2"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "results.json"
            search_export.export_to_json(albums, output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["total_count"], 2)


class TestAlbumMatchesTags(unittest.TestCase):
    def test_requires_all_tags_case_insensitively(self):
        album = {"tags": ["明日方舟", "Touch"]}
        self.assertTrue(search_export.album_matches_tags(album, ["touch"]))
        self.assertFalse(search_export.album_matches_tags(album, ["touch", "missing"]))

    def test_accepts_comma_separated_tag_string(self):
        album = {"tags": "a, b ,c"}
        self.assertTrue(search_export.album_matches_tags(album, ["B", "C"]))
        self.assertFalse(search_export.album_matches_tags(album, ["d"]))


if __name__ == "__main__":
    unittest.main()
