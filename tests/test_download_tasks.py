"""Exercise native 2.7.9 batching, cancellation and runtime with controlled I/O."""

import asyncio
import contextlib
import io
import json
import logging
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from jmcomic import JTC, JmOption, jm_log

from jmcomic_ai.core import JmcomicService
from jmcomic_ai.downloads import DownloadTasks
from tests.process_policy import NO_WINDOW, hidden_windows_processes, stdio_python


def _run_shutdown_case(root: str):
    path = Path(root)
    service = JmcomicService(str(path / "option.yml"), str(path / "tasks"), str(path / "shutdown.log"))
    started = threading.Event()

    def download(_option, jm_id, **kwargs):
        started.set()
        while not JTC.is_cancelled():
            time.sleep(0.005)
        JTC.raise_if_cancelled()

    async def main():
        await service.start_download(["1"])
        await asyncio.to_thread(started.wait, 3)

    with patch.object(JmOption, "download_album", download):
        asyncio.run(main())
    state = next(iter(service._downloads.jobs.values()))
    report = json.loads(Path(state["report_path"]).read_text(encoding="utf-8"))
    print(json.dumps([state["status"], report["status"]]))


def _start_download_stdio_server(root: str):
    """Real stdio transport with controlled download I/O and native batch orchestration."""
    from jmcomic_ai.mcp.server import run_server

    path = Path(root)
    service = JmcomicService(str(path / "option.yml"), str(path / "tasks"), str(path / "stdio.log"))

    def download(_option, jm_id, **kwargs):
        if jm_id == "9":
            while not JTC.is_cancelled():
                time.sleep(0.005)
            JTC.raise_if_cancelled()
        if jm_id == "2":
            raise ValueError("controlled failure")
        return SimpleNamespace(
            detail=SimpleNamespace(id=jm_id, name="Example", save_path=path),
            duration=0.01,
            manifest=SimpleNamespace(image_filepath_list=[], export_filepath_dict={}),
        )

    JmOption.download_album = download
    run_server("stdio", service)


def _start_cancellable_stdio_server(root: str):
    """Use real transport/Runtime/export hooks with audited controlled download I/O."""
    from jmcomic_ai.mcp.server import run_server
    from tests.background_fixture import install

    install()
    path = Path(root)
    service = JmcomicService(str(path / "option.yml"), str(path / "tasks"), str(path / "stdio.log"))
    run_server("stdio", service)


class TestDownloadTasks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.process_policy = hidden_windows_processes()
        self.process_policy.__enter__()
        self.addCleanup(self.process_policy.__exit__, None, None, None)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = object.__new__(JmcomicService)
        self.service._setup_logging(str(self.root / "main.log"))
        self.service.task_log_dir = self.root / "tasks"
        self.service.option = JmOption.construct({"dir_rule": {"base_dir": str(self.root)}})
        self.service._downloads = DownloadTasks(self.service)

    async def asyncTearDown(self):
        for task_id, task in list(self.service._downloads.runners.items()):
            if not task.done():
                self.service._downloads.controls[task_id].cancel()
                await task
        for logger in (logging.getLogger(), logging.getLogger("jmcomic_ai"), logging.getLogger("jmcomic")):
            for handler in list(logger.handlers):
                if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve().is_relative_to(
                    self.root.resolve()
                ):
                    logger.removeHandler(handler)
                    handler.close()
        self.temporary.cleanup()

    def result(self, jm_id):
        path = self.root / jm_id
        path.mkdir(exist_ok=True)
        image = path / "1.jpg"
        image.write_bytes(b"test image")
        return SimpleNamespace(
            detail=SimpleNamespace(id=jm_id, name=f"Test {jm_id}", save_path=path),
            duration=0.1,
            manifest=SimpleNamespace(image_filepath_list=[str(image)], export_filepath_dict={}),
        )

    async def test_plan_offline_dedup_validation_and_no_config_mutation(self):
        before = self.service.option.deconstruct()
        with patch.object(self.service, "get_client", side_effect=AssertionError("No network")):
            plan = await self.service.plan_download(["JM2", "1", "2"], export_formats=["zip", "zip"])
        self.assertEqual(["2", "1"], plan["ids"])
        self.assertEqual(1, plan["duplicates_removed"])
        self.assertEqual(["zip"], plan["export_formats"])
        self.assertEqual(20, plan["workers"]["image"])
        self.assertEqual(before, self.service.option.deconstruct())
        for bad_ids in ([], ["0"], ["wrong"], ["1"] * 501):
            self.assertEqual("error", (await self.service.plan_download(bad_ids))["status"])
        self.assertEqual("error", (await self.service.start_download(["1"], album_workers=0))["status"])
        self.assertEqual("error", (await self.service.start_download(["1"], export_formats=["shell"]))["status"])
        self.assertFalse(self.service._downloads.jobs)

    async def test_explicit_layer_workers_and_chapter_batch_limit(self):
        self.service.option.download.threading.photo = 11
        self.service.option.download.threading.image = 37
        plan = await self.service.plan_download(["1"], kind="photo")
        self.assertEqual({"album": None, "photo": 11, "image": 37}, plan["workers"])
        self.assertEqual("error", (await self.service.plan_download(["1"], kind="photo", album_workers=2))["status"])
        for field in ("album_workers", "photo_workers", "image_workers"):
            for value in (0, -1, True, 1.5):
                self.assertEqual("error", (await self.service.plan_download(["1"], **{field: value}))["status"])

        lock = threading.Lock()
        active = peak = 0
        observed = []
        self.service.option.download.threading.photo = 1
        self.service.option.download.threading.image = 1

        def download(option, jm_id, **kwargs):
            nonlocal active, peak
            runtime = JTC.get_runtime()
            with lock:
                active += 1
                peak = max(peak, active)
                observed.append((option.download.threading.photo, option.download.threading.image))
            try:
                # The image work uses a separate executor while top-level chapters wait.
                runtime.executor("image").submit(time.sleep, 0.02).result()
                return self.result(jm_id)
            finally:
                with lock:
                    active -= 1

        with patch.object(JmOption, "download_photo", download):
            result = await self.service.download_batch(["1", "2", "3"], kind="photo", photo_workers=2, image_workers=4)
        self.assertEqual("success", result["status"])
        self.assertLessEqual(peak, 2)
        self.assertEqual([(2, 4)] * 3, observed)
        self.assertEqual({"album": None, "photo": 2, "image": 4}, result["plan"]["workers"])
        self.assertEqual(1, self.service.option.download.threading.photo)
        self.assertEqual(1, self.service.option.download.threading.image)

    async def test_legacy_report_retry_preserves_chapter_limit(self):
        from unittest.mock import AsyncMock

        task_id = "batch-" + "0" * 32
        self.service.task_log_dir.mkdir()
        report = {
            "task_id": task_id,
            "status": "partial",
            "unfinished_ids": ["2"],
            "plan": {"kind": "photo", "concurrency": 2, "workers": {"photo": 8, "image": 20}, "export_formats": []},
        }
        (self.service.task_log_dir / f"{task_id}.json").write_text(json.dumps(report), encoding="utf-8")
        with patch.object(
            self.service, "start_download", new_callable=AsyncMock, return_value={"status": "queued"}
        ) as start:
            self.assertEqual("queued", (await self.service.retry_download(task_id))["status"])
        start.assert_awaited_once_with(
            ["2"], kind="photo", album_workers=None, photo_workers=2, image_workers=20, export_formats=[]
        )

    async def test_native_batch_is_bounded_ordered_partial_and_retryable(self):
        lock = threading.Lock()
        active = peak = 0
        runtimes = []

        def download(_option, jm_id, **kwargs):
            nonlocal active, peak
            runtime = JTC.get_runtime()
            with lock:
                active += 1
                peak = max(peak, active)
                runtimes.append(runtime)
            try:
                time.sleep(0.03 if jm_id == "2" else 0.01)
                jm_log("test.batch", f"item-{jm_id}")
                if jm_id == "3":
                    raise ValueError("controlled item failure")
                return self.result(jm_id)
            finally:
                with lock:
                    active -= 1

        with patch.object(JmOption, "download_album", download):
            result = await self.service.download_batch(["2", "1", "2", "3"], album_workers=2)
        self.assertEqual("partial", result["status"])
        self.assertEqual(["2", "1", "3"], [item["id"] for item in result["items"]])
        self.assertEqual(["3"], result["failed_ids"])
        self.assertEqual(["3"], result["unfinished_ids"])
        self.assertLessEqual(peak, 2)
        self.assertEqual(1, len({id(runtime) for runtime in runtimes}))
        self.assertTrue(runtimes[0]._closed)
        self.assertEqual(result, json.loads(Path(result["report_path"]).read_text(encoding="utf-8")))
        self.assertTrue(all(Path(item["image_paths"][0]).is_file() for item in result["items"][:2]))
        original_id = result["task_id"]
        with patch.object(JmOption, "download_album", lambda _option, jm_id, **kw: self.result(jm_id)):
            retry = await self.service.retry_download(original_id)
            result = await self.service._downloads.wait(retry["task_id"])
        self.assertEqual(["3"], result["plan"]["ids"])
        self.assertEqual("success", result["status"])
        self.assertNotEqual(original_id, result["task_id"])
        self.assertEqual("partial", self.service.get_download_task(original_id)["status"])

    async def test_cooperative_cancel_preserves_completed_and_drains_workers(self):
        started = threading.Event()
        writes = []

        def download(_option, jm_id, **kwargs):
            if jm_id == "1":
                return self.result(jm_id)
            started.set()
            while not JTC.is_cancelled():
                time.sleep(0.005)
            JTC.raise_if_cancelled()
            writes.append(jm_id)

        with patch.object(JmOption, "download_album", download):
            initial = await self.service.start_download(["1", "2", "3"], album_workers=1)
            self.assertTrue(Path(initial["log_path"]).is_absolute())
            self.assertTrue(await asyncio.to_thread(started.wait, 3))
            self.assertEqual("cancelling", self.service.cancel_download(initial["task_id"])["status"])
            self.service.cancel_download(initial["task_id"])
            result = await self.service._downloads.wait(initial["task_id"])
        self.assertEqual("cancelled", result["status"])
        self.assertEqual("success", result["items"][0]["status"])
        self.assertEqual(["2", "3"], result["unfinished_ids"])
        self.assertEqual([], writes)
        self.assertEqual("cancelled", self.service.cancel_download(initial["task_id"])["status"])

    async def _assert_failures_survive_cancellation(self, *, missing_export):
        started = threading.Event()

        def result(jm_id, *, with_export=False):
            item = self.result(jm_id)
            if with_export:
                artifact = self.root / f"{jm_id}.zip"
                artifact.write_bytes(b"test export")
                item.manifest.export_filepath_dict = {"zip": [str(artifact)]}
            return item

        def download(_option, jm_id, **kwargs):
            if jm_id == "1":
                return result(jm_id, with_export=missing_export)
            if jm_id == "2":
                if missing_export:
                    return result(jm_id)
                raise ValueError("failure before cancellation")
            started.set()
            while not JTC.is_cancelled():
                time.sleep(0.005)
            JTC.raise_if_cancelled()

        with patch.object(JmOption, "download_album", download):
            initial = await self.service.start_download(
                ["1", "2", "3"], album_workers=1, export_formats=["zip"] if missing_export else []
            )
            self.assertTrue(await asyncio.to_thread(started.wait, 3))
            self.service.cancel_download(initial["task_id"])
            state = await self.service._downloads.wait(initial["task_id"])
        self.assertEqual("cancelled", state["status"])
        self.assertEqual(["success", "failed", "unfinished"], [item["status"] for item in state["items"]])
        self.assertEqual(["2"], state["failed_ids"])
        self.assertEqual(["2", "3"], state["unfinished_ids"])
        self.assertIsNone(state["items"][2]["error"])
        if missing_export:
            self.assertEqual(["zip"], state["items"][1]["missing_exports"])
            self.assertTrue(Path(state["items"][1]["image_paths"][0]).is_file())
        else:
            self.assertEqual("failure before cancellation", state["items"][1]["error"])
        self.assertEqual(state, json.loads(Path(state["report_path"]).read_text(encoding="utf-8")))

        retried = []

        def retry_download(_option, jm_id, **kwargs):
            retried.append(jm_id)
            return result(jm_id, with_export=missing_export)

        with patch.object(JmOption, "download_album", retry_download):
            retry = await self.service.retry_download(initial["task_id"])
            recovered = await self.service._downloads.wait(retry["task_id"])
        self.assertEqual(["2", "3"], recovered["plan"]["ids"])
        self.assertEqual(["2", "3"], retried)
        self.assertEqual("success", recovered["status"])

    async def test_item_failure_survives_batch_cancellation(self):
        await self._assert_failures_survive_cancellation(missing_export=False)

    async def test_export_failure_survives_batch_cancellation(self):
        await self._assert_failures_survive_cancellation(missing_export=True)

    async def test_caller_cancellation_stops_thread_before_return(self):
        started = threading.Event()
        stopped = threading.Event()

        def download(_option, jm_id, **kwargs):
            started.set()
            while not JTC.is_cancelled():
                time.sleep(0.005)
            stopped.set()
            JTC.raise_if_cancelled()

        with patch.object(JmOption, "download_album", download):
            task = asyncio.create_task(self.service.download_batch(["1"]))
            self.assertTrue(await asyncio.to_thread(started.wait, 3))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(stopped.is_set())
        self.assertEqual("cancelled", next(iter(self.service._downloads.jobs.values()))["status"])

    async def test_report_recovery_and_path_validation(self):
        with patch.object(JmOption, "download_album", lambda _option, jm_id, **kw: self.result(jm_id)):
            result = await self.service.download_batch(["1"])
        self.service._downloads = DownloadTasks(self.service)
        self.assertEqual(result, self.service.get_download_task(result["task_id"]))
        self.assertEqual("error", self.service.get_download_task("../option.yml")["status"])
        path = Path(result["report_path"])
        result["status"] = "running"
        path.write_text(json.dumps(result), encoding="utf-8")
        self.assertEqual("interrupted", self.service.get_download_task(result["task_id"])["status"])

    async def test_configuration_snapshot_and_missing_exports(self):
        original = self.service.option.download.threading.image
        observed = []

        def download(option, jm_id, **kwargs):
            observed.append(option.download.threading.image)
            return self.result(jm_id)

        with patch.object(JmOption, "download_album", download):
            task = await self.service.start_download(["1"], export_formats=["zip"])
            self.service.option.download.threading.image = 7
            result = await self.service._downloads.wait(task["task_id"])
        self.assertEqual([original], observed)
        self.assertEqual("failed", result["status"])
        self.assertEqual(["zip"], result["items"][0]["missing_exports"])
        self.assertTrue(Path(result["items"][0]["image_paths"][0]).is_file())
        self.assertEqual(["1"], result["unfinished_ids"])

    async def test_actual_zip_and_long_image_exports(self):
        from zipfile import ZipFile

        from jmcomic import JmAlbumDetail, JmPhotoDetail
        from PIL import Image

        def export(option, jm_id, **kwargs):
            album = JmAlbumDetail("1", "0", "Example", [("11", "1", "One")], 1, "", "", "0", "0", "0", [], [], [], [])
            photo = JmPhotoDetail(jm_id, "One", 1, 1, page_arr=["1.jpg"], from_album=album)
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
            for feature in kwargs["extra"]:
                feature.invoke(option, "after_photo", photo=photo, downloader=downloader)
            photo.save_path = str(directory)
            return SimpleNamespace(detail=photo, duration=0.1, manifest=manifest)

        with patch.object(JmOption, "download_photo", export):
            result = await self.service.download_batch(["11"], kind="photo", export_formats=["zip", "long_img"])
        self.assertEqual("success", result["status"])
        outputs = result["items"][0]["export_files"]
        self.assertEqual({"zip", "png"}, set(outputs))
        with ZipFile(outputs["zip"][0]) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(1, len(archive.namelist()))
        with Image.open(outputs["png"][0]) as image:
            self.assertEqual((4, 4), image.size)

    async def test_loop_shutdown_waits_for_thread_and_persists_terminal_report(self):
        result = await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "-B",
                "-c",
                "import sys; from tests.test_download_tasks import _run_shutdown_case; _run_shutdown_case(sys.argv[1])",
                str(self.root),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=NO_WINDOW,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["cancelled", "cancelled"], json.loads(result.stdout))

    async def test_cli_cancelled_json_and_offline_service_registration(self):
        from mcp.server.fastmcp import FastMCP

        from jmcomic_ai.download_cli import run_download
        from jmcomic_ai.mcp.server import _register_service_tools

        cancelled = asyncio.CancelledError()
        cancelled.download_result = {"status": "cancelled", "task_id": "example"}
        service = SimpleNamespace(download_batch=AsyncMock(side_effect=cancelled))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(asyncio.CancelledError):
            await run_download(service, SimpleNamespace(json=True), ["1"], "album")
        self.assertEqual("cancelled", json.loads(output.getvalue())["status"])
        with patch.object(JmOption, "build_jm_client", side_effect=AssertionError("No client during offline work")):
            service = JmcomicService(str(self.root / "offline.yml"), log_path=str(self.root / "offline.log"))
            _register_service_tools(FastMCP("offline-test"), service)
            self.assertEqual("success", (await service.plan_download(["1"]))["status"])

    async def test_new_tools_over_real_stdio(self):
        from datetime import timedelta

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = StdioServerParameters(
            command=stdio_python(),
            args=[
                "-B",
                "-c",
                "import sys; from tests.test_download_tasks import _start_download_stdio_server; "
                "_start_download_stdio_server(sys.argv[1])",
                str(self.root),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=10)) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                self.assertTrue(
                    {
                        "plan_download",
                        "download_batch",
                        "start_download",
                        "get_download_task",
                        "cancel_download",
                        "retry_download",
                    }
                    <= names
                )
                schema = next(
                    tool.inputSchema for tool in (await session.list_tools()).tools if tool.name == "start_download"
                )
                self.assertTrue({"album_workers", "photo_workers", "image_workers"} <= set(schema["properties"]))
                self.assertNotIn("concurrency", schema["properties"])

                async def call(name, args):
                    response = await session.call_tool(name, args)
                    self.assertFalse(response.isError, response.content)
                    self.assertEqual(response.structuredContent, json.loads(response.content[0].text))
                    return response.structuredContent

                plan = await call("plan_download", {"ids": ["001", "1", "2"]})
                self.assertEqual(["1", "2"], plan["ids"])
                result = await call("download_batch", {"ids": ["1", "2"]})
                self.assertEqual("partial", result["status"])
                retry = await call("retry_download", {"task_id": result["task_id"]})
                self.assertEqual(["2"], retry["plan"]["ids"])
                task = await call("start_download", {"ids": ["9"]})
                self.assertTrue(task["task_id"])
                cancel = await call("cancel_download", {"task_id": task["task_id"]})
                self.assertIn(cancel["status"], {"cancelling", "cancelled"})
                for _ in range(100):
                    final = await call("get_download_task", {"task_id": task["task_id"]})
                    if final["status"] == "cancelled":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual("cancelled", final["status"])
                self.assertEqual(["9"], final["unfinished_ids"])

    async def test_stdio_cancel_stops_writes_and_retry_executes_only_unfinished(self):
        from datetime import timedelta

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self.service.option.to_file(str(self.root / "option.yml"))
        server = StdioServerParameters(
            command=stdio_python(),
            args=[
                "-B",
                "-c",
                "import sys; from tests.test_download_tasks import _start_cancellable_stdio_server; "
                "_start_cancellable_stdio_server(sys.argv[1])",
                str(self.root),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=10)) as session:
                await session.initialize()

                async def call(name, args):
                    response = await session.call_tool(name, args)
                    self.assertFalse(response.isError, response.content)
                    return response.structuredContent

                async def wait(task_id, predicate):
                    for _ in range(200):
                        state = await call("get_download_task", {"task_id": task_id})
                        if predicate(state):
                            return state
                        await asyncio.sleep(0.025)
                    self.fail("MCP task did not reach expected state")

                def snapshot():
                    return {
                        str(path): (path.stat().st_size, path.stat().st_mtime_ns, path.read_bytes())
                        for path in self.root.rglob("*")
                        if path.is_file() and path.suffix in {".jpg", ".zip"}
                    }

                job = await call(
                    "start_download",
                    {"ids": ["1", "2", "3"], "album_workers": 1, "image_workers": 1, "export_formats": ["zip"]},
                )
                activity = self.root / "activity.log"
                await wait(
                    job["task_id"],
                    lambda state: state["progress"]["1"]["status"] == "success"
                    and activity.is_file()
                    and "start:2" in activity.read_text(encoding="utf-8"),
                )
                cancel = await call("cancel_download", {"task_id": job["task_id"]})
                self.assertIn(cancel["status"], {"cancelling", "cancelled"})
                final = await wait(job["task_id"], lambda state: state["status"] == "cancelled")
                self.assertEqual(["2", "3"], final["unfinished_ids"])
                trace = activity.read_text(encoding="utf-8")
                self.assertNotIn("start:3", trace)
                files = snapshot()
                await asyncio.sleep(1)
                self.assertEqual(files, snapshot())
                self.assertEqual(trace, activity.read_text(encoding="utf-8"))
                unchanged = await call("get_download_task", {"task_id": job["task_id"]})
                self.assertEqual(final["completed_images"], unchanged["completed_images"])
                repeated = await call("cancel_download", {"task_id": job["task_id"]})
                self.assertEqual("cancelled", repeated["status"])
                completed_image = Path(final["items"][0]["image_paths"][0])
                signature = completed_image.stat().st_mtime_ns, completed_image.read_bytes()
                (self.root / "release").touch()
                retry = await call("retry_download", {"task_id": job["task_id"]})
                self.assertNotEqual(job["task_id"], retry["task_id"])
                self.assertEqual(["2", "3"], retry["plan"]["ids"])
                result = await wait(retry["task_id"], lambda state: state["status"] == "success")
                self.assertEqual(["2", "3"], [item["id"] for item in result["items"]])
                executed = activity.read_text(encoding="utf-8")[len(trace) :].splitlines()
                self.assertEqual(["start:2", "start:3"], [line for line in executed if line.startswith("start:")])
                self.assertEqual(signature, (completed_image.stat().st_mtime_ns, completed_image.read_bytes()))
                self.assertEqual("cancelled", (await call("get_download_task", {"task_id": job["task_id"]}))["status"])

    async def test_metadata_chapters_and_partial_request_failure(self):
        album = SimpleNamespace(
            album_id="1",
            is_favorite=False,
            liked=False,
            name="Example",
            author="Author",
            likes=1,
            views=2,
            tags=[],
            actors=[],
            description="",
            page_count=25,
            pub_date="2026-01-01",
            episode_list=[("11", "1", "Part 1"), ("12", "2", "Part 2")],
            update_date="today",
        )

        class Album(SimpleNamespace):
            def __len__(self):
                return 2

        details = self.service._parse_album_detail(Album(**vars(album)))
        self.assertEqual(["11", "12"], [item["id"] for item in details["chapters"]])
        with patch.object(self.service, "get_album_detail", side_effect=[details, ValueError("missing")]):
            plan = await self.service.plan_download(["1", "2"], include_details=True, album_workers=1)
        self.assertEqual("partial", plan["status"])
        self.assertEqual(["success", "failed"], [detail["status"] for detail in plan["details"]])
        self.assertTrue(plan["network_requested"])


if __name__ == "__main__":
    unittest.main()
