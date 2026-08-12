"""Tests for friendly failures in the forum comments skill script."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jmcomic_ai.skills.jmcomic.scripts import forum_comments


class TestForumCommentsScript(unittest.TestCase):
    def test_service_failure_is_printed_without_traceback(self):
        args = SimpleNamespace(page=2, output=None, option="missing.yml")
        stderr = io.StringIO()

        with (
            patch.object(forum_comments, "parse_args", return_value=args),
            patch.object(forum_comments, "JmcomicService", side_effect=RuntimeError("invalid option")),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as exit_context,
        ):
            forum_comments.main()

        self.assertEqual(1, exit_context.exception.code)
        self.assertIn("failed to fetch forum comments on page 2: invalid option", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_fetch_failure_is_printed_without_traceback(self):
        args = SimpleNamespace(page=2, output=None, option="option.yml")
        service = Mock()
        service.get_forum_comments.side_effect = RuntimeError("request failed")
        stderr = io.StringIO()

        with (
            patch.object(forum_comments, "parse_args", return_value=args),
            patch.object(forum_comments, "JmcomicService", return_value=service),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as exit_context,
        ):
            forum_comments.main()

        self.assertEqual(1, exit_context.exception.code)
        self.assertIn("failed to fetch forum comments on page 2: request failed", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        service.get_forum_comments.assert_called_once_with(page=2)

    def test_result_can_be_exported_as_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "comments.json"
            args = SimpleNamespace(page=3, output=str(output_path), option="custom-option.yml")
            service = Mock()
            service.get_forum_comments.return_value = {"page": 3, "comments": []}

            with (
                patch.object(forum_comments, "parse_args", return_value=args),
                patch.object(forum_comments, "JmcomicService", return_value=service) as service_class,
            ):
                forum_comments.main()

            service_class.assert_called_once_with(option_path="custom-option.yml")
            service.get_forum_comments.assert_called_once_with(page=3)
            self.assertEqual({"page": 3, "comments": []}, json.loads(output_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
