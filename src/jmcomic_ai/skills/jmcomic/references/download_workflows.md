# Downloads and tasks

## Download and preview

Use the installed `jmai` command for this workflow; it does not require an MCP service.

```bash
# Download albums and generate ZIPs
jmai download --ids 123,456 --export zip --json

# Inspect titles, page counts and chapter IDs before choosing chapters
jmai download --ids 123 --plan --details --json
jmai download --ids 123 --kind photo --export pdf --json
```

Without `--details`, `--plan` validates inputs and reports the configured output root and worker limits.
It does not request album metadata or images; configured initialization plugins retain their own behavior.
With `--details`, inspect each entry in `details`, including failed metadata lookups. Chapter IDs can
differ from album IDs; use the returned chapter IDs with `--kind photo`.

`--ids` accepts comma-separated IDs or links. `--file ids.txt` accepts one per line, UTF-8 BOM and
indented `#` comments. Positive IDs are normalized and deduplicated in input order; a request accepts
at most 500 input entries. Select configuration with `--option` or `JM_OPTION_PATH`.

## Background tasks, cancellation and retry

```bash
jmai download --ids 123,456 --background --export zip --json
# Replace <task_id> with the ID returned by the launch command:
jmai task status <task_id> --json
jmai task cancel <task_id> --json
# Once the original task has ended, retry its unfinished items:
jmai task retry <task_id> --json
```

The background launch returns after startup is confirmed. The launching command can exit while the
task continues. Keep `task_id`, `report_path` and `log_path` from its result. Use the same `--task-dir`
or `JM_TASK_LOG_DIR` for every task command; the default is `~/.jmcomic-ai/logs`. Querying and cancelling
do not load configuration or contact the site.

| State | Next action |
| --- | --- |
| `queued`, `running` | Query progress, or request cancellation if needed. |
| `cancel_requested`, `cancelling` | Cancellation is pending; continue querying. In-flight HTTP calls must settle. |
| `success` | All requested items and exports completed. Hand off their returned paths. |
| `partial`, `failed`, `cancelled`, `interrupted` | Inspect per-item errors and `unfinished_ids`; retry if requested. |

Cancellation retains completed items and partial files. Retry creates a new task for `unfinished_ids`,
using image cache where possible; completed items are excluded and the original report is preserved.
It keeps the original kind, worker limits, exports, option path and execution directory, while loading
current option contents. `task retry --option PATH` overrides the option file.

`task retry` defaults to background execution; add `--foreground` to wait for it. Ordinary
`jmai download` and `jmai download --retry <task_id>` wait in the foreground unless `--background`
is supplied. Foreground Ctrl+C cooperatively cancels and waits for cleanup; agents should use the task
commands to control background work. Tasks do not automatically restart after an owner or machine stops.

### Startup and storage errors

A launch error can still include a task ID and paths. Query that task before starting another batch:
launcher `status=error` is not the task's terminal state. Startup timeout requests cancellation even
if initialization has not finished. If `cancellation_requested=false`, the control request could not
be stored; retry cancellation after storage recovers and query until the task has ended.

## Worker limits and exports

| CLI flag | MCP argument | Scope and default |
| --- | --- | --- |
| `--album-workers` | `album_workers` | Simultaneous albums, default 3; only album batches. |
| `--photo-workers` | `photo_workers` | Chapters across the batch, including chapter-ID batches; defaults to `download.threading.photo`. |
| `--image-workers` | `image_workers` | Images across the batch; defaults to `download.threading.image` (20 upstream). |

All values must be positive integers. Explicit arguments affect only this task and do not save option
changes or silently clamp values. Chapter batches reject `album_workers`. Limits are per batch;
independent CLI background tasks do not share a global concurrency cap.

`--export` accepts `zip`, `pdf`, `long_img`, or combinations such as `zip,pdf`. Long-image files
are PNGs. PDF needs `img2pdf`; if missing, install it explicitly before retrying. Requested outputs
are checked after download. If export fails, inspect the item's error, available image paths and
`missing_exports`, then retry the unfinished item. Existing plugins still apply; deletion plugins
can remove source images.

## Results and exit codes

Task results contain per-ID `progress`, `completed_images`, ordered `items`, `failed_ids` and
`unfinished_ids`. `completed_images` includes cache hits. Use the final report after the task ends
for handoff; use each successful item's `image_paths` and `export_files` instead of predicting paths
or rescanning the configured directory. Report partial failures and cancellations accurately.

Foreground downloads exit 0 on complete success, 1 on task/business errors, 2 on CLI usage errors,
and 130 on Ctrl+C. With `--json`, normal results and business errors are one JSON document on stdout;
Typer usage errors use its error output and do not guarantee JSON. A successful `task status` query
exits 0 even when the queried task failed: inspect its JSON `status`.

Task reports contain titles and absolute paths, but do not serialize the full configuration or account
cookies. Treat reports and task logs as local runtime data. `JM_LOG_PATH` selects the global log file;
ordinary runtime logs are file-only. Keep terminal-progress plugins such as `download_progress` off
when consuming JSON or using MCP stdio; use task progress or MCP notifications instead.

## Script entrypoints

`batch_download.py` fixes album mode and `download_photo.py` fixes chapter mode. Both support
`--ids` / `--file`, `--option`, worker limits, exports, plan/details, background, task directory and
JSON flags. They do not accept `--kind` or `--retry`; use `jmai task` for task control.
See [scripts.md](scripts.md) for invoking the scripts with the package's Python environment.

## MCP tools

In an MCP client, use the registered tools instead of starting CLI commands for the same work:

- `plan_download` validates a batch; `include_details=true` fetches metadata.
- `download_batch` waits for completion and reports progress notifications.
- `start_download` returns a task ID; use `get_download_task`, `cancel_download` and `retry_download`
  to manage it. The state and unfinished-item rules above apply.

MCP tasks run inside the current server, so keep that server alive. Each server permits up to four
active batches; limits remain per batch. MCP retry uses the server's current configuration.
For a standalone short-lived command, use CLI `--background` rather than calling `start_download`
from a throwaway Python script.

The single-item `download_album` and `download_photo` tools remain available. Their results contain
`status` (`success`/`failed`), `download_path`, `duration`, `image_paths`, `export_files`,
`task_id`, `log_path` and `error`. Album results add `album_id` and `title`; photo results add
`photo_id` and `image_count`. Their task IDs identify download logs and are not batch-task handles
for the status/cancel/retry tools. Use `start_download` when cancellation or later retry is needed.
