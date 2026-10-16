"""Real CLI/worker subprocesses and OS locks; only download I/O is controlled."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from jmcomic import JmOption

from jmcomic_ai.background import launch_background
from jmcomic_ai.task_store import TERMINAL, TaskStore
from tests.process_policy import NO_WINDOW, hidden_windows_processes

PROJECT = Path(__file__).resolve().parents[1]


class TestBackgroundTasks(unittest.TestCase):
    def setUp(self):
        self.process_policy = hidden_windows_processes()
        self.process_policy.__enter__()
        self.addCleanup(self.process_policy.__exit__, None, None, None)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task_dir = self.root / "tasks"
        self.output = self.root / "downloads"
        self.option_path = self.root / "option.yml"
        JmOption.construct(
            {
                "dir_rule": {"base_dir": str(self.output)},
                "client": {"postman": {"meta_data": {"cookies": {"fixture": "test-only-canary"}}}},
            }
        ).to_file(str(self.option_path))
        site = self.root / "python-startup"
        site.mkdir()
        (site / "sitecustomize.py").write_text(
            "from tests.background_fixture import install\ninstall()\n", encoding="utf-8"
        )
        self.environment = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(site), str(PROJECT)]),
            "PYTHONIOENCODING": "utf-8",
            "JM_TASK_LOG_DIR": str(self.task_dir),
            "JM_LOG_PATH": str(self.root / "global.log"),
        }
        self.store = TaskStore(self.task_dir)
        self.task_ids = []

    def tearDown(self):
        for task_id in self.task_ids:
            try:
                self.store.request_cancel(task_id)
                self.wait_terminal(task_id, timeout=8)
            except (ValueError, OSError, AssertionError):
                pass
        deadline = time.monotonic() + 5
        while True:
            try:
                self.temporary.cleanup()
                break
            except OSError:
                # A terminal task has no remaining I/O, but the short-lived
                # interpreter can still be releasing its bootstrap log handle.
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def cli(self, *arguments, expected=0, environment=None, cwd=None):
        result = subprocess.run(
            [sys.executable, "-B", "-c", "from jmcomic_ai.cli import app; app()", *arguments],
            cwd=str(cwd or PROJECT),
            env=environment or self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=25,
            creationflags=NO_WINDOW,
        )
        self.assertIn(result.returncode, expected if isinstance(expected, tuple) else (expected,), result.stderr)
        return json.loads(result.stdout)

    def start(self, ids="1,2,3", *extra):
        result = self.cli(
            "download",
            "--ids",
            ids,
            "--album-workers",
            "1",
            "--option",
            str(self.option_path),
            "--task-dir",
            str(self.task_dir),
            "--background",
            "--json",
            *extra,
        )
        self.task_ids.append(result["task_id"])
        return result

    def wait_terminal(self, task_id, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.store.read(task_id)
            if state["status"] in TERMINAL:
                return state
            time.sleep(0.05)
        self.fail("Task did not reach a terminal state")

    def test_parent_exits_query_cancel_and_retry_from_new_cli(self):
        job = self.start("1,2,3", "--export", "zip")
        self.assertTrue(job["ready"])
        self.assertTrue(self.store.owner_alive(job["task_id"]))
        # The launching CLI has exited. Query using a new process, without loading configuration.
        environment = {**self.environment, "JM_OPTION_PATH": str(self.root / "nonexistent" / "bad.yml")}
        state = self.cli("task", "status", job["task_id"], "--json", environment=environment)
        self.assertIn(state["status"], {"queued", "running"})
        self.assertEqual("success", state["items"][0]["status"])
        cancel = self.cli("task", "cancel", job["task_id"], "--json", environment=environment)
        self.assertIn(cancel["status"], {"cancel_requested", "cancelling", "cancelled"})
        final = self.wait_terminal(job["task_id"])
        self.assertEqual("cancelled", final["status"])
        self.assertEqual(["2", "3"], final["unfinished_ids"])
        activity = (self.output / "activity.log").read_text(encoding="utf-8")
        self.assertNotIn("start:3", activity)
        time.sleep(0.1)
        self.assertEqual(activity, (self.output / "activity.log").read_text(encoding="utf-8"))
        self.assertEqual("cancelled", self.cli("task", "cancel", job["task_id"], "--json")["status"])
        (self.output / "release").touch()
        retry = self.cli("task", "retry", job["task_id"], "--json")
        self.task_ids.append(retry["task_id"])
        self.assertNotEqual(job["task_id"], retry["task_id"])
        result = self.wait_terminal(retry["task_id"])
        self.assertEqual("success", result["status"])
        self.assertEqual(["2", "3"], result["plan"]["ids"])
        for item in result["items"]:
            self.assertTrue(Path(item["image_paths"][0]).is_file())
            with ZipFile(item["export_files"]["zip"][0]) as archive:
                self.assertIsNone(archive.testzip())
        self.assertEqual("cancelled", self.store.read(job["task_id"])["status"])
        self.assertNotIn(
            "test-only-canary", self.store.path(job["task_id"], ".request.json").read_text(encoding="utf-8")
        )
        if os.name == "nt":
            consoles = list(self.root.glob("console-*.txt"))
            self.assertTrue(consoles)
            self.assertTrue(
                all(path.read_text(encoding="utf-8") == "0" for path in consoles), "A test process acquired a console"
            )

    def test_retry_preserves_original_directory_for_relative_config(self):
        origin, other = self.root / "origin", self.root / "other"
        origin.mkdir()
        other.mkdir()
        self.option_path.write_text("dir_rule:\n  rule: Bd_Pname\n  base_dir: downloads\n", encoding="utf-8")
        original = self.cli(
            "download",
            "--ids",
            "99",
            "--option",
            str(self.option_path),
            "--background",
            "--json",
            cwd=origin,
            expected=(0, 1),
        )
        self.task_ids.append(original["task_id"])
        self.assertEqual("failed", self.wait_terminal(original["task_id"])["status"])
        output = origin / "downloads"
        (output / "release").touch()
        retry = self.cli("task", "retry", original["task_id"], "--json", cwd=other)
        self.task_ids.append(retry["task_id"])
        finished = self.wait_terminal(retry["task_id"])
        self.assertEqual("success", finished["status"])
        self.assertTrue(output.samefile(finished["plan"]["base_dir"]))
        foreground = self.cli("task", "retry", original["task_id"], "--foreground", "--json", cwd=other)
        self.task_ids.append(foreground["task_id"])
        self.assertTrue(output.samefile(foreground["plan"]["base_dir"]))
        self.assertFalse((other / "downloads").exists())

    def test_startup_queries_do_not_compete_for_workers_execution_lease(self):
        state = self.store.reserve({"ids": ["1"], "kind": "album"}, self.option_path, PROJECT, 15)
        with patch.object(self.store, "acquire", side_effect=AssertionError("Query stole startup lease")):
            self.assertEqual("queued", self.store.read(state["task_id"])["status"])
            self.assertEqual("cancel_requested", self.store.request_cancel(state["task_id"])["status"])
            self.assertTrue(self.store.cancel_requested(state["task_id"], state["owner_nonce"]))

    def test_interrupted_startup_is_persisted_before_late_worker_can_download(self):
        parameters = {
            "ids": ["1"],
            "kind": "album",
            "album_workers": 1,
            "photo_workers": 1,
            "image_workers": 1,
            "export_formats": [],
        }
        state = self.store.reserve(parameters, self.option_path, PROJECT, 15)
        self.task_ids.append(state["task_id"])
        state["startup_deadline"] = time.time() + 0.1
        self.store.save(state)
        environment = {**self.environment, "JMAI_FIXTURE_START_DELAY": "0.8"}
        worker = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "jmcomic_ai.worker",
                "--task-id",
                state["task_id"],
                "--task-dir",
                str(self.task_dir),
            ],
            cwd=str(PROJECT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=NO_WINDOW,
        )
        try:
            time.sleep(0.15)
            observed = self.store.read(state["task_id"])
            self.assertEqual("interrupted", observed["status"])
            self.assertEqual(
                "interrupted", json.loads(self.store.path(state["task_id"]).read_text(encoding="utf-8"))["status"]
            )
            worker.communicate(timeout=15)
            self.assertEqual(1, worker.returncode)
            self.assertEqual("interrupted", self.store.read(state["task_id"])["status"])
            self.assertFalse((self.output / "activity.log").exists())
            self.assertFalse(any(self.output.rglob("*.jpg")))
        finally:
            if worker.poll() is None:
                worker.kill()
            worker.communicate(timeout=10)

    def test_interruption_is_published_while_probe_lease_is_still_held(self):
        state = self.store.reserve({"ids": ["1"], "kind": "album"}, self.option_path, PROJECT, 15)
        state.update(status="running", ready=True)
        self.store.save(state)
        save = self.store.save

        def save_under_probe(report):
            self.assertTrue(self.store.owner_alive(state["task_id"]))
            save(report)

        with patch.object(self.store, "save", side_effect=save_under_probe):
            self.assertEqual("interrupted", self.store.read(state["task_id"])["status"])
        self.assertFalse(self.store.owner_alive(state["task_id"]))

    def test_owner_finishing_during_query_returns_final_report(self):
        state = self.store.reserve({"ids": ["1"], "kind": "album"}, self.option_path, PROJECT, 15)
        state.update(status="running", ready=True)
        self.store.save(state)
        acquire = self.store.acquire

        def owner_finishes(task_id):
            state.update(status="success", unfinished_ids=[])
            self.store.save(state)
            return acquire(task_id)

        with patch.object(self.store, "acquire", side_effect=owner_finishes):
            result = self.store.read(state["task_id"])
        self.assertEqual("success", result["status"])
        self.assertEqual([], result["unfinished_ids"])

    def test_duplicate_worker_does_not_repeat_a_finished_task(self):
        job = self.start("1")
        self.wait_terminal(job["task_id"])
        before = (self.output / "activity.log").read_text(encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "jmcomic_ai.worker",
                "--task-id",
                job["task_id"],
                "--task-dir",
                str(self.task_dir),
            ],
            cwd=str(PROJECT),
            env=self.environment,
            capture_output=True,
            timeout=15,
            creationflags=NO_WINDOW,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, (self.output / "activity.log").read_text(encoding="utf-8"))

    def test_cancel_before_worker_ready(self):
        parameters = {
            "ids": ["2"],
            "kind": "album",
            "album_workers": 1,
            "photo_workers": None,
            "image_workers": None,
            "export_formats": [],
        }
        state = self.store.reserve(parameters, self.option_path, PROJECT, 15)
        task_id = state["task_id"]
        self.task_ids.append(task_id)
        self.assertEqual("cancel_requested", self.store.request_cancel(task_id)["status"])
        result = subprocess.run(
            [sys.executable, "-B", "-m", "jmcomic_ai.worker", "--task-id", task_id, "--task-dir", str(self.task_dir)],
            env=self.environment,
            cwd=str(PROJECT),
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=NO_WINDOW,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("cancelled", self.store.read(task_id)["status"])
        self.assertFalse((self.output / "activity.log").exists())

    def test_timeout_control_write_failure_still_returns_recoverable_task_id(self):
        with patch.dict(os.environ, self.environment):
            with patch(
                "jmcomic_ai.task_store.TaskStore.write_cancel", side_effect=PermissionError("Controlled I/O failure")
            ):
                state = launch_background(
                    ["2"], option_path=self.option_path, task_dir=self.task_dir, startup_timeout=0
                )
        self.task_ids.append(state["task_id"])
        self.assertEqual("error", state["status"])
        self.assertFalse(state["cancellation_requested"])
        self.assertEqual(str(self.store.path(state["task_id"])), state["report_path"])
        self.store.request_cancel(state["task_id"])
        self.assertEqual("cancelled", self.wait_terminal(state["task_id"])["status"])

    def test_readiness_io_error_returns_task_id_and_requests_cancellation(self):
        with patch.dict(os.environ, self.environment):
            with patch("jmcomic_ai.background.read_json", side_effect=PermissionError("Controlled sharing failure")):
                state = launch_background(["2"], option_path=self.option_path, task_dir=self.task_dir)
        self.task_ids.append(state["task_id"])
        self.assertEqual("error", state["status"])
        self.assertTrue(state["cancellation_requested"])
        self.assertEqual("cancelled", self.wait_terminal(state["task_id"])["status"])
        self.assertFalse(any(self.output.rglob("*.jpg")))

    def test_startup_error_is_persisted_and_no_live_owner(self):
        self.option_path.write_text("download: [", encoding="utf-8")
        state = self.cli(
            "download", "--ids", "1", "--background", "--option", str(self.option_path), "--json", expected=1
        )
        self.task_ids.append(state["task_id"])
        self.assertEqual("failed", state["status"])
        self.assertEqual("failed", self.store.read(state["task_id"])["status"])

    def test_dead_worker_is_interrupted_not_permanently_running(self):
        state = self.start("2")
        task_id = state["task_id"]
        pid = state["owner_pid"]
        self.assertNotEqual(os.getpid(), pid)
        if os.name == "nt":
            result = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=NO_WINDOW)
            self.assertEqual(0, result.returncode)
        else:
            import signal

            os.kill(pid, signal.SIGKILL)
        final = self.wait_terminal(task_id)
        self.assertEqual("interrupted", final["status"])
        self.assertEqual(["2"], final["unfinished_ids"])

    def test_startup_timeout_preserves_cancel_for_delayed_worker(self):
        with patch.dict(os.environ, {**self.environment, "JMAI_FIXTURE_START_DELAY": "0.8"}):
            state = launch_background(["2"], option_path=self.option_path, task_dir=self.task_dir, startup_timeout=0.1)
        self.task_ids.append(state["task_id"])
        self.assertEqual("error", state["status"])
        self.assertEqual("cancelled", self.wait_terminal(state["task_id"])["status"])
        self.assertFalse((self.output / "activity.log").exists())

    def test_lease_is_visible_across_processes_and_cannot_be_replaced_by_pid(self):
        state = self.store.reserve({"ids": ["1"], "kind": "album"}, self.option_path, PROJECT, 1)
        lease = self.store.acquire(state["task_id"])
        try:
            # A bogus PID does not change the actual lock owner's liveness.
            state.update(owner_pid=99999999, ready=True, status="running")
            self.store.save(state)
            observed = self.cli("task", "status", state["task_id"], "--json")
            self.assertEqual("running", observed["status"])
        finally:
            lease.close()
        self.assertEqual("interrupted", self.store.read(state["task_id"])["status"])


if __name__ == "__main__":
    unittest.main()
