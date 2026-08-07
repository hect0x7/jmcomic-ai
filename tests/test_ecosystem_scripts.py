"""Tests for APK download and local-reader Skill scripts."""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jmcomic_ai.skills.jmcomic.scripts import download_latest_apk, start_view_server


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class TestDownloadLatestApk(unittest.TestCase):
    def test_fetch_latest_apk_selects_release_asset(self):
        release = {
            "tag_name": "2.0.30",
            "html_url": "https://github.com/hect0x7/JMComic-APK/releases/tag/2.0.30",
            "assets": [
                {
                    "name": "2.0.30.apk",
                    "size": 3,
                    "digest": "sha256:84caeca2dc85b498c6687ef57f2f8e3451f5b6f16b1f68bc7d344ab47e8d8d04",
                    "browser_download_url": "https://github.com/hect0x7/JMComic-APK/releases/download/2.0.30/2.0.30.apk",
                }
            ],
        }
        with patch.object(
            download_latest_apk.urllib.request,
            "urlopen",
            return_value=_Response(json.dumps(release).encode()),
        ):
            asset = download_latest_apk.fetch_latest_apk()

        self.assertEqual("2.0.30", asset["version"])
        self.assertEqual("2.0.30.apk", asset["name"])

    def test_download_apk_writes_atomically(self):
        asset = {
            "name": "2.0.30.apk",
            "size": 3,
            "digest": f"sha256:{hashlib.sha256(b'apk').hexdigest()}",
            "download_url": "https://github.com/example.apk",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(download_latest_apk.urllib.request, "urlopen", return_value=_Response(b"apk")):
                result = download_latest_apk.download_apk(asset, Path(temp_dir))

            self.assertEqual(b"apk", result.read_bytes())
            self.assertEqual([], list(Path(temp_dir).glob("*.part")))

    def test_download_apk_rejects_size_mismatch(self):
        asset = {"name": "2.0.30.apk", "size": 4, "download_url": "https://github.com/example.apk"}
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(download_latest_apk.urllib.request, "urlopen", return_value=_Response(b"apk")),
                self.assertRaisesRegex(RuntimeError, "size mismatch"),
            ):
                download_latest_apk.download_apk(asset, Path(temp_dir))
            self.assertEqual([], list(Path(temp_dir).iterdir()))

    def test_download_apk_rejects_digest_mismatch(self):
        asset = {
            "name": "2.0.30.apk",
            "size": 3,
            "digest": f"sha256:{'0' * 64}",
            "download_url": "https://github.com/example.apk",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(download_latest_apk.urllib.request, "urlopen", return_value=_Response(b"apk")),
                self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"),
            ):
                download_latest_apk.download_apk(asset, Path(temp_dir))
            self.assertEqual([], list(Path(temp_dir).iterdir()))


class TestStartViewServer(unittest.TestCase):
    def test_local_command_uses_safe_defaults(self):
        command = start_view_server.build_command("jms", Path("/comics"), "127.0.0.1", 8080, None)
        self.assertEqual(
            ["jms", str(Path("/comics")), "--host", "127.0.0.1", "--port", "8080", "--no-debug"],
            command,
        )

    def test_lan_command_requires_password(self):
        with self.assertRaisesRegex(ValueError, "password is required"):
            start_view_server.build_command("jms", Path("/comics"), "0.0.0.0", 8080, None)

    def test_lan_command_includes_password(self):
        command = start_view_server.build_command("jms", Path("/comics"), "0.0.0.0", 8080, "secret")
        self.assertEqual(["--password", "secret"], command[-2:])

    def test_redact_command_hides_password(self):
        command = ["jms", "/comics", "--password", "secret"]
        self.assertEqual(["jms", "/comics", "--password", "********"], start_view_server.redact_command(command))
        self.assertEqual("secret", command[-1])


if __name__ == "__main__":
    unittest.main()
