"""Internal, short-lived owner process for one explicit CLI background batch."""

import argparse
import asyncio
import json
from typing import Any

from jmcomic_ai.task_store import TERMINAL, TaskStore, atomic_json, utc_now


async def execute(store: TaskStore, task_id: str) -> dict[str, Any]:
    from jmcomic_ai.core import JmcomicService

    request = json.loads(store.path(task_id, ".request.json").read_text(encoding="utf-8"))
    lease = store.acquire(task_id)
    state = store.read(task_id)
    try:
        if request.get("owner_nonce") != state.get("owner_nonce"):
            raise ValueError("Task request identity does not match report")
        if state["status"] in TERMINAL:
            return state
        import os

        state.update(owner_pid=os.getpid(), heartbeat_at=utc_now())
        store.save(state)
        if store.cancel_requested(task_id, state["owner_nonce"]):
            state.update(status="cancelled", finished_at=utc_now())
            store.save(state)
            return state
        service = JmcomicService(option_path=request["option_path"], task_log_dir=str(store.directory))
        parameters = request["parameters"]
        plan = service._downloads.plan(
            parameters["ids"],
            parameters["kind"],
            parameters["album_workers"],
            parameters["photo_workers"],
            parameters["image_workers"],
            parameters["export_formats"],
        )
        service._downloads.start(plan, task_id=task_id, lease=lease, initial_state=state)
        atomic_json(store.path(task_id, ".ready.json"), {"task_id": task_id, "owner_nonce": state["owner_nonce"]})
        return await service._downloads.wait(task_id)
    except Exception as error:
        # If the managed runner has started, its lease/report remain exclusively
        # owned by that runner. Initialization failures are still ours to publish.
        if "service" in locals() and task_id in service._downloads.runners:
            await service._downloads.wait(task_id)
            return service._downloads.get(task_id)
        state.update(status="failed", error=str(error), finished_at=utc_now())
        store.save(state)
        return state
    finally:
        lease.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal jmai background task executor")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-dir", required=True)
    args = parser.parse_args()
    try:
        state = asyncio.run(execute(TaskStore(args.task_dir), args.task_id))
    except (OSError, ValueError) as error:
        raise SystemExit(f"Worker initialization failed: {error}") from error
    raise SystemExit(0 if state["status"] in {"success", "cancelled"} else 1)


if __name__ == "__main__":
    main()
