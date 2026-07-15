"""
Unit tests for core logic and upstream compatibility that do not require network access.

These tests cover the shared friendly-vocabulary mappings used by both
`search_album` and `browse_albums`, ensuring the two tools keep an identical
`order_by` / `time_range` vocabulary, plus the jmcomic API and option schema
contract required by the declared dependency baseline (see CHANGELOG 0.0.10).
"""

import json
import unittest
from pathlib import Path

from jmcomic import JmOption

from jmcomic_ai.core import ORDER_BY_MAP, TIME_RANGE_MAP


class TestSharedMappings(unittest.TestCase):
    def test_order_by_friendly_keys(self):
        """search_album and browse_albums share these friendly order_by values."""
        expected = {"latest", "likes", "views", "pictures", "score", "comments"}
        self.assertEqual(expected, set(ORDER_BY_MAP.keys()))
        # Every value maps to a non-empty magic constant code.
        for code in ORDER_BY_MAP.values():
            self.assertTrue(code)

    def test_time_range_friendly_keys(self):
        """'day' and 'today' are accepted aliases for the same range."""
        expected = {"all", "day", "today", "week", "month"}
        self.assertEqual(expected, set(TIME_RANGE_MAP.keys()))
        self.assertEqual(TIME_RANGE_MAP["day"], TIME_RANGE_MAP["today"])


class TestJmcomicCompatibility(unittest.TestCase):
    def test_native_async_download_api_is_available(self):
        """The declared jmcomic baseline must provide the 2.7 async download APIs."""
        self.assertTrue(callable(getattr(JmOption, "download_album_async", None)))
        self.assertTrue(callable(getattr(JmOption, "download_photo_async", None)))

    def test_option_schema_covers_upstream_default_client_fields(self):
        """The MCP option schema must accept every client key emitted by JmOption.default()."""
        project_root = Path(__file__).resolve().parents[1]
        schema_path = project_root / "src" / "jmcomic_ai" / "skills" / "jmcomic" / "assets" / "option_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_client = schema["properties"]["client"]
        upstream_client_keys = set(JmOption.default().deconstruct()["client"])

        self.assertFalse(schema_client.get("additionalProperties", True))
        self.assertLessEqual(upstream_client_keys, set(schema_client["properties"]))


if __name__ == "__main__":
    unittest.main()
