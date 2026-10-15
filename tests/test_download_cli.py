"""User-visible failures from shared download output and installed scripts."""

import asyncio
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jmcomic import DownloadCancelledException
from typer.testing import CliRunner

from jmcomic_ai.cli import app
from jmcomic_ai.core import JmcomicService
from jmcomic_ai.download_cli import print_result
from jmcomic_ai.skills.jmcomic.scripts import batch_download, download_photo


class TestBackgroundScriptErrors(unittest.TestCase):
    def test_invalid_request_and_io_failure_are_json_errors(self):
        for module, kind in ((batch_download, "album"), (download_photo, "photo")):
            for error_type in (ValueError, OSError):
                with self.subTest(script=module.__name__, error=error_type.__name__):
                    output = io.StringIO()
                    message = "Controlled background request failure"
                    with (
                        patch("sys.argv", ["script", "--ids", "123", "--background", "--json"]),
                        patch("jmcomic_ai.background.from_arguments", side_effect=error_type(message)) as launch,
                        patch.object(module, "JmcomicService") as service,
                        redirect_stdout(output),
                        self.assertRaises(SystemExit) as stopped,
                    ):
                        asyncio.run(module.main())
                    self.assertEqual(1, stopped.exception.code)
                    self.assertEqual({"status": "error", "error": message}, json.loads(output.getvalue()))
                    self.assertEqual((["123"], kind), launch.call_args.args[1:])
                    service.assert_not_called()


class TestScriptInputErrors(unittest.TestCase):
    def test_input_failures_are_json_errors_before_any_download_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_file = str(Path(directory) / "missing-ids.txt")
            cases = (
                ("invalid_ids", ["--ids", "abc"]),
                ("missing_file", ["--file", missing_file]),
                ("empty_ids", ["--ids", " , , "]),
                ("details_without_plan", ["--ids", "123", "--details"]),
            )
            for module in (batch_download, download_photo):
                for background in (False, True):
                    for case, arguments in cases:
                        with self.subTest(script=module.__name__, background=background, case=case):
                            output = io.StringIO()
                            argv = ["script", *arguments, "--json"]
                            if background:
                                argv.append("--background")
                            with (
                                patch("sys.argv", argv),
                                patch("jmcomic_ai.background.from_arguments") as launch,
                                patch.object(module, "JmcomicService") as service,
                                redirect_stdout(output),
                                self.assertRaises(SystemExit) as stopped,
                            ):
                                asyncio.run(module.main())
                            self.assertEqual(1, stopped.exception.code)
                            result = json.loads(output.getvalue())
                            self.assertEqual("error", result["status"])
                            self.assertTrue(result["error"])
                            launch.assert_not_called()
                            service.assert_not_called()

    def test_bom_id_files_normalize_ids_and_ignore_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "ids.txt"
            input_path.write_text(
                "  # comment\nJM123\nhttps://18comic.vip/album/456\n\n", encoding="utf-8-sig"
            )
            args = SimpleNamespace(ids=None, file=str(input_path))
            for loader in (batch_download.load_album_ids, download_photo.load_photo_ids):
                with self.subTest(loader=loader.__name__):
                    self.assertEqual(["123", "456"], loader(args))


class TestConfigurationInputErrors(unittest.TestCase):
    def test_malformed_yaml_is_a_json_error_without_configuration_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            option = root / "option.yml"
            canary = "SYNTHETIC_TEST_ONLY_CONFIG_VALUE"
            option.write_text(f"client: [\n  {canary}: invalid\n", encoding="utf-8")
            with (
                patch.dict(os.environ, {
                    "JM_LOG_PATH": str(root / "service.log"),
                    "JM_TASK_LOG_DIR": str(root / "tasks"),
                }),
                patch.object(JmcomicService, "_setup_logging", autospec=True,
                             side_effect=lambda service, log_path: setattr(service, "logger", Mock())),
                patch.object(JmcomicService, "get_client") as client,
            ):
                for module in (batch_download, download_photo):
                    with self.subTest(script=module.__name__):
                        output = io.StringIO()
                        with (
                            patch("sys.argv", ["script", "--ids", "123", "--option", str(option), "--json"]),
                            redirect_stdout(output),
                            self.assertRaises(SystemExit) as stopped,
                        ):
                            asyncio.run(module.main())
                        self.assertEqual(1, stopped.exception.code)
                        payload = json.loads(output.getvalue())
                        self.assertEqual("error", payload["status"])
                        self.assertTrue(payload["error"])
                        self.assertNotIn(canary, output.getvalue())
                cli = CliRunner().invoke(app, [
                    "download", "--ids", "123", "--option", str(option), "--plan", "--json"
                ])
                self.assertEqual(1, cli.exit_code, cli.output)
                payload = json.loads(cli.stdout)
                self.assertEqual("error", payload["status"])
                self.assertTrue(payload["error"])
                self.assertNotIn(canary, cli.output)
                client.assert_not_called()

    def test_configuration_initialization_preserves_download_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            option = root / "option.yml"
            option.write_text("{}\n", encoding="utf-8")
            cancellation = DownloadCancelledException("Controlled configuration cancellation")
            with (
                patch.dict(os.environ, {
                    "JM_LOG_PATH": str(root / "service.log"),
                    "JM_TASK_LOG_DIR": str(root / "tasks"),
                }),
                patch.object(JmcomicService, "_setup_logging", autospec=True,
                             side_effect=lambda service, log_path: setattr(service, "logger", Mock())),
                patch("jmcomic_ai.core.create_option_by_file", side_effect=cancellation),
                patch.object(JmcomicService, "get_client") as client,
                self.assertRaises(DownloadCancelledException) as stopped,
            ):
                JmcomicService(option_path=str(option))
            self.assertIs(cancellation, stopped.exception)
            client.assert_not_called()


class TestPlanOutput(unittest.TestCase):
    def test_partial_and_failed_plans_show_per_item_details(self):
        failed = {"id": "2", "status": "failed", "error": "Controlled metadata lookup failure"}
        succeeded = {
            "id": "1", "status": "success", "title": "Example title", "page_count": 25,
            "chapters": [{"id": "11", "title": "Part 1"}],
        }
        for status, details in (("partial", [succeeded, failed]), ("failed", [failed])):
            result = {
                "status": status, "kind": "album", "ids": [detail["id"] for detail in details],
                "base_dir": "downloads", "details": details, "network_requested": True,
            }
            with self.subTest(status=status):
                output = io.StringIO()
                with redirect_stdout(output):
                    print_result(result)
                rendered = output.getvalue()
                self.assertIn(status, rendered)
                self.assertIn("2", rendered)
                self.assertIn(failed["error"], rendered)
                if status == "partial":
                    for visible in ("Example title", "25", "11", "Part 1"):
                        self.assertIn(visible, rendered)

    def test_json_plan_output_preserves_all_details(self):
        result = {
            "status": "failed", "ids": ["2"], "details": [
                {"id": "2", "status": "failed", "error": "Controlled metadata lookup failure"}
            ],
        }
        output = io.StringIO()
        with redirect_stdout(output):
            print_result(result, as_json=True)
        self.assertEqual(result, json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
