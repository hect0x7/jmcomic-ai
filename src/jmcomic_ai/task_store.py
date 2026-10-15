"""Local task reports, cooperative control requests and OS-owned execution leases."""

import errno
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

TERMINAL = {"success", "partial", "failed", "cancelled", "interrupted"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def execution_directory(directory: str | None):
    """Only used by the single-shot foreground CLI, never inside the MCP server."""
    previous = Path.cwd()
    try:
        if directory:
            os.chdir(directory)
        yield
    finally:
        if directory:
            os.chdir(previous)


def validate_task_id(task_id: str) -> str:
    if (
        not isinstance(task_id, str)
        or not task_id.startswith("batch-")
        or len(task_id) != 38
        or any(char not in "0123456789abcdef" for char in task_id[6:])
    ):
        raise ValueError("Invalid batch task_id")
    return task_id


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    """Publish a whole snapshot; control requests never overwrite the owner's report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8"
        ) as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
        for attempt in range(20):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.01)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    # Windows can briefly deny opening a destination while atomic replacement
    # is pending. Retry sharing violations rather than reporting a missing task.
    for attempt in range(20):
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return data
        except (PermissionError, FileNotFoundError):
            if attempt == 19:
                raise
            time.sleep(0.01)
    raise AssertionError("unreachable")


class TaskLease:
    """The OS releases the lock even on abrupt process death; PID reuse is irrelevant."""

    def __init__(self, path: Path):
        self.path = path
        self.stream: BinaryIO | None = None

    def acquire(self) -> "TaskLease":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            if self.path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import importlib

                fcntl: Any = importlib.import_module("fcntl")
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            stream.close()
            raise
        self.stream = stream
        return self

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


class TaskStore:
    def __init__(self, directory: str | Path | None = None):
        self.directory = (
            Path(directory or os.getenv("JM_TASK_LOG_DIR") or Path.home() / ".jmcomic-ai" / "logs")
            .expanduser()
            .resolve()
        )

    def path(self, task_id: str, suffix: str = ".json") -> Path:
        return self.directory / f"{validate_task_id(task_id)}{suffix}"

    def acquire(self, task_id: str) -> TaskLease:
        return TaskLease(self.path(task_id, ".lock")).acquire()

    def owner_alive(self, task_id: str) -> bool:
        try:
            lease = self.acquire(task_id)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return True
            raise
        lease.close()
        return False

    def save(self, state: dict[str, Any]) -> None:
        atomic_json(self.path(state["task_id"]), state)

    def read(self, task_id: str) -> dict[str, Any]:
        path = self.path(task_id)
        try:
            state = read_json(path)
        except FileNotFoundError:
            raise ValueError("Task not found; use the same --task-dir or JM_TASK_LOG_DIR")
        if state.get("task_id") != task_id or not isinstance(state.get("plan"), dict):
            raise ValueError("Invalid task report")
        if state["status"] not in TERMINAL:
            startup_pending = not state.get("ready", True) and time.time() < state.get("startup_deadline", 0)
            # Queries must not take the lease before the initial worker starts.
            if not startup_pending:
                try:
                    probe = self.acquire(task_id)
                except OSError as error:
                    if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        raise
                else:
                    try:
                        # Recheck under ownership: final publication may have
                        # happened after the first read. Persist interruption
                        # before releasing the lease so a late worker cannot
                        # resume a task already reported as terminal.
                        state = read_json(path)
                        if state["status"] not in TERMINAL:
                            state.update(
                                status="interrupted",
                                finished_at=utc_now(),
                                error="The task owner exited before writing a terminal report; retry unfinished IDs",
                            )
                            self.save(state)
                        return state
                    finally:
                        probe.close()
            if self.cancel_requested(task_id, state.get("owner_nonce")) and state["status"] != "cancelling":
                state["status"] = "cancel_requested"
        return state

    def cancel_requested(self, task_id: str, owner_nonce: str | None) -> bool:
        path = self.path(task_id, ".cancel.json")
        if not owner_nonce or not path.is_file():
            return False
        request = read_json(path)
        return bool(request.get("owner_nonce") == owner_nonce)

    def write_cancel(self, task_id: str, owner_nonce: str) -> None:
        atomic_json(
            self.path(task_id, ".cancel.json"),
            {
                "task_id": task_id,
                "owner_nonce": owner_nonce,
                "requested_at": utc_now(),
            },
        )

    def request_cancel(self, task_id: str) -> dict[str, Any]:
        state = self.read(task_id)
        if state["status"] in TERMINAL:
            return state
        self.write_cancel(task_id, state["owner_nonce"])
        return self.read(task_id)

    def reserve(
        self, parameters: dict[str, Any], option_path: Path, cwd: Path, startup_timeout: float
    ) -> dict[str, Any]:
        task_id = f"batch-{uuid4().hex}"
        state = {
            "schema_version": 1,
            "task_id": task_id,
            "status": "queued",
            "created_at": utc_now(),
            "owner_nonce": uuid4().hex,
            "owner_pid": None,
            "ready": False,
            "startup_deadline": time.time() + max(startup_timeout, 30),
            "execution_mode": "background",
            "execution_cwd": str(cwd),
            "option_path": str(option_path),
            "plan": parameters,
            "completed_images": 0,
            "progress": {},
            "items": [],
            "unfinished_ids": list(parameters["ids"]),
            "failed_ids": [],
            "error": None,
            "report_path": str(self.path(task_id)),
            "log_path": str(self.path(task_id, ".log")),
            "worker_log_path": str(self.path(task_id, ".worker.log")),
        }
        self.save(state)
        # Configuration is a path reference, never a persisted credentials snapshot.
        atomic_json(
            self.path(task_id, ".request.json"),
            {
                "task_id": task_id,
                "owner_nonce": state["owner_nonce"],
                "parameters": parameters,
                "option_path": str(option_path),
                "cwd": str(cwd),
            },
        )
        return state


def retry_parameters(state: dict[str, Any]) -> dict[str, Any]:
    if state["status"] not in TERMINAL or not state.get("unfinished_ids"):
        raise ValueError("Only a finished task with unfinished IDs can be retried")
    plan = state["plan"]
    workers = plan.get("workers", {})
    album_workers = plan.get("album_workers")
    photo_workers = plan.get("photo_workers", workers.get("photo"))
    if "concurrency" in plan:
        if plan["kind"] == "album":
            album_workers = plan["concurrency"]
        else:
            photo_workers = plan["concurrency"]
    return {
        "ids": list(state["unfinished_ids"]),
        "kind": plan["kind"],
        "album_workers": album_workers,
        "photo_workers": photo_workers,
        "image_workers": plan.get("image_workers", workers.get("image")),
        "export_formats": plan.get("export_formats", []),
    }
