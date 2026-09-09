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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Lock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jmcomic import (
    JmAlbumComment,
    JmAlbumCommentPage,
    JmApiClient,
    JmApiResp,
    JmcomicClient,
    JmModuleConfig,
    JmOption,
    jm_log,
    jm_task_context,
)

from jmcomic_ai.core import (
    GLOBAL_LOG_HANDLER_NAME,
    ORDER_BY_MAP,
    TIME_RANGE_MAP,
    JmcomicService,
    _configure_logger_file_only,
    _get_global_file_handler,
    _serialize_download_result,
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

    def test_option_schema_exposes_upstream_download_progress_plugin(self):
        project_root = Path(__file__).resolve().parents[1]
        schema_path = project_root / "src" / "jmcomic_ai" / "skills" / "jmcomic" / "assets" / "option_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertIn("download_progress", schema["definitions"]["plugin"]["properties"]["plugin"]["enum"])
        kwargs = schema["definitions"]["download_progress_plugin"]["allOf"][1]["properties"]["kwargs"]
        self.assertEqual(1, kwargs["properties"]["terminal_log_lines"]["minimum"])
        self.assertFalse(kwargs["additionalProperties"])

        from jsonschema import Draft7Validator

        validator = Draft7Validator(schema)
        valid_progress = {
            "plugins": {
                "after_init": [
                    {
                        "plugin": "download_progress",
                        "kwargs": {"log_file": "progress.log", "terminal_log_lines": 6},
                    }
                ]
            }
        }
        invalid_progress = {
            "plugins": {"after_init": [{"plugin": "download_progress", "kwargs": {"unknown_option": True}}]}
        }
        other_plugin = {"plugins": {"after_init": [{"plugin": "usage_log", "kwargs": {"interval": 1}}]}}

        self.assertFalse(list(validator.iter_errors(valid_progress)))
        self.assertTrue(list(validator.iter_errors(invalid_progress)))
        self.assertFalse(list(validator.iter_errors(other_plugin)))

    def test_download_result_paths_are_resolved(self):
        result = SimpleNamespace(
            detail=SimpleNamespace(save_path=Path("downloads") / "album-1"),
            duration=1.5,
            manifest=SimpleNamespace(
                image_filepath_list=[Path("downloads") / "album-1" / "1.jpg"],
                export_filepath_dict={"pdf": [Path("downloads") / "album-1.pdf"]},
            ),
        )

        serialized = _serialize_download_result(result)

        self.assertEqual(str((Path("downloads") / "album-1").resolve()), serialized["download_path"])
        self.assertEqual(
            [str((Path("downloads") / "album-1" / "1.jpg").resolve())],
            serialized["image_paths"],
        )
        self.assertEqual(
            {"pdf": [str((Path("downloads") / "album-1.pdf").resolve())]},
            serialized["export_files"],
        )


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
        comment_page = JmAlbumCommentPage([root_comment], total=11, page_number=3)
        client = Mock()
        client.album_pagination.return_value = comment_page

        service = object.__new__(JmcomicService)
        service.client = client
        service.logger = logging.getLogger("jmcomic_ai.test.comments")

        result = service.get_album_comments("302820", page=2)

        client.album_pagination.assert_called_once_with("302820", page=2)
        self.assertEqual("302820", result["album_id"])
        self.assertEqual(3, result["page"])
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

    def test_forum_comments_include_source_album_and_upstream_page(self):
        comment = JmAlbumComment(
            {
                "CID": "forum-1",
                "AID": "654321",
                "UID": "7",
                "content": "site-wide comment",
                "username": "reader",
                "nickname": "Reader",
                "is_spoiler": False,
                "likes": "4",
            }
        )
        comment_page = JmAlbumCommentPage([comment], total=21, page_number=4)
        client = Mock()
        client.forum_pagination.return_value = comment_page
        service = object.__new__(JmcomicService)
        service.client = client
        service.logger = logging.getLogger("jmcomic_ai.test.comments.forum")

        result = service.get_forum_comments(page=2)

        client.forum_pagination.assert_called_once_with(page=2)
        self.assertEqual(4, result["page"])
        self.assertEqual("654321", result["comments"][0]["album_id"])
        self.assertEqual(4, result["comments"][0]["likes"])

    def test_search_page_uses_upstream_page_number(self):
        service = object.__new__(JmcomicService)
        search_page = SimpleNamespace(content=[], total=0, page_number=6)

        result = service._parse_search_page(search_page)

        self.assertEqual(6, result["page"])


class TestFavorites(unittest.TestCase):
    @staticmethod
    def response(payload):
        return SimpleNamespace(
            status_code=200,
            content=b"response",
            text=json.dumps({"code": 200, "data": json.dumps(payload)}),
        )

    def setUp(self):
        self.service = object.__new__(JmcomicService)
        self.service.logger = Mock()
        self.client = object.__new__(JmApiClient)
        self.service.client = self.client
        favorite_page = {
            "list": [{"id": "123", "name": "Example album"}],
            "folder_list": [{"FID": "4", "name": "Example folder"}],
            "total": "1",
            "count": 20,
        }

        self.client.get = Mock(return_value=self.response(favorite_page))
        self.client.post = Mock(return_value=self.response({"status": "ok", "msg": "漫畫添加到您最喜愛的清單！"}))
        decoded_data = patch.object(JmApiResp, "decoded_data", property(lambda response: response.encoded_data))
        decoded_data.start()
        self.addCleanup(decoded_data.stop)

    def test_favorite_directory_and_browse_responses(self):
        self.assertEqual({"folders": [{"id": "4", "name": "Example folder"}]}, self.service.get_favorite_folders())
        result = self.service.browse_favorite_albums(folder_id="4")

        self.assertEqual((1, 1, "4"), (result["total_count"], result["page"], result["folder_id"]))
        self.assertEqual(1, len(result["albums"]))
        album = result["albums"][0]
        self.assertEqual(("123", "Example album", []), (album["id"], album["title"], album["tags"]))
        self.assertTrue(album["cover_url"])

    def test_add_favorite_success_response(self):
        self.client.get.return_value = self.response({"id": 456, "is_favorite": False})

        result = self.service.add_favorite_album("456")

        self.assertEqual(
            {"status": "success", "album_id": "456", "folder_id": "0", "message": "漫畫添加到您最喜愛的清單！"},
            result,
        )

    def test_add_existing_favorite_response(self):
        self.client.get.return_value = self.response({"id": 123, "is_favorite": True})
        self.client.post.return_value = self.response({"status": "ok", "msg": "已移除收藏"})

        result = self.service.add_favorite_album("123")

        self.assertEqual(
            {"status": "success", "album_id": "123", "folder_id": "0", "message": "已收藏，无需重复添加"},
            result,
        )

    def test_add_favorite_list_response_returns_error(self):
        self.client.post.return_value = self.client.get.return_value
        self.client.get.return_value = self.response({"id": 456, "is_favorite": False})

        result = self.service.add_favorite_album("456")

        self.assertEqual({"status": "error", "album_id": "456", "folder_id": "0", "message": "'status'"}, result)

    def test_remove_favorite_success_response(self):
        self.client.get.return_value = self.response({"id": 456, "is_favorite": True})
        self.client.post.return_value = self.response({"status": "ok", "msg": "Favorite removed"})

        result = self.service.remove_favorite_album("JM456")

        self.assertEqual(
            {"status": "success", "album_id": "456", "folder_id": "0", "message": "Favorite removed"},
            result,
        )

    def test_remove_missing_favorite_response(self):
        self.client.get.return_value = self.response({"id": 456, "is_favorite": False})

        result = self.service.remove_favorite_album("456")

        self.assertEqual(
            {"status": "success", "album_id": "456", "folder_id": "0", "message": "未收藏，无需移除"},
            result,
        )
        self.assertEqual(1, self.client.get.call_count)
        self.client.post.assert_not_called()

    def test_concurrent_adds_keep_album_favorited(self):
        """Concurrent callers sharing an account only toggle the favorite once."""
        reads = Barrier(2)
        state_lock = Lock()
        favorite = False

        def read_favorite(*args, **kwargs):
            with state_lock:
                is_favorite = favorite
            try:
                reads.wait(timeout=0.5)
            except BrokenBarrierError:
                pass
            return self.response({"id": 123, "is_favorite": is_favorite})

        def toggle_favorite(*args, **kwargs):
            nonlocal favorite
            with state_lock:
                favorite = not favorite
            return self.response({"status": "ok", "msg": "Favorite toggled"})

        self.client.get.side_effect = read_favorite
        self.client.post.side_effect = toggle_favorite
        other_service = object.__new__(JmcomicService)
        other_service.logger = Mock()
        other_service.client = object.__new__(JmApiClient)
        other_service.client.get = self.client.get
        other_service.client.post = self.client.post

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.service.add_favorite_album, "123"),
                executor.submit(other_service.add_favorite_album, "JM123"),
            ]
            results = [future.result(timeout=5) for future in futures]

        self.assertTrue(favorite)
        self.client.post.assert_called_once()
        self.assertTrue(all(result["status"] == "success" for result in results))
        self.assertEqual(1, sum(result["message"] == "已收藏，无需重复添加" for result in results))


class TestPostProcessCompatibility(unittest.TestCase):
    def test_post_process_returns_registered_plugin_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            album = Mock()
            album.__iter__ = Mock(return_value=iter([]))
            photo = Mock()
            album.__iter__ = Mock(return_value=iter([photo]))
            image_dir = Path(temp_dir) / "images"
            image_dir.mkdir()
            (image_dir / "1.jpg").write_bytes(b"image")
            output_path = Path(temp_dir) / "exports" / "album.pdf"

            class FakePlugin:
                @classmethod
                def build(cls, option):
                    del option
                    return cls()

                @staticmethod
                def invoke(album, downloader, **kwargs):
                    del kwargs
                    output_path.parent.mkdir()
                    output_path.write_bytes(b"pdf")
                    downloader.record_export_filepath(album, output_path)

            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.post-process")
            service.client = Mock()
            service.client.get_album_detail.return_value = album
            service.option = Mock()
            service.option.decide_image_save_dir.return_value = image_dir

            with patch.dict(JmModuleConfig.REGISTRY_PLUGIN, {"img2pdf": FakePlugin}):
                result = service.post_process("123", "img2pdf")

            self.assertEqual("success", result["status"])
            self.assertEqual(str(output_path.resolve()), result["output_path"])
            self.assertEqual([str(output_path.resolve())], result["output_paths"])
            self.assertFalse(result["is_directory"])

    def test_album_zip_uses_album_filename_rule_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            album = Mock()
            photo = Mock()
            album.__iter__ = Mock(return_value=iter([photo]))
            image_dir = Path(temp_dir) / "images"
            image_dir.mkdir()
            (image_dir / "1.jpg").write_bytes(b"image")
            captured_params = {}

            class FakePlugin:
                @classmethod
                def build(cls, option):
                    del option
                    return cls()

                @staticmethod
                def invoke(album, downloader, **kwargs):
                    captured_params.update(kwargs)
                    output_path = Path(temp_dir) / "album.zip"
                    output_path.write_bytes(b"zip")
                    downloader.record_export_filepath(album, output_path)

            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.post-process.zip")
            service.client = Mock()
            service.client.get_album_detail.return_value = album
            service.option = Mock()
            service.option.decide_image_save_dir.return_value = image_dir

            with patch.dict(JmModuleConfig.REGISTRY_PLUGIN, {"zip": FakePlugin}):
                result = service.post_process("123", "zip")

            self.assertEqual("success", result["status"])
            self.assertEqual("Aid", captured_params["filename_rule"])

    def test_post_process_expands_user_output_paths_before_plugin_invocation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            album = Mock()
            photo = Mock()
            album.__iter__ = Mock(return_value=iter([photo]))
            image_dir = Path(temp_dir) / "images"
            image_dir.mkdir()
            (image_dir / "1.jpg").write_bytes(b"image")
            captured_params = {}

            class FakePlugin:
                @classmethod
                def build(cls, option):
                    del option
                    return cls()

                @staticmethod
                def invoke(album, downloader, **kwargs):
                    captured_params.update(kwargs)
                    output_path = Path(kwargs["dir_rule"]["base_dir"]) / "album.pdf"
                    output_path.parent.mkdir(parents=True)
                    output_path.write_bytes(b"pdf")
                    downloader.record_export_filepath(album, output_path)

            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.post-process.user-path")
            service.client = Mock()
            service.client.get_album_detail.return_value = album
            service.option = Mock()
            service.option.decide_image_save_dir.return_value = image_dir
            params = {
                "dir_rule": {"rule": "Bd", "base_dir": "~/jmcomic-review-output"},
                "pdf_dir": "~/jmcomic-review-pdf",
                "img_dir": "~/jmcomic-review-images",
                "zip_dir": "~/jmcomic-review-zips",
            }

            fake_home = Path(temp_dir) / "home"
            with (
                patch.dict(os.environ, {"HOME": str(fake_home)}),
                patch.dict(JmModuleConfig.REGISTRY_PLUGIN, {"img2pdf": FakePlugin}),
            ):
                result = service.post_process("123", "img2pdf", params)

                expected_base_dir = str(Path("~/jmcomic-review-output").expanduser())
                expected_pdf_dir = str(Path("~/jmcomic-review-pdf").expanduser())
                expected_img_dir = str(Path("~/jmcomic-review-images").expanduser())
                expected_zip_dir = str(Path("~/jmcomic-review-zips").expanduser())

            self.assertEqual("success", result["status"])
            self.assertEqual(expected_base_dir, captured_params["dir_rule"]["base_dir"])
            self.assertEqual(expected_pdf_dir, captured_params["pdf_dir"])
            self.assertEqual(expected_img_dir, captured_params["img_dir"])
            self.assertEqual(expected_zip_dir, captured_params["zip_dir"])
            self.assertEqual(
                str((Path(expected_base_dir) / "album.pdf").resolve()),
                result["output_path"],
            )
            self.assertEqual("~/jmcomic-review-output", params["dir_rule"]["base_dir"])


class TestDownloadTaskLogs(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_album_downloads_write_isolated_task_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = object.__new__(JmcomicService)
            service.logger = logging.getLogger("jmcomic_ai.test.downloads")
            service.logger.setLevel(logging.INFO)
            service.task_log_dir = Path(temp_dir)
            service.client = Mock()

            class FakeOption:
                @staticmethod
                def download_album(album_id, downloader):
                    del downloader
                    with jm_task_context(download_type="album", jm_id=album_id):
                        jm_log("test.download", f"jm-log-{album_id}")
                        service.logger.info(f"service-log-{album_id}")
                        time.sleep(0.01)
                    detail = SimpleNamespace(
                        name=f"Album {album_id}",
                        save_path=Path(temp_dir) / f"album-{album_id}",
                    )
                    manifest = SimpleNamespace(
                        image_filepath_list=[Path(temp_dir) / f"{album_id}-1.jpg"],
                        export_filepath_dict={"pdf": [Path(temp_dir) / f"{album_id}.pdf"]},
                    )
                    return SimpleNamespace(detail=detail, manifest=manifest, duration=0.25)

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
                self.assertEqual(f"Album {own_id}", result["title"])
                self.assertEqual(str((Path(temp_dir) / f"album-{own_id}").resolve()), result["download_path"])
                self.assertEqual(0.25, result["duration"])
                self.assertEqual([str((Path(temp_dir) / f"{own_id}-1.jpg").resolve())], result["image_paths"])
                self.assertEqual({"pdf": [str((Path(temp_dir) / f"{own_id}.pdf").resolve())]}, result["export_files"])
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
            service.client.get_album_detail.assert_not_called()

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
            self.assertEqual("", result["download_path"])
            self.assertIsNone(result["duration"])
            self.assertEqual([], result["image_paths"])
            self.assertEqual({}, result["export_files"])
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
            photo = SimpleNamespace(
                save_path=Path(temp_dir) / "photo-404",
                __len__=lambda: 99,
            )
            download_dir = Path(temp_dir) / "photo-404"
            image_paths = [download_dir / "1.jpg", download_dir / "2.jpg"]
            export_path = Path(temp_dir) / "photo-404.zip"

            class FakeOption:
                @staticmethod
                def download_photo(photo_id, downloader):
                    del downloader
                    with jm_task_context(download_type="photo", jm_id=photo_id):
                        jm_log("test.download", f"jm-log-{photo_id}")
                    manifest = SimpleNamespace(
                        image_filepath_list=image_paths,
                        export_filepath_dict={"zip": [export_path]},
                    )
                    return SimpleNamespace(detail=photo, manifest=manifest, duration=1.5)

            service.option = FakeOption()
            result = await service.download_photo("404")

            self.assertEqual("success", result["status"])
            self.assertEqual(2, result["image_count"])
            self.assertEqual(str(download_dir.resolve()), result["download_path"])
            self.assertEqual(1.5, result["duration"])
            self.assertEqual([str(path.resolve()) for path in image_paths], result["image_paths"])
            self.assertEqual({"zip": [str(export_path.resolve())]}, result["export_files"])
            service.client.get_photo_detail.assert_not_called()
            log_text = Path(result["log_path"]).read_text(encoding="utf-8")
            self.assertIn("mcp_tool=download-photo", log_text)
            self.assertIn("photo=404", log_text)


if __name__ == "__main__":
    unittest.main()
