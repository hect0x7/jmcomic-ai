"""
Unit tests for core logic and upstream compatibility that do not require network access.

These tests cover the shared friendly-vocabulary mappings used by both
`search_album` and `browse_albums`, ensuring the two tools keep an identical
`order_by` / `time_range` vocabulary, plus the jmcomic API and option schema
contract required by the declared dependency baseline (see CHANGELOG 0.0.10).
"""

import asyncio
import json
import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jmcomic import JmAlbumComment, JmAlbumCommentPage, JmcomicClient, JmOption, jm_log, jm_task_context

from jmcomic_ai.core import (
    GLOBAL_LOG_HANDLER_NAME,
    ORDER_BY_MAP,
    TIME_RANGE_MAP,
    JmcomicService,
    _configure_logger_file_only,
    _get_global_file_handler,
)


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


class TestLoggingConfiguration(unittest.TestCase):
    def test_logger_uses_shared_files_without_console_or_root_propagation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = logging.Logger("jmcomic_ai.test.file_only")
            console_handler = logging.StreamHandler()
            task_handler = logging.FileHandler(Path(temp_dir) / "task.log", encoding="utf-8")
            global_handler = logging.FileHandler(Path(temp_dir) / "global.log", encoding="utf-8")
            logger.addHandler(console_handler)
            logger.addHandler(task_handler)

            try:
                _configure_logger_file_only(logger, global_handler)

                self.assertNotIn(console_handler, logger.handlers)
                self.assertIn(task_handler, logger.handlers)
                self.assertIn(global_handler, logger.handlers)
                self.assertFalse(logger.propagate)
            finally:
                task_handler.close()
                global_handler.close()

    @unittest.skipIf(os.name == "nt", "Creating symlinks requires extra privileges on Windows")
    def test_global_handler_is_reused_for_symlinked_log_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            real_dir = temp_path / "real"
            real_dir.mkdir()
            linked_dir = temp_path / "linked"
            linked_dir.symlink_to(real_dir, target_is_directory=True)

            logger = logging.getLogger("jmcomic_ai")
            handler = logging.FileHandler(linked_dir / "shared.log", encoding="utf-8")
            handler.set_name(GLOBAL_LOG_HANDLER_NAME)
            logger.addHandler(handler)
            result = None
            try:
                result = _get_global_file_handler((real_dir / "shared.log").resolve())
                self.assertIs(handler, result)
            finally:
                logger.removeHandler(handler)
                handler.close()
                if result is not None and result is not handler:
                    result.close()


class TestJmcomicCompatibility(unittest.TestCase):
    def test_native_async_download_api_is_available(self):
        """The declared jmcomic baseline must provide the 2.7 async download APIs."""
        self.assertTrue(callable(getattr(JmOption, "download_album_async", None)))
        self.assertTrue(callable(getattr(JmOption, "download_photo_async", None)))

    def test_album_comment_api_is_available(self):
        """The declared jmcomic baseline must provide comment pagination entities and APIs."""
        self.assertTrue(callable(getattr(JmcomicClient, "album_pagination", None)))
        self.assertTrue(issubclass(JmAlbumComment, object))
        self.assertTrue(issubclass(JmAlbumCommentPage, object))

    def test_option_schema_covers_upstream_default_client_fields(self):
        """The MCP option schema must accept every client key emitted by JmOption.default()."""
        project_root = Path(__file__).resolve().parents[1]
        schema_path = project_root / "src" / "jmcomic_ai" / "skills" / "jmcomic" / "assets" / "option_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_client = schema["properties"]["client"]
        upstream_client_keys = set(JmOption.default().deconstruct()["client"])

        self.assertFalse(schema_client.get("additionalProperties", True))
        self.assertLessEqual(upstream_client_keys, set(schema_client["properties"]))


class TestAlbumComments(unittest.TestCase):
    def test_nested_comments_are_serialized_for_mcp(self):
        reply_data = {
            "CID": "reply-1",
            "AID": "302820",
            "UID": "2",
            "parent_CID": "root-1",
            "content": "reply content",
            "username": "reply-user",
            "nickname": "Reply User",
            "is_spoiler": False,
            "addtime": "2026-08-03",
            "likes": "2",
        }
        root_comment = JmAlbumComment(
            {
                "CID": "root-1",
                "AID": "302820",
                "UID": "1",
                "parent_CID": "0",
                "content": "root content",
                "username": "root-user",
                "nickname": "Root User",
                "is_spoiler": True,
                "addtime": "2026-08-02",
                "likes": "5",
                "replys": [reply_data],
            }
        )
        comment_page = JmAlbumCommentPage([root_comment], total=11)
        client = Mock()
        client.album_pagination.return_value = comment_page

        service = object.__new__(JmcomicService)
        service.client = client
        service.logger = logging.getLogger("jmcomic_ai.test.comments")

        result = service.get_album_comments("302820", page=2)

        client.album_pagination.assert_called_once_with("302820", page=2)
        self.assertEqual("302820", result["album_id"])
        self.assertEqual(2, result["page"])
        self.assertEqual(10, result["page_size"])
        self.assertEqual(11, result["total"])
        self.assertEqual(2, result["page_count"])
        self.assertEqual(2, result["comment_count"])
        self.assertTrue(result["comments"][0]["is_spoiler"])
        self.assertEqual("reply-1", result["comments"][0]["replies"][0]["comment_id"])
        self.assertEqual(2, result["comments"][0]["replies"][0]["likes"])

    def test_invalid_comment_page_is_rejected(self):
        service = object.__new__(JmcomicService)
        service.logger = logging.getLogger("jmcomic_ai.test.comments.invalid")
        with self.assertRaisesRegex(ValueError, "page must be"):
            service.get_album_comments("302820", page=0)


class TestDownloadTaskLogs(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_album_downloads_write_isolated_task_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.downloads")
            service.logger.setLevel(logging.INFO)
            service.task_log_dir = Path(temp_dir)

            albums = {
                "101": SimpleNamespace(name="Album 101"),
                "202": SimpleNamespace(name="Album 202"),
            }
            client = Mock()
            client.get_album_detail.side_effect = lambda album_id: albums[album_id]
            service.client = client

            class FakeDirRule:
                @staticmethod
                def decide_album_root_dir(album):
                    return Path(temp_dir) / album.name.replace(" ", "-")

            class FakeOption:
                dir_rule = FakeDirRule()

                @staticmethod
                def download_album(album_id, downloader):
                    del downloader
                    with jm_task_context(download_type="album", jm_id=album_id):
                        jm_log("test.download", f"jm-log-{album_id}")
                        service.logger.info(f"service-log-{album_id}")
                        time.sleep(0.01)

            service.option = FakeOption()

            result_101, result_202 = await asyncio.gather(
                service.download_album("101"),
                service.download_album("202"),
            )

            for result, own_id, other_id in (
                (result_101, "101", "202"),
                (result_202, "202", "101"),
            ):
                self.assertEqual("success", result["status"])
                self.assertTrue(result["task_id"].startswith(f"download-album-{own_id}-"))
                log_path = Path(result["log_path"])
                self.assertTrue(log_path.is_file())
                log_text = log_path.read_text(encoding="utf-8")
                self.assertIn(f"jm-log-{own_id}", log_text)
                self.assertIn(f"service-log-{own_id}", log_text)
                self.assertIn("mcp_tool=download-album", log_text)
                self.assertIn(f"album={own_id}", log_text)
                self.assertNotIn(f"jm-log-{other_id}", log_text)
                self.assertNotIn(f"service-log-{other_id}", log_text)

    async def test_failed_photo_download_still_returns_a_task_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.download-failure")
            service.logger.setLevel(logging.INFO)
            service.task_log_dir = Path(temp_dir)
            service.client = Mock()

            class FakeOption:
                @staticmethod
                def download_photo(photo_id, downloader):
                    del photo_id, downloader
                    raise RuntimeError("expected download failure")

            service.option = FakeOption()
            result = await service.download_photo("303")

            self.assertEqual("failed", result["status"])
            self.assertEqual("expected download failure", result["error"])
            log_path = Path(result["log_path"])
            self.assertTrue(log_path.is_file())
            self.assertIn("expected download failure", log_path.read_text(encoding="utf-8"))

    async def test_photo_download_uses_returned_detail_without_refetching(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.download-photo-result")
            service.logger.setLevel(logging.INFO)
            service.task_log_dir = Path(temp_dir)
            service.client = Mock()
            photo = [SimpleNamespace(id="1"), SimpleNamespace(id="2")]
            download_dir = Path(temp_dir) / "photo-404"

            class FakeOption:
                @staticmethod
                def download_photo(photo_id, downloader):
                    del downloader
                    with jm_task_context(download_type="photo", jm_id=photo_id):
                        jm_log("test.download", f"jm-log-{photo_id}")
                    return SimpleNamespace(detail=photo)

                @staticmethod
                def decide_image_save_dir(detail):
                    self.assertIs(photo, detail)
                    return download_dir

            service.option = FakeOption()
            result = await service.download_photo("404")

            self.assertEqual("success", result["status"])
            self.assertEqual(2, result["image_count"])
            self.assertEqual(str(download_dir), result["download_path"])
            service.client.get_photo_detail.assert_not_called()
            log_text = Path(result["log_path"]).read_text(encoding="utf-8")
            self.assertIn("mcp_tool=download-photo", log_text)
            self.assertIn("photo=404", log_text)


if __name__ == "__main__":
    unittest.main()
