"""Tests for forward-compatible CSV exports in Skill scripts."""

import csv
import tempfile
import unittest
from pathlib import Path

from jmcomic_ai.skills.jmcomic.scripts import ranking_tracker, search_export


class TestCsvExportScripts(unittest.TestCase):
    def test_search_export_adds_extra_fields_as_columns(self):
        result = {
            "id": "123",
            "title": "Test Album",
            "tags": ["tag-a", "tag-b"],
            "cover_url": "https://example.test/123.jpg",
            "likes": 100,
        }
        later_result = {
            "id": "456",
            "title": "Later Album",
            "tags": [],
            "cover_url": "https://example.test/456.jpg",
            "future_field": "value",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "search.csv"
            search_export.export_to_csv([result, later_result], output_path)

            with output_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(["id", "title", "tags", "cover_url", "likes", "future_field"], list(rows[0]))
        self.assertEqual("tag-a, tag-b", rows[0]["tags"])
        self.assertEqual("100", rows[0]["likes"])
        self.assertEqual("value", rows[1]["future_field"])

    def test_ranking_export_adds_extra_fields_as_columns(self):
        result = {
            "rank": 1,
            "id": "123",
            "title": "Test Album",
            "tags": ["tag"],
            "cover_url": "https://example.test/123.jpg",
            "period": "day",
            "likes": 100,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "ranking.csv"
            ranking_tracker.export_to_csv([result], output_path)

            with output_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(["rank", "id", "title", "tags", "cover_url", "period", "likes"], list(rows[0]))
        self.assertEqual("1", rows[0]["rank"])
        self.assertEqual("100", rows[0]["likes"])

    def test_json_exports_create_parent_directories(self):
        results = [{"id": "123", "title": "Test Album"}]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            search_path = temp_path / "search" / "results.json"
            ranking_path = temp_path / "ranking" / "results.json"

            search_export.export_to_json(results, search_path)
            ranking_tracker.export_to_json(results, ranking_path)

            self.assertTrue(search_path.is_file())
            self.assertTrue(ranking_path.is_file())


if __name__ == "__main__":
    unittest.main()
