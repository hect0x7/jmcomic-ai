"""
Unit tests for core pure logic that does not require network access.

These tests cover the shared friendly-vocabulary mappings used by both
`search_album` and `browse_albums`, ensuring the two tools keep an identical
`order_by` / `time_range` vocabulary (see CHANGELOG 0.0.10).
"""

import unittest

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


if __name__ == "__main__":
    unittest.main()
