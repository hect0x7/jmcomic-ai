"""Regression tests for Skill script process exit codes."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from jmcomic_ai.skills.jmcomic.scripts import (
    album_info,
    batch_download,
    doctor,
    download_covers,
    download_photo,
    post_process,
    ranking_tracker,
)


class TestSkillScriptExitCodes(unittest.TestCase):
    def test_album_info_partial_failure_exits_nonzero(self):
        args = SimpleNamespace(id="1", ids=None, file=None, output=None, option=None, verbose=False)
        with (
            patch.object(album_info, "parse_args", return_value=args),
            patch.object(album_info, "JmcomicService"),
            patch.object(album_info, "fetch_album_details", return_value=([], [{"id": "1", "error": "failed"}])),
            self.assertRaisesRegex(SystemExit, "1"),
        ):
            album_info.main()

    def test_batch_download_failure_exits_nonzero(self):
        args = SimpleNamespace(ids="1", file=None, option=None)
        service = Mock()
        service.download_album = AsyncMock(return_value={"status": "failed", "error": "failed", "log_path": "log"})
        with (
            patch.object(batch_download, "parse_args", return_value=args),
            patch.object(batch_download, "JmcomicService", return_value=service),
            self.assertRaisesRegex(SystemExit, "1"),
        ):
            asyncio.run(batch_download.main())

    def test_download_photo_failure_exits_nonzero(self):
        args = SimpleNamespace(ids="1", file=None, option=None)
        service = Mock()
        service.download_photo = AsyncMock(return_value={"status": "failed", "error": "failed", "log_path": "log"})
        with (
            patch.object(download_photo, "parse_args", return_value=args),
            patch.object(download_photo, "JmcomicService", return_value=service),
            self.assertRaisesRegex(SystemExit, "1"),
        ):
            asyncio.run(download_photo.main())

    def test_download_cover_failure_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(ids="1", file=None, output=str(Path(temp_dir) / "covers"), option=None)
            with (
                patch.object(download_covers, "parse_args", return_value=args),
                patch.object(download_covers, "JmcomicService"),
                patch.object(download_covers, "download_covers", return_value=(0, ["1"])),
                self.assertRaisesRegex(SystemExit, "1"),
            ):
                download_covers.main()

    def test_ranking_failure_exits_nonzero(self):
        args = SimpleNamespace(period="day", all=False, max_pages=1, output="ranking.json", option=None, add_timestamp=False)
        with (
            patch.object(ranking_tracker, "parse_args", return_value=args),
            patch.object(ranking_tracker, "JmcomicService"),
            patch.object(ranking_tracker, "fetch_ranking", return_value=([], True)),
            self.assertRaisesRegex(SystemExit, "1"),
        ):
            ranking_tracker.main()

    def test_post_process_error_result_exits_nonzero(self):
        args = SimpleNamespace(
            id="1",
            type="zip",
            option=None,
            delete=False,
            password=None,
            outdir=None,
            dir_rule=None,
            base_dir=None,
            level="photo",
        )
        service = Mock()
        service.post_process.return_value = {"status": "error", "message": "failed"}
        with (
            patch.object(post_process.argparse.ArgumentParser, "parse_args", return_value=args),
            patch.object(post_process, "JmcomicService", return_value=service),
            self.assertRaisesRegex(SystemExit, "1"),
        ):
            post_process.main()

    def test_doctor_failure_exits_nonzero(self):
        with (
            patch.object(doctor, "check_dependencies", return_value=False),
            patch.object(doctor, "check_config"),
            patch.object(doctor, "check_network", return_value=True),
            self.assertRaisesRegex(SystemExit, "1"),
        ):
            doctor.main()


if __name__ == "__main__":
    unittest.main()
