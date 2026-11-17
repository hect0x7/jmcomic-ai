"""Exercise real upstream exporters using local images only."""

import importlib.util
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

from jmcomic import JmAlbumDetail, JmOption
from PIL import Image

from jmcomic_ai.core import JmcomicService


class TestRealPostProcessExports(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.album = JmAlbumDetail(
            "1", "0", "Example", [("11", "1", "One"), ("12", "2", "Two")], 1, "", "", "0", "0", "0", [], [], [], []
        )
        self.service = object.__new__(JmcomicService)
        self.service.logger = logging.getLogger("test.exports")
        self.service.client = Mock()
        self.service.client.get_album_detail.return_value = self.album
        self.service.option = JmOption.construct(
            {"log": False, "dir_rule": {"base_dir": str(self.root / "images"), "rule": "Bd/Aid/Pid"}}
        )
        for photo in self.album:
            directory = Path(self.service.option.decide_image_save_dir(photo))
            directory.mkdir(parents=True, exist_ok=True)
            for name, color in [("1.png", "red"), ("2.png", "green"), ("10.png", "blue")]:
                Image.new("RGB", (4, 4), color).save(directory / name)
            (directory / "3.png").mkdir()
            (directory / ".hidden.png").write_bytes(b"ignored")
        self.output = self.root / "exports"
        self.output.mkdir()

    def run_export(self, kind, **params):
        directory_key = {"zip": "zip_dir", "long_img": "img_dir", "img2pdf": "pdf_dir"}[kind]
        result = self.service.post_process("1", kind, {directory_key: str(self.output), **params})
        self.assertEqual("success", result["status"], result)
        self.assertTrue(all(Path(p).is_file() for p in result["output_paths"]))
        return result

    def test_zip_album_and_chapter_defaults_and_cleanup(self):
        result = self.run_export("zip")
        self.assertEqual("[JM1]Example.zip", Path(result["output_path"]).name)
        with ZipFile(result["output_path"]) as archive:
            self.assertEqual(
                ["11/1.png", "11/2.png", "11/10.png", "12/1.png", "12/2.png", "12/10.png"], archive.namelist()
            )
            self.assertIsNone(archive.testzip())
        result = self.run_export("zip", level="photo", delete_original_file=True)
        self.assertEqual({"[JM11]One.zip", "[JM12]Two.zip"}, {Path(p).name for p in result["output_paths"]})
        self.assertEqual([], list((self.root / "images").rglob("1.png")))
        self.assertEqual(2, len(list((self.root / "images").rglob(".hidden.png"))))

    def test_long_image_page_order_and_custom_filename(self):
        result = self.run_export("long_img", filename_rule="custom-{Aid}")
        self.assertEqual("custom-1.png", Path(result["output_path"]).name)
        with Image.open(result["output_path"]) as image:
            self.assertEqual((4, 24), image.size)
            self.assertEqual(
                [(255, 0, 0), (0, 128, 0), (0, 0, 255)] * 2, [image.getpixel((0, y)) for y in range(0, 24, 4)]
            )

    def test_full_path_rule_takes_precedence(self):
        result = self.run_export(
            "zip", filename_rule="unused", dir_rule={"base_dir": str(self.output), "rule": "Bd/chosen.zip"}
        )
        self.assertEqual("chosen.zip", Path(result["output_path"]).name)

    @unittest.skipUnless(
        importlib.util.find_spec("img2pdf") and importlib.util.find_spec("pikepdf"),
        "PDF integration requires img2pdf and pikepdf",
    )
    def test_pdf_pages_and_fixed_encryption(self):
        import pikepdf

        result = self.run_export("img2pdf", encrypt={"password": "test-only-password"})
        self.assertEqual("[JM1]Example.pdf", Path(result["output_path"]).name)
        with pikepdf.open(result["output_path"], password="test-only-password") as pdf:
            self.assertEqual(6, len(pdf.pages))
            self.assertTrue(pdf.is_encrypted)

    @unittest.skipUnless(
        importlib.util.find_spec("img2pdf") and importlib.util.find_spec("pikepdf"),
        "PDF integration requires img2pdf and pikepdf",
    )
    def test_pdf_random_encryption(self):
        from unittest.mock import patch

        import pikepdf
        from jmcomic import Img2pdfPlugin

        with patch.object(Img2pdfPlugin, "generate_random_str", return_value="test-only-random"):
            result = self.run_export("img2pdf", encrypt={"type": "random"})
        with pikepdf.open(result["output_path"], password="test-only-random") as pdf:
            self.assertEqual(6, len(pdf.pages))
            self.assertTrue(pdf.is_encrypted)

    def test_chapter_long_images(self):
        result = self.run_export("long_img", level="photo")
        self.assertEqual({"[JM11]One.png", "[JM12]Two.png"}, {Path(p).name for p in result["output_paths"]})
        for path in result["output_paths"]:
            with Image.open(path) as image:
                self.assertEqual((4, 12), image.size)

    def test_invalid_level_returns_error(self):
        result = self.service.post_process("1", "zip", {"level": "invalid"})
        self.assertEqual("error", result["status"])
        self.assertIn("level must be", result["message"])
