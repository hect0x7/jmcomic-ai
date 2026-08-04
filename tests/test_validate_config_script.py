"""Tests for the configuration validation Skill script."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from jmcomic import JmOption

from jmcomic_ai.skills.jmcomic.scripts import validate_config


class TestValidateConfigScript(unittest.TestCase):
    def test_default_dir_rule_is_printed(self):
        option = JmOption.default()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            validate_config.print_config_summary(option)

        self.assertIn(f"Rule: {option.dir_rule.rule_dsl}", stdout.getvalue())

    def test_custom_dir_rule_is_printed(self):
        option = JmOption.default()
        option.dir_rule.rule_dsl = "Bd_Aid_Pindex"
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            validate_config.print_config_summary(option)

        self.assertIn("Rule: Bd_Aid_Pindex", stdout.getvalue())

    def test_json_conversion_creates_parent_directories(self):
        option = JmOption.default()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "option.json"
            success, error = validate_config.convert_to_json(option, output_path)

            self.assertTrue(success, error)
            self.assertTrue(output_path.is_file())


if __name__ == "__main__":
    unittest.main()
