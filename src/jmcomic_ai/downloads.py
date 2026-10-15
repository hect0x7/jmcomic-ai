"""Bounded native batches and process-owned, cooperatively cancellable jobs."""

import asyncio
import copy
import os
import threading
from contextvars import copy_context
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from jmcomic import (
    DownloadCancelledException,
    DownloadControl,
    Feature,
    JmcomicException,
    JmcomicText,
    JmSyncRuntime,
    download_batch,
    get_jm_task_context,
    jm_task_context,
)

from jmcomic_ai.task_store import TERMINAL, TaskLease, TaskStore, utc_now

EXPORTS = {"zip": Feature.export_zip, "pdf": Feature.export_pdf, "long_img": Feature.export_long_img}


class ExportFailed(ValueError):
    def __init__(self, result: Any, formats: list[str]):
        super().__init__(f"Images downloaded but requested exports are missing: {', '.join(formats)}; see task log")
        self.result = result
        self.formats = formats


def normalize_ids(ids: list[str]) -> list[str]:
    if not isinstance(ids, list) or not ids or len(ids) > 500:
        raise ValueError("ids must contain 1..500 album or chapter IDs")
    parsed = []
    for value in ids:
        try:
            item = JmcomicText.parse_to_jm_id(str(value).strip())
        except JmcomicException as error:
            raise ValueError(str(error)) from error
        if not item.isascii() or not item.isdecimal() or int(item) < 1:
            raise ValueError(f"Invalid positive JM ID: {value}")
        parsed.append(str(int(item)))
    return list(dict.fromkeys(parsed))


class DownloadTasks:
    def __init__(self, service: Any):
        self.service = service
        self.jobs: dict[str, dict[str, Any]] = {}
        self.runners: dict[str, asyncio.Task] = {}
        self.controls: dict[str, DownloadControl] = {}
        self.lock = threading.RLock()
        self.store = TaskStore(service.task_log_dir)
        self.leases: dict[str, TaskLease] = {}
        self.on_started: Any = None

    def plan(
        self,
        ids: list[str],
        kind: str,
        album_workers: int | None,
        photo_workers: int | None,
        image_workers: int | None,
        export_formats: list[str] | None,
    ) -> dict[str, Any]:
        normalized = normalize_ids(ids)
        if kind not in {"album", "photo"}:
            raise ValueError("kind must be album or photo")
        for name, value in (
            ("album_workers", album_workers),
            ("photo_workers", photo_workers),
            ("image_workers", image_workers),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
                raise ValueError(f"{name} must be a positive integer")
        if kind == "photo" and album_workers is not None:
            raise ValueError("album_workers applies only to kind=album; use photo_workers for chapter batches")
        option = self.service.option
        album_workers = (album_workers if album_workers is not None else 3) if kind == "album" else None
        photo_workers = photo_workers if photo_workers is not None else option.download.threading.photo
        image_workers = image_workers if image_workers is not None else option.download.threading.image
        # Defaults follow the loaded upstream option; do not silently clamp configured worker counts.
        for name, value in (("photo_workers", photo_workers), ("image_workers", image_workers)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer; check download.threading")
        formats = list(dict.fromkeys(export_formats or []))
        if any(fmt not in EXPORTS for fmt in formats):
            raise ValueError("export_formats supports zip, pdf, long_img")
        if "pdf" in formats:
            import importlib.util

            if importlib.util.find_spec("img2pdf") is None:
                raise ValueError("PDF export requires img2pdf; install it with: pip install img2pdf")
        option = self.service.option
        return {
            "ids": normalized,
            "kind": kind,
            "album_workers": album_workers,
            "photo_workers": photo_workers,
            "image_workers": image_workers,
            "export_formats": formats,
            "duplicates_removed": len(ids) - len(normalized),
            "base_dir": str(Path(option.dir_rule.base_dir).expanduser().resolve()),
            "workers": {
                "album": album_workers,
                "photo": photo_workers,
                "image": image_workers,
            },
        }

    def start(
        self,
        plan: dict[str, Any],
        ctx: Any = None,
        *,
        task_id: str | None = None,
        lease: TaskLease | None = None,
        initial_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if sum(not task.done() for task in self.runners.values()) >= 4:
            raise ValueError("At most 4 batches may run at once; wait or cancel an existing task")
        # Completed reports remain on disk, so memory does not grow with server uptime.
        for retained_id in list(self.jobs):
            if len(self.jobs) < 100:
                break
            if self.jobs[retained_id]["status"] in TERMINAL:
                self.jobs.pop(retained_id)
                self.runners.pop(retained_id, None)
                self.controls.pop(retained_id, None)
        task_id = task_id or f"batch-{uuid4().hex}"
        report_path = self.service.task_log_dir / f"{task_id}.json"
        state = {
            **(initial_state or {}),
            "schema_version": 1,
            "owner_nonce": (initial_state or {}).get("owner_nonce", uuid4().hex),
            "owner_pid": os.getpid(),
            "heartbeat_at": utc_now(),
            "ready": True,
            "execution_mode": (initial_state or {}).get("execution_mode", "in_process"),
            "execution_cwd": (initial_state or {}).get("execution_cwd", os.getcwd()),
            "option_path": str(getattr(self.service, "option_path", "")),
            "task_id": task_id,
            "status": "queued",
            "created_at": (initial_state or {}).get("created_at", datetime.now(timezone.utc).isoformat()),
            "plan": copy.deepcopy(plan),
            "completed_images": 0,
            "progress": {jm_id: {"status": "queued", "completed_images": 0} for jm_id in plan["ids"]},
            "items": [],
            "unfinished_ids": list(plan["ids"]),
            "failed_ids": [],
            "report_path": str(report_path),
            "log_path": str(self.service.task_log_dir / f"{task_id}.log"),
            "error": None,
        }
        # Freeze configuration at submission, including runtime-only overrides.
        option = self.service.option.copy_option()
        for field in ("download", "client", "plugins"):
            original = getattr(option, field)
            setattr(option, field, type(original)(copy.deepcopy(original.src_dict)))
        # The downloader's sequential fast path also reads these fields. Updating
        # only Runtime would leave an original threading=1 setting serial even
        # when this task explicitly requests more workers.
        option.download.threading.photo = plan["photo_workers"]
        option.download.threading.image = plan["image_workers"]
        held_lease = lease or self.store.acquire(task_id)
        try:
            self._save(state)
            self.jobs[task_id] = state
            self.controls[task_id] = DownloadControl()
            self.leases[task_id] = held_lease
            if self.store.cancel_requested(task_id, state["owner_nonce"]):
                self.controls[task_id].cancel("Cancelled by external request before startup")
                state["status"] = "cancelling"
            self.runners[task_id] = asyncio.create_task(self._run(state, option, ctx))
        except BaseException:
            held_lease.close()
            raise
        if self.on_started is not None:
            try:
                self.on_started(self.get(task_id))
            except OSError:
                self.service.logger.warning("Could not announce started task: %s", task_id)
        return self.get(task_id)

    def _save(self, state: dict[str, Any]) -> None:
        with self.lock:
            snapshot = copy.deepcopy(state)
            self.store.save(snapshot)

    def get(self, task_id: str) -> dict[str, Any]:
        with self.lock:
            if task_id in self.jobs:
                return copy.deepcopy(self.jobs[task_id])
        return self.store.read(task_id)

    def cancel(self, task_id: str) -> dict[str, Any]:
        with self.lock:
            state = self.get(task_id)
            if state["status"] in TERMINAL:
                return state
            self.store.request_cancel(task_id)
            if task_id in self.jobs:
                self.controls[task_id].cancel("Cancelled by user")
                self.jobs[task_id]["status"] = "cancelling"
                return self.get(task_id)
        return self.store.read(task_id)

    def _poll_control(self, state: dict[str, Any]) -> None:
        if self.store.cancel_requested(state["task_id"], state["owner_nonce"]):
            self.controls[state["task_id"]].cancel("Cancelled by external request")
        with self.lock:
            if self.controls[state["task_id"]].is_cancelled and state["status"] not in TERMINAL:
                state["status"] = "cancelling"
            state["heartbeat_at"] = utc_now()
        self._save(state)

    async def wait(self, task_id: str) -> dict[str, Any]:
        runner = self.runners[task_id]
        try:
            await asyncio.shield(runner)
        except asyncio.CancelledError as error:
            self.controls[task_id].cancel("Caller disconnected or interrupted")
            # A Python thread cannot be force-killed. Drain it before releasing logs/runtime.
            await asyncio.shield(runner)
            error.download_result = self.get(task_id)  # type: ignore[attr-defined]
            raise
        return self.get(task_id)

    async def _run(self, state: dict[str, Any], option: Any, ctx: Any) -> None:
        task_id = state["task_id"]
        loop = asyncio.get_running_loop()
        worker = loop.run_in_executor(None, copy_context().run, self._blocking, state, option, ctx, loop)
        outcome: str | None = None
        try:
            while not worker.done():
                try:
                    self._poll_control(state)
                except (OSError, ValueError) as error:
                    # An IPC/report failure must not abandon a live download thread.
                    state["report_error"] = str(error)
                    self.service.logger.warning("Task control/report update failed: %s", task_id)
                await asyncio.wait([worker], timeout=0.25)
            outcome = await asyncio.shield(worker)
        except asyncio.CancelledError:
            self.controls[task_id].cancel("Server shutting down")
            outcome = await asyncio.shield(worker)
        except Exception as error:
            with self.lock:
                state.update(status="failed", error=str(error))
            self.service.logger.exception("Batch worker failed: %s", task_id)
        finally:
            # Keep the OS lease until all I/O/exports have settled and the final
            # report is published, including event-loop shutdown cancellation.
            try:
                if not worker.done():
                    self.controls[task_id].cancel("Task owner shutting down")
                    outcome = await asyncio.shield(worker)
            finally:
                with self.lock:
                    if outcome is not None:
                        state["status"] = outcome
                    elif state["status"] not in TERMINAL:
                        state.update(status="failed", error="Worker exited without a terminal result")
                    state["finished_at"] = utc_now()
                    state["heartbeat_at"] = utc_now()
                try:
                    self._save(state)
                except OSError as error:
                    state["report_error"] = str(error)
                    self.service.logger.exception("Could not persist batch report: %s", task_id)
                finally:
                    self.leases.pop(task_id).close()

    def _blocking(self, state: dict[str, Any], option: Any, ctx: Any, loop: Any) -> str:
        from jmcomic_ai.core import _build_progress_downloaders, _serialize_download_result

        plan = state["plan"]
        control = self.controls[state["task_id"]]
        album_factory, photo_factory = _build_progress_downloaders(ctx, loop, self.service.logger, threading)
        factory = album_factory if plan["kind"] == "album" else photo_factory
        manager = self

        def tracked_downloader(current_option):
            downloader = factory(current_option)
            after_image = downloader.after_image

            def track(image, path):
                after_image(image, path)
                with manager.lock:
                    state["completed_images"] += 1
                    jm_id = str(get_jm_task_context().get("jm_id", ""))
                    if jm_id in state["progress"]:
                        state["progress"][jm_id]["completed_images"] += 1

            downloader.after_image = track
            return downloader

        with self.service._download_task_log("download-batch", ",".join(plan["ids"]), state["task_id"]) as (
            _,
            log_path,
        ):
            with self.lock:
                state["log_path"] = str(log_path)
                state["status"] = "cancelling" if control.is_cancelled else "running"
                self._save(state)
            succeeded: dict[str, Any] = {}
            failed: dict[str, Any] = {}
            cancelled = False
            try:
                # Pools are shared by the entire batch and closed after every worker settles.
                with (
                    JmSyncRuntime(
                        # Upstream download_batch always launches top-level IDs on its album pool,
                        # even for photo IDs. Map the public chapter limit to that launcher only.
                        album_workers=plan["workers"]["album"] if plan["kind"] == "album" else plan["workers"]["photo"],
                        photo_workers=plan["workers"]["photo"],
                        image_workers=plan["workers"]["image"],
                    ) as runtime,
                    jm_task_context(runtime=runtime, control=control),
                ):
                    api = option.download_album if plan["kind"] == "album" else option.download_photo

                    def download_one(jm_id, _option, downloader, **kwargs):
                        with self.lock:
                            state["progress"][jm_id]["status"] = "running"
                        try:
                            item = api(jm_id, downloader=downloader, **kwargs)
                            missing = []
                            for fmt in plan["export_formats"]:
                                suffix = "png" if fmt == "long_img" else fmt
                                paths = item.manifest.export_filepath_dict.get(suffix, [])
                                if not paths or not all(Path(path).is_file() for path in paths):
                                    missing.append(fmt)
                            if missing:
                                raise ExportFailed(item, missing)
                            with self.lock:
                                state["progress"][jm_id].update(status="success", title=str(item.detail.name))
                                completed = {entry["id"]: entry for entry in state["items"]}
                                completed[jm_id] = {
                                    "id": jm_id,
                                    "status": "success",
                                    "title": str(item.detail.name),
                                    **_serialize_download_result(item),
                                }
                                state["items"] = [completed[jmid] for jmid in plan["ids"] if jmid in completed]
                                state["unfinished_ids"] = [jmid for jmid in plan["ids"] if jmid not in completed]
                            return item
                        except DownloadCancelledException:
                            # Cooperative cancellation is unfinished work, never an item failure.
                            raise
                        except Exception as error:
                            # Upstream cancellation carries completed results but omits BatchResult.failed.
                            # Retain each settled failure here before the batch can raise cancellation.
                            with self.lock:
                                failed[str(jm_id)] = error
                                state["progress"][jm_id].update(status="failed", error=str(error))
                            raise

                    try:
                        result = download_batch(
                            download_one,
                            plan["ids"],
                            option=option,
                            downloader=tracked_downloader,
                            download_type=plan["kind"],
                            control=control,
                            extra=[EXPORTS[fmt] for fmt in plan["export_formats"]],
                        )
                        succeeded = {str(item.detail.id): item for item in result}
                        failed.update(result.failed)
                    except DownloadCancelledException as error:
                        succeeded = {str(item.detail.id): item for item in error.completed_results}
                        cancelled = True
            except Exception as error:
                state["error"] = str(error)
                self.service.logger.exception("Batch failed")
            items = []
            for jm_id in plan["ids"]:
                if jm_id in succeeded:
                    item = succeeded[jm_id]
                    items.append(
                        {
                            "id": jm_id,
                            "status": "success",
                            "title": str(item.detail.name),
                            **_serialize_download_result(item),
                        }
                    )
                else:
                    failure = {
                        "id": jm_id,
                        "status": "failed" if jm_id in failed else "unfinished",
                        "error": str(failed[jm_id]) if jm_id in failed else state["error"],
                    }
                    item_error = failed.get(jm_id)
                    if isinstance(item_error, ExportFailed):
                        failure.update(_serialize_download_result(item_error.result))
                        failure["missing_exports"] = item_error.formats
                    items.append(failure)
            unfinished = [jm_id for jm_id in plan["ids"] if jm_id not in succeeded]
            final_status = "cancelled" if cancelled else "success" if not unfinished else "partial" if succeeded else "failed"
            with self.lock:
                for item in items:
                    state["progress"][item["id"]]["status"] = item["status"]
                state.update(
                    items=items,
                    unfinished_ids=unfinished,
                    failed_ids=[jm_id for jm_id in plan["ids"] if jm_id in failed],
                )
            self.service.logger.info("Batch finished: %s, unfinished=%s", final_status, unfinished)
        return final_status
