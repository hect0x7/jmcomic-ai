"""Controlled download I/O installed only in isolated subprocess test environments."""

import os
import time
from pathlib import Path
from types import SimpleNamespace


def install() -> None:
    from jmcomic import JTC, JmAlbumDetail, JmOption, JmPhotoDetail
    from PIL import Image

    if os.name == "nt" and os.getenv("JM_TASK_LOG_DIR"):
        import ctypes

        directory = Path(os.environ["JM_TASK_LOG_DIR"]).parent
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"console-{os.getpid()}.txt").write_text(str(ctypes.windll.kernel32.GetConsoleWindow()), encoding="utf-8")

    delay = float(os.getenv("JMAI_FIXTURE_START_DELAY", "0"))
    if delay:
        time.sleep(delay)

    def download(option, jm_id, **kwargs):
        root = Path(option.dir_rule.base_dir)
        root.mkdir(parents=True, exist_ok=True)
        JTC.raise_if_cancelled()
        with (root / "activity.log").open("a", encoding="utf-8") as stream:
            stream.write(f"start:{jm_id}\n")
        # Hold one item long enough for a wholly separate CLI to query/cancel.
        if jm_id == "2":
            deadline = time.monotonic() + 30
            while not (root / "release").exists() and time.monotonic() < deadline:
                JTC.raise_if_cancelled()
                time.sleep(0.03)
        if jm_id == "99" and not (root / "release").exists():
            raise ValueError("Controlled item failure")
        JTC.raise_if_cancelled()
        album = JmAlbumDetail(
            jm_id, "0", f"Fixture {jm_id}", [(jm_id, "1", f"Chapter {jm_id}")], 1, "", "", "0", "0", "0", [], [], [], []
        )
        photo = JmPhotoDetail(jm_id, f"Chapter {jm_id}", 1, 1, page_arr=["1.jpg"], from_album=album)
        directory = Path(option.decide_image_save_dir(photo))
        directory.mkdir(parents=True, exist_ok=True)
        image = directory / "1.jpg"
        Image.new("RGB", (4, 4), "red").save(image)
        manifest = SimpleNamespace(image_filepath_list=[str(image)], export_filepath_dict={})

        def record(detail, path):
            manifest.export_filepath_dict.setdefault(Path(path).suffix[1:], []).append(path)

        downloader = SimpleNamespace(
            download_success_dict={album: {photo: [(str(image), None)]}}, record_export_filepath=record
        )
        kind = JTC.get_context_value("download_type")
        for feature in kwargs.get("extra") or []:
            feature.invoke(
                option,
                f"after_{kind}",
                downloader=downloader,
                **({"photo": photo} if kind == "photo" else {"album": album}),
            )
        detail = photo if kind == "photo" else album
        detail.save_path = str(directory)
        with (root / "activity.log").open("a", encoding="utf-8") as stream:
            stream.write(f"finish:{jm_id}\n")
        return SimpleNamespace(detail=detail, duration=0.01, manifest=manifest)

    JmOption.download_album = download
    JmOption.download_photo = download
