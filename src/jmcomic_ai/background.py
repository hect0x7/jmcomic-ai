"""Explicit per-task launchers. No daemon, listener or persistent scheduling queue."""

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from jmcomic_ai.downloads import EXPORTS, normalize_ids
from jmcomic_ai.task_store import TERMINAL, TaskStore, read_json, retry_parameters, utc_now


def launch_background(
    ids: list[str],
    *,
    kind: str = "album",
    album_workers: int | None = None,
    photo_workers: int | None = None,
    image_workers: int | None = None,
    export_formats: list[str] | None = None,
    option_path: str | Path | None = None,
    task_dir: str | Path | None = None,
    startup_timeout: float = 15,
    execution_cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Start the installed worker and return only after readiness or an explicit error."""
    from jmcomic_ai.core import resolve_option_path

    ids = normalize_ids(ids)
    if kind not in {"album", "photo"}:
        raise ValueError("kind must be album or photo")
    if kind == "photo" and album_workers is not None:
        raise ValueError("album_workers applies only to album batches; use photo_workers")
    for name, value in (
        ("album_workers", album_workers),
        ("photo_workers", photo_workers),
        ("image_workers", image_workers),
    ):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
            raise ValueError(f"{name} must be a positive integer")
    formats = list(dict.fromkeys(export_formats or []))
    if any(fmt not in EXPORTS for fmt in formats):
        raise ValueError("export_formats supports zip, pdf, long_img")
    parameters = {
        "ids": ids,
        "kind": kind,
        "album_workers": album_workers,
        "photo_workers": photo_workers,
        "image_workers": image_workers,
        "export_formats": formats,
    }
    store = TaskStore(task_dir)
    option = resolve_option_path(str(Path(option_path).expanduser()) if option_path else None).expanduser().resolve()
    cwd = Path(execution_cwd or Path.cwd()).expanduser().resolve()
    if not cwd.is_dir():
        raise ValueError("Original execution directory no longer exists; cannot safely reuse relative paths")
    state = store.reserve(parameters, option, cwd, startup_timeout)
    task_id = state["task_id"]
    command = [
        sys.executable,
        "-B",
        "-m",
        "jmcomic_ai.worker",
        "--task-id",
        task_id,
        "--task-dir",
        str(store.directory),
    ]
    try:
        with store.path(task_id, ".worker.log").open("ab") as output:
            kwargs: dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": output,
                "stderr": output,
                "cwd": str(cwd),
                "close_fds": True,
            }
            if sys.platform == "win32":
                # CREATE_NO_WINDOW is ignored when combined with DETACHED_PROCESS.
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **kwargs)
            # Reap finished children in long-lived callers without waiting for
            # them on the launch path or retaining open stdout pipes.
            threading.Thread(target=process.wait, daemon=True).start()
    except OSError as error:
        state.update(status="failed", error=f"Could not launch download worker: {error}", finished_at=utc_now())
        store.save(state)
        return state

    try:
        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            state = store.read(task_id)
            ready_path = store.path(task_id, ".ready.json")
            ready = ready_path.is_file() and read_json(ready_path).get("owner_nonce") == state["owner_nonce"]
            if ready or state["status"] in TERMINAL:
                return state
            if process.poll() is not None:
                # After confirmed child death the launcher can acquire ownership
                # to publish a bootstrap failure, without racing a live report writer.
                lease = store.acquire(task_id)
                try:
                    state = store.read(task_id)
                    if state["status"] not in TERMINAL:
                        state.update(
                            status="failed",
                            finished_at=utc_now(),
                            error=f"Worker exited before readiness (exit {process.returncode}); see worker_log_path",
                        )
                        store.save(state)
                finally:
                    lease.close()
                return state
            time.sleep(0.05)
        # A delayed worker must still consume cancellation before starting work.
        store.write_cancel(task_id, state["owner_nonce"])
        state = store.read(task_id)
        return {
            **state,
            "status": "error",
            "error": "Worker startup timed out; cancellation requested. Query task status for cleanup.",
            "task_status": state["status"],
        }
    except BaseException as error:
        # Never leave an unacknowledged worker running after failed readiness
        # I/O or an interrupted launcher. Preserve its identity for recovery.
        cancellation_requested = False
        try:
            store.write_cancel(task_id, state["owner_nonce"])
            cancellation_requested = True
        except OSError:
            pass
        if not isinstance(error, (OSError, ValueError)):
            raise
        return {
            **state,
            "status": "error",
            "task_status": state["status"],
            "error": "Could not confirm worker readiness; query task status for cleanup",
            "cancellation_requested": cancellation_requested,
        }


def launch_retry(
    task_id: str,
    *,
    task_dir: str | Path | None = None,
    option_path: str | Path | None = None,
) -> dict[str, Any]:
    state = TaskStore(task_dir).read(task_id)
    return launch_background(
        **retry_parameters(state),
        task_dir=task_dir,
        option_path=option_path or state.get("option_path") or None,
        execution_cwd=state.get("execution_cwd"),
    )


def from_arguments(args: Any, ids: list[str], kind: str) -> dict[str, Any]:
    """Shared background launch path for main CLI and the installed Skill scripts."""
    if getattr(args, "plan", False) or getattr(args, "details", False):
        raise ValueError("--background cannot be combined with --plan or --details")
    task_dir = getattr(args, "task_dir", None)
    if getattr(args, "retry", None):
        return launch_retry(args.retry, task_dir=task_dir, option_path=getattr(args, "option", None))
    return launch_background(
        ids,
        kind=kind,
        option_path=getattr(args, "option", None),
        task_dir=task_dir,
        export_formats=[fmt.strip() for fmt in (getattr(args, "export", None) or "").split(",") if fmt.strip()],
        album_workers=getattr(args, "album_workers", None),
        photo_workers=getattr(args, "photo_workers", None),
        image_workers=getattr(args, "image_workers", None),
    )
