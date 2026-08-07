import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jmcomic_ai import updater
from jmcomic_ai.cli import app


class TestUpdateStrategy(unittest.TestCase):
    def test_detects_editable_installation(self):
        package_distribution = Mock()
        package_distribution.read_text.return_value = json.dumps({"dir_info": {"editable": True}})
        with patch.object(updater, "distribution", return_value=package_distribution):
            self.assertEqual("editable", updater.get_installation_source())

    def test_selects_uv_tool_upgrade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir)
            with (
                patch.object(updater, "get_installation_source", return_value="registry"),
                patch.object(updater.shutil, "which", return_value="uv"),
                patch.object(updater, "_get_uv_tool_dir", return_value=tool_dir),
                patch.object(updater, "get_installer", return_value="uv"),
                patch.object(updater.sys, "prefix", str(tool_dir / "jmcomic-ai")),
            ):
                strategy = updater.detect_update_strategy()

        self.assertEqual("uv tool", strategy.name)
        self.assertEqual(("uv", "tool", "upgrade", "jmcomic-ai", "--no-config"), strategy.command)

    def test_selects_current_python_pip(self):
        with (
            patch.object(updater, "get_installation_source", return_value="registry"),
            patch.object(updater.shutil, "which", return_value=None),
            patch.object(updater, "get_installer", return_value="pip"),
            patch.object(updater, "_pip_available", return_value=True),
        ):
            strategy = updater.detect_update_strategy()

        self.assertEqual("pip", strategy.name)
        self.assertEqual(updater.sys.executable, strategy.command[0])

    def test_selects_uv_pip_for_uv_installer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tools"
            environment_dir = Path(temp_dir) / "project-environment"
            with (
                patch.object(updater, "get_installation_source", return_value="registry"),
                patch.object(updater.shutil, "which", return_value="/usr/bin/uv"),
                patch.object(updater, "_get_uv_tool_dir", return_value=tool_dir),
                patch.object(updater, "get_installer", return_value="uv"),
                patch.object(updater.sys, "prefix", str(environment_dir)),
            ):
                strategy = updater.detect_update_strategy()

        self.assertEqual("uv pip", strategy.name)
        self.assertEqual(("/usr/bin/uv", "pip", "install"), strategy.command[:3])

    def test_refuses_editable_installation(self):
        with patch.object(updater, "get_installation_source", return_value="editable"):
            with self.assertRaisesRegex(updater.UpdateError, "Editable installation"):
                updater.detect_update_strategy()

    def test_refuses_uv_when_tool_directory_is_unknown(self):
        with (
            patch.object(updater, "get_installation_source", return_value="registry"),
            patch.object(updater, "get_installer", return_value="uv"),
            patch.object(updater.shutil, "which", return_value="uv"),
            patch.object(updater, "_get_uv_tool_dir", return_value=None),
        ):
            with self.assertRaisesRegex(updater.UpdateError, "Cannot determine"):
                updater.detect_update_strategy()

    def test_refuses_unknown_installer(self):
        with (
            patch.object(updater, "get_installation_source", return_value="registry"),
            patch.object(updater, "get_installer", return_value=None),
            patch.object(updater.shutil, "which", return_value="uv"),
        ):
            with self.assertRaisesRegex(updater.UpdateError, "unknown package installer"):
                updater.detect_update_strategy()

    def test_windows_update_is_scheduled_after_exit(self):
        strategy = updater.UpdateStrategy("pip", ("python", "-m", "pip"), ("python", "-m", "pip"))
        with (
            patch.object(updater, "_is_windows", return_value=True),
            patch.object(updater, "_schedule_windows_update") as schedule_update,
        ):
            result = updater.run_update(strategy)

        self.assertTrue(result.scheduled)
        schedule_update.assert_called_once_with(strategy)

    def test_windows_scheduler_builds_encoded_powershell_command(self):
        strategy = updater.UpdateStrategy(
            "pip",
            ("python.exe", "-m", "pip", "space value", "quote'value"),
            ("python", "-m", "pip"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(updater.shutil, "which", return_value="powershell.exe"),
                patch.object(updater.Path, "home", return_value=Path(temp_dir)),
                patch.object(updater.os, "getpid", return_value=123),
                patch.object(updater.subprocess, "Popen") as popen,
            ):
                updater._schedule_windows_update(strategy)

        command = popen.call_args.args[0]
        script = base64.b64decode(command[-1]).decode("utf-16-le")
        self.assertTrue(script.startswith("Wait-Process -Id 123"))
        self.assertIn("'space value'", script)
        self.assertIn("'quote''value'", script)
        self.assertIn("update.log", script)
        self.assertEqual(updater.subprocess.DEVNULL, popen.call_args.kwargs["stdout"])


class TestUpdateCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.strategy = updater.UpdateStrategy(
            name="pip",
            command=("python", "-m", "pip", "install", "--upgrade", "jmcomic-ai"),
            display_command=("python", "-m", "pip", "install", "--upgrade", "jmcomic-ai"),
        )

    def test_root_help_lists_update(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(0, result.exit_code, result.output)
        self.assertIn("update", result.output)

    def test_update_dry_run_does_not_execute(self):
        with (
            patch.object(updater, "detect_update_strategy", return_value=self.strategy),
            patch.object(updater, "run_update") as run_update,
        ):
            result = self.runner.invoke(app, ["update", "--dry-run"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertIn("Update method: pip", result.output)
        self.assertIn("no changes were made", result.output)
        run_update.assert_not_called()

    def test_update_success(self):
        with (
            patch.object(updater, "detect_update_strategy", return_value=self.strategy),
            patch.object(updater, "run_update", return_value=updater.UpdateResult(0)) as run_update,
        ):
            result = self.runner.invoke(app, ["update"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertIn("Update completed", result.output)
        run_update.assert_called_once_with(self.strategy)

    def test_update_failure_uses_nonzero_exit(self):
        with (
            patch.object(updater, "detect_update_strategy", return_value=self.strategy),
            patch.object(updater, "run_update", return_value=updater.UpdateResult(7)),
        ):
            result = self.runner.invoke(app, ["update"])

        self.assertEqual(7, result.exit_code)
        self.assertIn("Update failed with exit code 7", result.output)

    def test_windows_update_reports_scheduled(self):
        with (
            patch.object(updater, "detect_update_strategy", return_value=self.strategy),
            patch.object(updater, "run_update", return_value=updater.UpdateResult(0, scheduled=True)),
        ):
            result = self.runner.invoke(app, ["update"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertIn("Update scheduled", result.output)

    def test_update_rejects_editable_installation(self):
        with patch.object(
            updater,
            "detect_update_strategy",
            side_effect=updater.UpdateError("Editable installation detected"),
        ):
            result = self.runner.invoke(app, ["update"])

        self.assertEqual(1, result.exit_code)
        self.assertIn("Editable installation detected", result.output)


if __name__ == "__main__":
    unittest.main()
