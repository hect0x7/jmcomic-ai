"""Tests for friendly failures in the album comments skill script."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jmcomic_ai.skills.jmcomic.scripts import album_comments


class TestAlbumCommentsScript(unittest.TestCase):
    def test_service_initialization_failure_is_printed_without_traceback(self):
        args = SimpleNamespace(id="123", page=1, output=None, option="missing.yml")
        stderr = io.StringIO()

        with (
            patch.object(album_comments, "parse_args", return_value=args),
            patch.object(album_comments, "JmcomicService", side_effect=RuntimeError("invalid option")),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as exit_context,
        ):
            album_comments.main()
        self.assertEqual(1, exit_context.exception.code)

        self.assertIn("failed to fetch comments for album 123: invalid option", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_output_failure_is_printed_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_directory = Path(temp_dir) / "already-a-directory"
            output_directory.mkdir()
            args = SimpleNamespace(id="123", page=1, output=str(output_directory), option=None)
            service = Mock()
            service.get_album_comments.return_value = {"comments": []}
            stderr = io.StringIO()

            with (
                patch.object(album_comments, "parse_args", return_value=args),
                patch.object(album_comments, "JmcomicService", return_value=service),
                redirect_stderr(stderr),
                self.assertRaises(SystemExit) as exit_context,
            ):
                album_comments.main()
            self.assertEqual(1, exit_context.exception.code)

            self.assertIn(f"failed to export comments to {output_directory}", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
