"""Regression tests for JMComic Skill script edge cases."""

import argparse
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from jmcomic_ai.core import JmcomicService
from jmcomic_ai.skills.jmcomic.scripts import batch_download, doctor, download_covers, download_photo
from jmcomic_ai.skills.jmcomic.scripts._script_utils import import_error_message


class TestImportErrors(unittest.TestCase):
    def test_missing_target_package_is_reported_as_not_installed(self):
        error = ModuleNotFoundError("missing", name="jmcomic_ai")

        message = import_error_message(error, "jmcomic_ai", "Install it.")

        self.assertEqual(message, "Error: jmcomic_ai not found. Install it.")

    def test_missing_transitive_dependency_is_reported_by_name(self):
        error = ModuleNotFoundError("missing", name="yaml")

        message = import_error_message(error, "jmcomic_ai", "Install it.")

        self.assertIn("dependency 'yaml' is unavailable", message)


class TestIdParsing(unittest.TestCase):
    def test_file_inputs_ignore_indented_comments_and_normalize_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "ids.txt"
            input_path.write_text(
                "  # ignored comment\nJM123\nhttps://18comic.vip/album/456\n\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(ids=None, file=str(input_path))

            self.assertEqual(batch_download.load_album_ids(args), ["123", "456"])
            self.assertEqual(download_covers.load_album_ids(args), ["123", "456"])

    def test_photo_file_inputs_use_jmcomic_parser(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "ids.txt"
            input_path.write_text("  # ignored comment\nJM789\nhttps://18comic.vip/photo/456\n", encoding="utf-8")
            args = argparse.Namespace(ids=None, file=str(input_path))

            self.assertEqual(download_photo.load_photo_ids(args), ["789", "456"])


class TestCancellation(unittest.TestCase):
    def test_batch_download_propagates_cancellation(self):
        args = SimpleNamespace(ids="1", file=None, option=None)
        service = Mock()
        service.download_album = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch.object(batch_download, "parse_args", return_value=args),
            patch.object(batch_download, "JmcomicService", return_value=service),
            self.assertRaises(asyncio.CancelledError),
        ):
            asyncio.run(batch_download.main())

    def test_photo_download_propagates_cancellation(self):
        args = SimpleNamespace(ids="1", file=None, option=None)
        service = Mock()
        service.download_photo = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch.object(download_photo, "parse_args", return_value=args),
            patch.object(download_photo, "JmcomicService", return_value=service),
            self.assertRaises(asyncio.CancelledError),
        ):
            asyncio.run(download_photo.main())


class TestCoverOutput(unittest.TestCase):
    def test_script_passes_custom_output_directory_to_service(self):
        service = Mock()
        service.download_cover.return_value = "ok"
        output_dir = Path("custom") / "my_covers"

        success_count, failed_ids = download_covers.download_covers(service, ["123"], output_dir)

        self.assertEqual((success_count, failed_ids), (1, []))
        service.download_cover.assert_called_once_with("123", output_dir=str(output_dir))

    def test_service_creates_and_uses_custom_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "nested" / "my_covers"
            client = Mock()
            service = JmcomicService.__new__(JmcomicService)
            service.get_client = Mock(return_value=client)
            service.logger = Mock()

            message = service.download_cover("123", output_dir=str(output_dir))

            client.download_album_cover.assert_called_once_with("123", str(output_dir / "123.jpg"))
            self.assertTrue(output_dir.is_dir())
            self.assertIn(str(output_dir / "123.jpg"), message)


class TestDoctorDomainFiltering(unittest.TestCase):
    def test_only_telegram_links_are_filtered(self):
        self.assertTrue(doctor.is_telegram_link("t.me/hcomic18"))
        self.assertTrue(doctor.is_telegram_link("https://t.me/hcomic18"))
        self.assertFalse(doctor.is_telegram_link("jm-88.cc/ZNPJam"))
        self.assertFalse(doctor.is_telegram_link("18comic.vip"))

    def test_network_check_skips_telegram_but_tests_path_candidate(self):
        import jmcomic

        tested_domains = []
        option = Mock()

        def new_client(*, impl, domain_list):
            self.assertEqual(impl, "html")
            tested_domains.extend(domain_list)
            return Mock()

        def launch(*, iter_objs, apply_each_obj_func):
            for domain in iter_objs:
                apply_each_obj_func(domain)

        option.new_jm_client.side_effect = new_client
        discovered = {"18comic.vip", "jm-88.cc/ZNPJam", "t.me/hcomic18"}

        with (
            patch.object(jmcomic.JmModuleConfig, "get_html_domain_all", return_value=discovered),
            patch.object(jmcomic.JmOption, "default", return_value=option),
            patch.object(jmcomic, "disable_jm_log"),
            patch.object(jmcomic, "multi_thread_launcher", side_effect=launch),
        ):
            self.assertTrue(doctor.check_network())

        self.assertCountEqual(tested_domains, ["18comic.vip", "jm-88.cc/ZNPJam"])

    def test_network_check_reports_domain_discovery_error(self):
        import jmcomic

        with (
            patch.object(
                jmcomic.JmModuleConfig,
                "get_html_domain_all",
                side_effect=RuntimeError("publish page unavailable"),
            ),
            patch.object(jmcomic.JmOption, "default", return_value=Mock()),
            patch.object(jmcomic, "disable_jm_log"),
            patch("builtins.print") as print_mock,
        ):
            self.assertFalse(doctor.check_network())

        output = "\n".join(" ".join(map(str, call.args)) for call in print_mock.call_args_list)
        self.assertIn("Domain discovery failed: publish page unavailable", output)


if __name__ == "__main__":
    unittest.main()
