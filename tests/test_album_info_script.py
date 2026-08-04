"""Tests for the album information skill script."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jmcomic_ai.skills.jmcomic.scripts import album_info


class TestAlbumInfoScript(unittest.TestCase):
    def test_summary_formats_numeric_string_counts(self):
        album = {
            "id": "350234",
            "title": "Test Album",
            "author": "N/A",
            "likes": "87178",
            "views": "1722123",
            "chapter_count": 2,
            "update_time": "0",
            "tags": ["tag"],
            "description": "",
        }
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            album_info.print_album_summary(album)

        self.assertIn("Likes: 87,178 | Views: 1,722,123", stdout.getvalue())
        self.assertIn("Chapters: 2", stdout.getvalue())

    def test_export_creates_parent_directories(self):
        album = {"id": "350234", "title": "Test Album"}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "album.json"
            args = SimpleNamespace(id="350234", ids=None, file=None, output=str(output_path), option=None, verbose=False)

            with (
                patch.object(album_info, "parse_args", return_value=args),
                patch.object(album_info, "JmcomicService"),
                patch.object(album_info, "fetch_album_details", return_value=([album], [])),
            ):
                album_info.main()

            output = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual([album], output["albums"])


if __name__ == "__main__":
    unittest.main()
