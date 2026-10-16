"""Shared download workflow for the main CLI and installed Skill scripts."""

import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jmcomic_ai.task_store import TERMINAL

if TYPE_CHECKING:
    from jmcomic_ai.core import JmcomicService


async def run_download(service: "JmcomicService", args: Any, ids: list[str], kind: str) -> dict[str, Any]:
    from jmcomic_ai.downloads import DownloadTasks

    manager = getattr(service, "_downloads", None)
    if isinstance(manager, DownloadTasks):

        def announce(state):
            print(
                f"Task: {state['task_id']}\nReport: {state['report_path']}\nLog: {state['log_path']}", file=sys.stderr
            )

        manager.on_started = announce
    formats = [item.strip() for item in (getattr(args, "export", None) or "").split(",") if item.strip()]
    workers = {name: getattr(args, name, None) for name in ("album_workers", "photo_workers", "image_workers")}
    if getattr(args, "plan", False):
        return await service.plan_download(
            ids, kind=kind, **workers, export_formats=formats, include_details=getattr(args, "details", False)
        )
    retry = getattr(args, "retry", None)
    if retry:
        result = await service.retry_download(retry)
        if result.get("status") == "error" or result.get("status") in TERMINAL:
            return result
        task_id = result["task_id"]
        try:
            return await service._downloads.wait(task_id)
        except asyncio.CancelledError as error:
            if hasattr(error, "download_result"):
                print_result(error.download_result, getattr(args, "json", False))
            raise
    try:
        return await service.download_batch(ids, kind=kind, **workers, export_formats=formats)
    except asyncio.CancelledError as error:
        if hasattr(error, "download_result"):
            print_result(error.download_result, getattr(args, "json", False))
        raise


def print_result(result: dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {result['status']}")
        if "plan" in result:
            print(f"Task: {result['task_id']}")
            print(f"Log: {result['log_path']}")
            print(f"Report: {result['report_path']}")
            print(f"Progress: {result.get('completed_images', 0)} images processed")
            for item in result["items"]:
                print(f"  {item['id']}: {item['status']} {item.get('download_path', item.get('error') or '')}")
                if item.get("actual_id") and item["actual_id"] != item["id"]:
                    print(f"    Upstream {result['plan']['kind']} ID: {item['actual_id']}")
                for suffix, paths in item.get("export_files", {}).items():
                    for path in paths:
                        print(f"    {suffix}: {path}")
            if result["unfinished_ids"] and not result.get("report_error"):
                print(f"Retry: jmai task retry {result['task_id']} (use the same --task-dir)")
        elif "details" in result or result["status"] == "success":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("error"):
            print(result["error"])
        if result.get("report_error"):
            print(f"Task report could not be saved: {result['report_error']}")


def add_download_arguments(parser: Any) -> None:
    parser.add_argument("--album-workers", type=int, help="Concurrent albums; album mode only (default: 3)")
    parser.add_argument(
        "--photo-workers", type=int, help="Concurrent chapters across the batch (default: download.threading.photo)"
    )
    parser.add_argument(
        "--image-workers", type=int, help="Concurrent images across the batch (default: download.threading.image)"
    )
    parser.add_argument("--export", help="Download and export: zip,pdf,long_img (comma-separated)")
    parser.add_argument("--plan", action="store_true", help="Preview without downloading images")
    parser.add_argument("--details", action="store_true", help="With --plan, request metadata and chapter IDs")
    parser.add_argument("--json", action="store_true", help="Emit one JSON result")
    parser.add_argument("--background", action="store_true", help="Launch a temporary worker and return task ID")
    parser.add_argument("--task-dir", help="Task directory (default: JM_TASK_LOG_DIR or ~/.jmcomic-ai/logs)")


def read_ids(ids: str | None, file: str | None) -> list[str]:
    if ids:
        return [value.strip() for value in ids.split(",") if value.strip()]
    if file:
        return [
            value.strip()
            for value in Path(file).read_text(encoding="utf-8-sig").splitlines()
            if value.strip() and not value.lstrip().startswith("#")
        ]
    return []


def script_exit(result: dict[str, Any], as_json: bool) -> None:
    print_result(result, as_json)
    if result["status"] not in {"success", "queued", "running", "cancel_requested", "cancelling"}:
        sys.exit(1)
