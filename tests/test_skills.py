"""Tests for cross-platform Agent Skills installation."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from jmcomic_ai.cli import app
from jmcomic_ai.skills.manager import SkillManager


class TestSkillPlatformTargets(unittest.TestCase):
    def test_platform_target_directories(self):
        home_dir = Path("/test-home")

        self.assertEqual(
            {"claude": home_dir / ".claude" / "skills"},
            SkillManager.get_platform_target_dirs("claude", home_dir),
        )
        self.assertEqual(
            {"codex": home_dir / ".agents" / "skills"},
            SkillManager.get_platform_target_dirs("codex", home_dir),
        )
        self.assertEqual(
            {"gemini": home_dir / ".gemini" / "skills"},
            SkillManager.get_platform_target_dirs("gemini", home_dir),
        )

    def test_all_platform_target_directories(self):
        home_dir = Path("/test-home")
        targets = SkillManager.get_platform_target_dirs("all", home_dir)

        self.assertEqual(["claude", "codex", "gemini"], list(targets))
        self.assertEqual(home_dir / ".claude" / "skills", targets["claude"])
        self.assertEqual(home_dir / ".agents" / "skills", targets["codex"])
        self.assertEqual(home_dir / ".gemini" / "skills", targets["gemini"])

    def test_unknown_platform_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported platform"):
            SkillManager.get_platform_target_dirs("unknown", Path("/test-home"))


class TestSkillPlatformCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_non_interactive_install_remains_claude_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            with patch("pathlib.Path.home", return_value=home_dir):
                result = self.runner.invoke(app, ["skills", "install", "--yes"])

            self.assertEqual(0, result.exit_code, result.output)
            self.assertTrue((home_dir / ".claude" / "skills" / "jmcomic" / "SKILL.md").is_file())
            self.assertTrue((home_dir / ".claude" / "skills" / "jmcomic" / "scripts" / "album_comments.py").is_file())
            self.assertFalse((home_dir / ".agents" / "skills" / "jmcomic").exists())
            self.assertFalse((home_dir / ".gemini" / "skills" / "jmcomic").exists())

    def test_interactive_install_can_select_all_platforms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            with patch("pathlib.Path.home", return_value=home_dir):
                result = self.runner.invoke(app, ["skills", "install"], input="4\ny\n")

            self.assertEqual(0, result.exit_code, result.output)
            self.assertIn("Select platforms to install", result.output)
            for target_dir in SkillManager.get_platform_target_dirs("all", home_dir).values():
                self.assertTrue((target_dir / "jmcomic" / "SKILL.md").is_file())

    def test_short_install_and_uninstall_flags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            claude_skill_dir = home_dir / ".claude" / "skills" / "jmcomic"
            with patch("pathlib.Path.home", return_value=home_dir):
                install_result = self.runner.invoke(app, ["skills", "-i"], input="1\ny\n")
                self.assertEqual(0, install_result.exit_code, install_result.output)
                self.assertTrue((claude_skill_dir / "SKILL.md").is_file())

                uninstall_result = self.runner.invoke(app, ["skills", "-u"], input="1\ny\n")
                self.assertEqual(0, uninstall_result.exit_code, uninstall_result.output)
                self.assertFalse(claude_skill_dir.exists())

    def test_short_install_and_uninstall_are_mutually_exclusive(self):
        result = self.runner.invoke(app, ["skills", "-i", "-u"])

        self.assertNotEqual(0, result.exit_code)
        self.assertIn("Choose either", result.output)

    def test_install_and_uninstall_all_platforms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            with patch("pathlib.Path.home", return_value=home_dir):
                install_result = self.runner.invoke(app, ["skills", "install", "--platform", "all", "--yes"])

                self.assertEqual(0, install_result.exit_code, install_result.output)
                for target_dir in SkillManager.get_platform_target_dirs("all", home_dir).values():
                    self.assertTrue((target_dir / "jmcomic" / "SKILL.md").is_file())

                uninstall_result = self.runner.invoke(
                    app,
                    ["skills", "uninstall", "--platform", "all", "--yes", "--lang", "zh"],
                )

                self.assertEqual(0, uninstall_result.exit_code, uninstall_result.output)
                self.assertIn("Skill 卸载成功", uninstall_result.output)
                for target_dir in SkillManager.get_platform_target_dirs("all", home_dir).values():
                    self.assertFalse((target_dir / "jmcomic").exists())

    def test_install_prompt_supports_chinese(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.runner.invoke(
                app,
                ["skills", "install", temp_dir, "--lang", "zh"],
                input="n\n",
            )

            self.assertEqual(0, result.exit_code, result.output)
            self.assertIn("安装结构预览", result.output)
            self.assertIn("确认安装", result.output)
            self.assertIn("已取消安装", result.output)


class TestSkillManagerSafety(unittest.TestCase):
    def test_uninstalling_symlink_preserves_source_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source" / "jmcomic"
            source_dir.mkdir(parents=True)
            source_file = source_dir / "SKILL.md"
            source_file.write_text("source content", encoding="utf-8")

            target_dir = temp_path / "target"
            target_dir.mkdir()
            skill_link = target_dir / "jmcomic"
            skill_link.symlink_to(source_dir, target_is_directory=True)

            manager = SkillManager()
            manager.skills_source_dir = source_dir
            manager.skill_name = "jmcomic"

            self.assertFalse(manager.uninstall(target_dir))
            self.assertTrue(skill_link.is_symlink())
            self.assertTrue(source_file.is_file())
            self.assertEqual("source content", source_file.read_text(encoding="utf-8"))

    def test_cli_warns_and_skips_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source" / "jmcomic"
            source_dir.mkdir(parents=True)
            source_file = source_dir / "SKILL.md"
            source_file.write_text("source content", encoding="utf-8")

            target_dir = temp_path / "target"
            target_dir.mkdir()
            skill_link = target_dir / "jmcomic"
            skill_link.symlink_to(source_dir, target_is_directory=True)

            result = CliRunner().invoke(
                app,
                ["skills", "uninstall", str(target_dir), "--yes", "--lang", "zh"],
            )

            self.assertEqual(0, result.exit_code, result.output)
            self.assertIn("已跳过外部管理的 Skill 软链接", result.output)
            self.assertTrue(skill_link.is_symlink())
            self.assertTrue(source_file.is_file())


if __name__ == "__main__":
    unittest.main()
