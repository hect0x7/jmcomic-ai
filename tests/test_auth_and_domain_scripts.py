"""Unit and regression tests for login and check_domains Skill scripts."""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jmcomic_ai.skills.jmcomic.scripts import check_domains, login


class TestLoginScript(unittest.TestCase):
    def test_api_login_passes_custom_domain_and_catches_client_setup_failure(self):
        service = Mock()
        client = Mock()
        client.login.return_value = SimpleNamespace(res_data={"uid": "1", "username": "tester"})
        client.get_meta_data.return_value = {"AVS": "cookie"}
        client.domain_list = ["api.example/path"]
        client.current_domain = "api.example/path"
        service.option.new_jm_client.return_value = client

        result = login.perform_api_login(service, "tester", "password", "api.example/path")

        self.assertEqual("success", result["status"])
        service.option.new_jm_client.assert_called_once_with(impl="api", domain_list=["api.example/path"])

        service.option.new_jm_client.side_effect = RuntimeError("invalid domain")
        result = login.perform_api_login(service, "tester", "password", "api.example/path")
        self.assertEqual("failed", result["status"])
        self.assertIn("invalid domain", result["error"])

    def test_html_login_passes_custom_domain(self):
        service = Mock()
        client = Mock()
        client.login.return_value = SimpleNamespace(status_code=200)
        client.get_meta_data.return_value = {"AVS": "cookie"}
        service.option.new_jm_client.return_value = client

        result = login.perform_html_login(service, "tester", "password", "html.example/base")

        self.assertEqual("success", result["status"])
        self.assertEqual("html.example/base", result["client_domain"])
        service.option.new_jm_client.assert_called_once_with(impl="html", domain_list=["html.example/base"])

    def test_missing_credentials_exits_nonzero(self):
        args = SimpleNamespace(
            username="",
            password="",
            impl="both",
            domain=None,
            proxy=None,
            save=False,
            option=None,
            json=False,
        )
        with (
            patch.object(login, "parse_args", return_value=args),
            patch("sys.stdin.isatty", return_value=False),
            self.assertRaises(SystemExit) as exit_context,
        ):
            login.main()
        self.assertEqual(1, exit_context.exception.code)

    def test_login_both_success_exits_zero(self):
        args = SimpleNamespace(
            username="test_user",
            password="test_password",
            impl="both",
            domain=None,
            proxy=None,
            save=False,
            option=None,
            json=True,
        )
        service = Mock()
        api_success = {
            "status": "success",
            "uid": "12345",
            "username": "test_user",
            "avs_cookie": "test_avs",
            "client_domain": "api.test",
        }
        html_success = {
            "status": "success",
            "status_code": 200,
            "avs_cookie": "test_avs",
            "client_domain": "html.test",
        }

        buf = io.StringIO()
        with (
            patch.object(login, "parse_args", return_value=args),
            patch.object(login, "JmcomicService", return_value=service),
            patch.object(login, "detect_local_proxy", return_value=None),
            patch.object(login, "perform_api_login", return_value=api_success),
            patch.object(login, "perform_html_login", return_value=html_success),
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            login.main()

        self.assertEqual(0, exit_context.exception.code)
        data = json.loads(buf.getvalue())
        self.assertEqual("success", data["status"])
        self.assertEqual("test_user", data["username"])
        self.assertIn("api", data["results"])
        self.assertIn("html", data["results"])

    def test_login_failure_exits_nonzero(self):
        args = SimpleNamespace(
            username="test_user",
            password="bad_password",
            impl="both",
            domain=None,
            proxy=None,
            save=False,
            option=None,
            json=True,
        )
        service = Mock()
        api_failed = {"status": "failed", "error": "Login failed: invalid password"}
        html_failed = {"status": "failed", "error": "Login failed: invalid password"}

        buf = io.StringIO()
        with (
            patch.object(login, "parse_args", return_value=args),
            patch.object(login, "JmcomicService", return_value=service),
            patch.object(login, "detect_local_proxy", return_value=None),
            patch.object(login, "perform_api_login", return_value=api_failed),
            patch.object(login, "perform_html_login", return_value=html_failed),
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            login.main()

        self.assertEqual(1, exit_context.exception.code)
        data = json.loads(buf.getvalue())
        self.assertEqual("failed", data["status"])

    def test_login_save_failure_exits_nonzero(self):
        args = SimpleNamespace(
            username="test_user",
            password="test_password",
            impl="api",
            domain=None,
            proxy=None,
            save=True,
            option=None,
            json=True,
        )
        service = Mock()
        service.update_option.return_value = "option update failed: invalid schema"
        api_success = {"status": "success", "avs_cookie": "api_cookie", "client_domain": "api.example"}

        buf = io.StringIO()
        with (
            patch.object(login, "parse_args", return_value=args),
            patch.object(login, "JmcomicService", return_value=service),
            patch.object(login, "detect_local_proxy", return_value=None),
            patch.object(login, "perform_api_login", return_value=api_success),
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            login.main()

        self.assertEqual(1, exit_context.exception.code)
        self.assertEqual("failed", json.loads(buf.getvalue())["status"])

    def test_login_partial_failure_exits_nonzero_and_passes_domain_to_both(self):
        args = SimpleNamespace(
            username="test_user",
            password="test_password",
            impl="both",
            domain="custom.example/base",
            proxy=None,
            save=False,
            option=None,
            json=True,
        )
        service = Mock()
        api_failed = {"status": "failed", "error": "API unavailable"}
        html_success = {"status": "success", "status_code": 200, "avs_cookie": "cookie"}

        buf = io.StringIO()
        with (
            patch.object(login, "parse_args", return_value=args),
            patch.object(login, "JmcomicService", return_value=service),
            patch.object(login, "detect_local_proxy", return_value=None),
            patch.object(login, "perform_api_login", return_value=api_failed) as api_login,
            patch.object(login, "perform_html_login", return_value=html_success) as html_login,
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            login.main()

        self.assertEqual(1, exit_context.exception.code)
        api_login.assert_called_once_with(service, "test_user", "test_password", "custom.example/base")
        html_login.assert_called_once_with(service, "test_user", "test_password", "custom.example/base")
        self.assertEqual("partial", json.loads(buf.getvalue())["status"])

    def test_login_save_flag_updates_option(self):
        args = SimpleNamespace(
            username="test_user",
            password="test_password",
            impl="api",
            domain=None,
            proxy=None,
            save=True,
            option=None,
            json=False,
        )
        service = Mock()
        service.option_path = "mock/option.yml"
        service.update_option.return_value = "Option updated"

        api_success = {
            "status": "success",
            "uid": "12345",
            "username": "test_user",
            "avs_cookie": "test_avs_123",
            "client_domain": "api.test",
        }

        buf = io.StringIO()
        with (
            patch.object(login, "parse_args", return_value=args),
            patch.object(login, "JmcomicService", return_value=service),
            patch.object(login, "detect_local_proxy", return_value=None),
            patch.object(login, "perform_api_login", return_value=api_success),
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            login.main()

        self.assertEqual(0, exit_context.exception.code)
        service.update_option.assert_called_once()
        call_arg = service.update_option.call_args[0][0]
        self.assertEqual("test_avs_123", call_arg["client"]["postman"]["meta_data"]["cookies"]["AVS"])

    def test_save_option_failure_is_reported(self):
        service = Mock()
        service.update_option.return_value = "option update failed: invalid option"

        saved, message = login.save_credentials_to_option(service, "cookie", "api", "api.example")

        self.assertFalse(saved)
        self.assertIn("option update failed", message)


class TestCheckDomainsScript(unittest.TestCase):
    def test_discovered_html_path_is_preserved(self):
        with patch.object(
            check_domains.JmModuleConfig,
            "get_html_domain_all",
            return_value={"jm-88.cc/ZNPJam", "https://18comic.ink/base/", "t.me/channel"},
        ):
            result = check_domains.fetch_candidate_domains("html")

        self.assertIn("jm-88.cc/ZNPJam", result["html"])
        self.assertIn("https://18comic.ink/base", result["html"])
        self.assertNotIn("t.me/channel", result["html"])

    def test_api_setting_requires_jmcomic_response_envelope(self):
        option = Mock()
        client = Mock()
        valid_response = SimpleNamespace(
            status_code=200,
            text='{"code": 200, "data": "encoded"}',
            headers={},
            json=lambda: {"code": 200, "data": "encoded"},
        )
        client.get.return_value = valid_response
        option.new_jm_client.return_value = client

        result = check_domains.test_single_domain("api.example", "api", option)
        self.assertEqual("available", result["verdict"])

        invalid_response = SimpleNamespace(
            status_code=200,
            text="<html>not an API response</html>",
            headers={},
            json=lambda: {"ok": True},
        )
        client.get.return_value = invalid_response
        result = check_domains.test_single_domain("api.example", "api", option)
        self.assertEqual("http_error", result["verdict"])

    def test_domain_client_setup_failure_is_reported(self):
        option = Mock()
        option.new_jm_client.side_effect = RuntimeError("bad domain")

        result = check_domains.test_single_domain("bad.example", "html", option)

        self.assertEqual("error", result["verdict"])
        self.assertIn("bad domain", result["error_detail"])

    def test_no_auto_proxy_flag_is_available(self):
        with patch.object(sys, "argv", ["check_domains.py", "--no-auto-proxy"]):
            args = check_domains.parse_args()

        self.assertFalse(args.auto_proxy)

    def test_check_domains_success_exits_zero(self):
        args = SimpleNamespace(
            type="all",
            proxy=None,
            auto_proxy=False,
            best=False,
            json=True,
            timeout=5,
            option=None,
        )
        service = Mock()
        mock_option = Mock()
        mock_option.client.postman.meta_data = {}
        service.option = mock_option

        mock_domains = {
            "html": ["18comic.ink"],
            "api": ["www.cdnhjk.net"],
        }
        mock_results = [
            {
                "domain": "18comic.ink",
                "type": "html",
                "status_code": 200,
                "latency_ms": 200.0,
                "verdict": "available",
                "location": None,
                "has_cf_challenge": False,
                "error_detail": None,
            },
            {
                "domain": "www.cdnhjk.net",
                "type": "api",
                "status_code": 200,
                "latency_ms": 150.0,
                "verdict": "available",
                "location": None,
                "has_cf_challenge": False,
                "error_detail": None,
            },
        ]

        buf = io.StringIO()
        with (
            patch.object(check_domains, "parse_args", return_value=args),
            patch.object(check_domains, "JmcomicService", return_value=service),
            patch.object(check_domains, "fetch_candidate_domains", return_value=mock_domains),
            patch.object(check_domains, "test_single_domain", side_effect=mock_results),
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            check_domains.main()

        self.assertEqual(0, exit_context.exception.code)
        data = json.loads(buf.getvalue())
        self.assertEqual("18comic.ink", data["best_html"])
        self.assertEqual("www.cdnhjk.net", data["best_api"])

    def test_check_domains_all_fail_exits_nonzero(self):
        args = SimpleNamespace(
            type="html",
            proxy=None,
            auto_proxy=False,
            best=False,
            json=False,
            timeout=5,
            option=None,
        )
        service = Mock()
        mock_option = Mock()
        mock_option.client.postman.meta_data = {}
        service.option = mock_option

        mock_domains = {"html": ["18comic.vip"]}
        mock_res = {
            "domain": "18comic.vip",
            "type": "html",
            "status_code": 403,
            "latency_ms": 500.0,
            "verdict": "blocked",
            "location": None,
            "has_cf_challenge": True,
            "error_detail": "Cloudflare Challenge",
        }

        buf = io.StringIO()
        with (
            patch.object(check_domains, "parse_args", return_value=args),
            patch.object(check_domains, "JmcomicService", return_value=service),
            patch.object(check_domains, "fetch_candidate_domains", return_value=mock_domains),
            patch.object(check_domains, "test_single_domain", return_value=mock_res),
            redirect_stdout(buf),
            self.assertRaises(SystemExit) as exit_context,
        ):
            check_domains.main()

        self.assertEqual(1, exit_context.exception.code)


if __name__ == "__main__":
    unittest.main()
