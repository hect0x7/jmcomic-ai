import json
from enum import Enum
from pathlib import Path

import typer

from jmcomic_ai import __version__
from jmcomic_ai.core import JmcomicService, resolve_option_path


def version_callback(value: bool):
    """
    Callback function to display version and exit.

    Args:
        value: If True, displays version and exits the program.
    """
    if value:
        typer.echo(f"jmai version: {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="jmcomic-ai",
    help="JMComic AI Agent Interface",
    add_completion=True,
    no_args_is_help=True,
)


@app.callback()
def main(
        version: bool | None = typer.Option(
            None,
            "--version",
            "-v",
            help="Show the version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
):
    """
    JMComic AI Agent Interface
    """
    pass


class TransportType(str, Enum):
    stdio = "stdio"  # Standard I/O (for local subprocess mode)
    sse = "sse"  # Server-Sent Events (recommended for Claude Desktop)
    http = "http"  # streamable_http


@app.command()
def mcp(
        transport: TransportType = typer.Argument(
            TransportType.sse, help="Transport mode: 'sse' (default), 'stdio', or 'http'"
        ),
        option: Path | None = typer.Option(None, "--option", help="Path to jmcomic option file"),
        port: int = typer.Option(8000, help="Port for server (ignored for stdio)"),
        host: str = typer.Option("127.0.0.1", help="Host for server (ignored for stdio)"),
        reload: bool = typer.Option(False, "--reload", help="Auto-reload server on file changes"),
):
    """
    Start the MCP Server.

    Transport modes:
    - sse: Server-Sent Events (default, recommended for Claude Desktop)
    - stdio: Standard Input/Output (for local subprocess mode)
    - http: Streamable HTTP (for production deployments, horizontal scaling)

    Note: SSE transport is deprecated in MCP spec, but still supported by Claude Desktop.
    Consider using 'http' (Streamable HTTP) for new deployments.
    """
    # Defer import to avoid circular dependency or early loading
    from jmcomic_ai.mcp.server import run_server

    transport_value: str = transport.value

    if reload:
        from jmcomic_ai.mcp.reloader import run_with_reloader

        src_path = Path(__file__).parent.parent
        run_with_reloader(src_path)
    else:
        # Initialize service only when actually running the server (not the monitor process)
        service = JmcomicService(str(option) if option else None)
        if transport != TransportType.stdio:
            typer.echo(f"Starting MCP Server ({transport_value}) using option: {service.option_path}", err=True)

            typer.echo(
                "\n💡 Copy and paste the following configuration into your MCP client config (Cursor, Windsurf, "
                "Claude Desktop, etc.)",
                err=True,
            )

        if transport == TransportType.sse:
            config = {"mcpServers": {"jmcomic-ai": {"url": f"http://{host}:{port}/sse"}}}
            typer.echo("\n--- MCP Client Config (SSE Mode) ---", err=True)
            typer.echo(json.dumps(config, indent=2), err=True)
            typer.echo("----------------------------------------------\n", err=True)

        elif transport == TransportType.http:
            config = {"mcpServers": {"jmcomic-ai": {"url": f"http://{host}:{port}/mcp"}}}
            typer.echo("\n--- MCP Client Config (HTTP Streaming Mode) ---", err=True)
            typer.echo(json.dumps(config, indent=2), err=True)
            typer.echo("---------------------------------------------\n", err=True)

        run_server(transport_value, service, host=host, port=port)


@app.command("update")
def update_self(
        dry_run: bool = typer.Option(False, "--dry-run", help="Show the update strategy without changing anything"),
):
    """Update jmcomic-ai using the current installation method."""
    from jmcomic_ai.updater import UpdateError, detect_update_strategy, format_update_command, run_update

    try:
        strategy = detect_update_strategy()
    except UpdateError as error:
        typer.secho(f"Cannot update jmcomic-ai: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Current version: {__version__}")
    typer.echo(f"Update method: {strategy.name}")
    typer.echo(f"Command: {format_update_command(strategy)}")
    if dry_run:
        typer.echo("Dry run complete; no changes were made.")
        return

    try:
        update_result = run_update(strategy)
    except (OSError, UpdateError) as error:
        typer.secho(f"Failed to start the updater: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error

    if update_result.return_code != 0:
        typer.secho(f"Update failed with exit code {update_result.return_code}.", fg=typer.colors.RED, err=True)
        raise typer.Exit(update_result.return_code if 1 <= update_result.return_code <= 255 else 1)

    if update_result.scheduled:
        typer.secho(
            "Update scheduled. It will start after jmai exits; see ~/.jmcomic-ai/update.log for the result.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho("Update completed. Restart jmai and run `jmai --version` to verify it.", fg=typer.colors.GREEN)


skills_app = typer.Typer(name="skills", help="Manage generic skills resources", no_args_is_help=True)
app.add_typer(skills_app, name="skills")


@skills_app.callback(invoke_without_command=True)
def skills_shortcuts(
        ctx: typer.Context,
        install_shortcut: bool = typer.Option(False, "--install", "-i", help="Interactive skill installation"),
        uninstall_shortcut: bool = typer.Option(False, "--uninstall", "-u", help="Interactive skill uninstallation"),
):
    """Use -i/-u as shortcuts for the install/uninstall subcommands."""
    if ctx.invoked_subcommand is not None:
        return
    if install_shortcut and uninstall_shortcut:
        raise typer.BadParameter("Choose either --install/-i or --uninstall/-u, not both")
    if install_shortcut:
        install_skills(target_dir=None, platform=None, force=False, yes=False)
    elif uninstall_shortcut:
        uninstall_skills(target_dir=None, platform=None, yes=False)


def _prompt_skill_platform(action: str) -> str:
    """Prompt for a supported Agent Skills platform."""
    choices = {
        "1": "claude",
        "2": "codex",
        "3": "gemini",
        "4": "all",
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
        "all": "all",
    }
    typer.secho(f"\nSelect platforms to {action} the jmcomic skill:", fg=typer.colors.BRIGHT_CYAN, bold=True)
    typer.echo("  1. Claude")
    typer.echo("  2. Codex")
    typer.echo("  3. Gemini CLI")
    typer.echo("  4. All platforms")

    while True:
        selection = typer.prompt("Platform", default="4").strip().lower()
        if selection in choices:
            return choices[selection]
        typer.secho(
            "Invalid selection. Enter 1-4 or claude/codex/gemini/all.",
            fg=typer.colors.RED,
        )


@skills_app.command("install")
def install_skills(
        target_dir: Path | None = typer.Argument(
            None, help="Custom parent directory to install the jmcomic skill into"
        ),
        platform: str | None = typer.Option(
            None, "--platform", "-p", help="Target platform: claude, codex, gemini, or all"
        ),
        force: bool = typer.Option(False, "--force", "-f", help="Force overwrite existing files"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Install built-in skill definitions (SKILL.md, etc.) to a directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    manager = SkillManager()

    if target_dir is not None:
        target_dirs = {"custom": target_dir.resolve()}
        typer.echo(f"[*] Target parent directory: {target_dirs['custom']}")
    else:
        selected_platform = platform or ("claude" if yes else _prompt_skill_platform("install"))
        try:
            target_dirs = manager.get_platform_target_dirs(selected_platform)
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--platform") from error
        typer.secho(f"[*] Installing for platform selection: {selected_platform}", fg=typer.colors.CYAN)
        typer.secho(
            "[*] Hint: Pass a custom PATH to override platform directories",
            fg=typer.colors.CYAN,
        )

    # 1. Preview
    typer.secho(
        "\n[ Installation Structure Preview ]",
        fg=typer.colors.BRIGHT_MAGENTA,
        bold=True,
    )
    for platform_name, platform_target_dir in target_dirs.items():
        preview = manager.get_install_preview(platform_target_dir)
        typer.echo(f"[{platform_name}] Target Directory: {preview['skill_target_dir']}")
        typer.echo("File Tree:")
        for file_path in preview["files"]:
            typer.echo(f"  - {file_path}")
    typer.echo("")

    # 2. Confirmation (unless -y is passed)
    if not yes:
        if not typer.confirm("Proceed with installation?", default=True):
            typer.echo("Installation cancelled.")
            return

    installed_platforms = []
    for platform_name, platform_target_dir in target_dirs.items():
        platform_target_dir.mkdir(parents=True, exist_ok=True)

        if force:
            manager.install(platform_target_dir, overwrite=True)
        elif manager.has_conflicts(platform_target_dir):
            typer.echo(f"Warning: Some skill files already exist for {platform_name}.")
            if yes or typer.confirm(f"Overwrite existing files for {platform_name}?"):
                manager.install(platform_target_dir, overwrite=True)
            else:
                typer.echo("Skipping existing files.")
                manager.install(platform_target_dir, overwrite=False)
        else:
            manager.install(platform_target_dir)
        installed_platforms.append(platform_name)

    platforms_text = ", ".join(installed_platforms)
    typer.echo(f"Skills installed successfully for: {platforms_text}")


@skills_app.command("uninstall")
def uninstall_skills(
        target_dir: Path | None = typer.Argument(
            None, help="Custom parent directory to uninstall the jmcomic skill from"
        ),
        platform: str | None = typer.Option(
            None, "--platform", "-p", help="Target platform: claude, codex, gemini, or all"
        ),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Uninstall skills from the directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    manager = SkillManager()

    if target_dir is not None:
        target_dirs = {"custom": target_dir.resolve()}
        typer.echo(f"[*] Uninstalling from: {target_dirs['custom']}")
    else:
        selected_platform = platform or ("claude" if yes else _prompt_skill_platform("uninstall"))
        try:
            target_dirs = manager.get_platform_target_dirs(selected_platform)
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--platform") from error
        typer.secho(f"[*] Uninstalling for platform selection: {selected_platform}", fg=typer.colors.YELLOW)

    # 1. Preview
    previews = {
        platform_name: manager.get_uninstall_preview(platform_target_dir)
        for platform_name, platform_target_dir in target_dirs.items()
    }
    symlink_previews = {name: preview for name, preview in previews.items() if preview["is_symlink"]}
    for preview in symlink_previews.values():
        typer.secho(
            f"[*] Skipped externally managed skill symlink: {preview['skill_target_dir']} "
            f"-> {preview['link_target']}. Nothing was changed; remove the link manually if intended.",
            fg=typer.colors.YELLOW,
        )

    existing_previews = {
        name: preview for name, preview in previews.items() if preview["exists"] and not preview["is_symlink"]
    }
    if not existing_previews:
        typer.secho(
            "[*] Skipped: No removable jmcomic skill directory found for the selected targets",
            fg=typer.colors.YELLOW,
        )
        return

    typer.secho(
        "\n[ Uninstallation Preview ]",
        fg=typer.colors.BRIGHT_RED,
        bold=True,
    )
    typer.secho(
        "THE FOLLOWING DIRECTORY AND FILES WILL BE DELETED:",
        fg=typer.colors.RED,
    )
    for platform_name, preview in existing_previews.items():
        typer.echo(f"[{platform_name}] Path: {preview['skill_target_dir']}")
        typer.echo("File Tree:")
        for file_path in preview["files"]:
            typer.echo(f"  - {file_path}")

    typer.echo("\nOnly the specific skill folder (jmcomic) will be removed. Your other skills remain safe.")
    typer.echo("")

    # 2. Confirmation
    if yes or typer.confirm(
        "Are you sure you want to PERMANENTLY DELETE the 'jmcomic' skill folder?",
        default=False,
    ):
        uninstalled_platforms = []
        for platform_name, preview in existing_previews.items():
            if manager.uninstall(preview["target_dir"]):
                uninstalled_platforms.append(platform_name)
        platforms_text = ", ".join(uninstalled_platforms)
        typer.echo(f"Skills uninstalled successfully for: {platforms_text}")


# Option group
@app.command("download")
def download_command(
    ids: str | None = typer.Option(None, "--ids", help="Comma-separated IDs or links"),
    file: Path | None = typer.Option(None, "--file", help="IDs file, one per line"),
    kind: str = typer.Option("album", "--kind", help="album or photo (chapter)"),
    album_workers: int | None = typer.Option(None, "--album-workers", min=1, help="Concurrent albums; album mode only (default: 3)"),
    photo_workers: int | None = typer.Option(None, "--photo-workers", min=1, help="Concurrent chapters across the batch; defaults to download.threading.photo"),
    image_workers: int | None = typer.Option(None, "--image-workers", min=1, help="Concurrent images across the batch; defaults to download.threading.image"),
    export: str = typer.Option("", "--export", help="zip,pdf,long_img (comma-separated)"),
    plan: bool = typer.Option(False, "--plan", help="Preview without downloading images"),
    details: bool = typer.Option(False, "--details", help="With --plan, fetch metadata and chapter IDs"),
    retry: str | None = typer.Option(None, "--retry", help="Retry unfinished IDs of a previous task"),
    background: bool = typer.Option(False, "--background", help="Start a temporary worker; return task ID after readiness"),
    task_dir: Path | None = typer.Option(None, "--task-dir", help="Task directory (default: JM_TASK_LOG_DIR or ~/.jmcomic-ai/logs)"),
    json_output: bool = typer.Option(False, "--json", help="Emit one JSON result"),
    option: Path | None = typer.Option(None, "--option", help="Configuration file; reports use JM_TASK_LOG_DIR"),
):
    """Download a bounded batch, export in one step, or retry a previous task. Ctrl+C cooperatively stops it."""
    import asyncio
    from types import SimpleNamespace

    from jmcomic_ai.download_cli import print_result, read_ids, run_download

    if sum(bool(value) for value in (ids, file, retry)) != 1:
        raise typer.BadParameter("Choose exactly one of --ids, --file, or --retry")
    if details and not plan:
        raise typer.BadParameter("--details requires --plan")
    if background and plan:
        raise typer.BadParameter("--background cannot be combined with --plan")
    if retry and (plan or export or details or kind != "album" or any(value is not None for value in (album_workers, photo_workers, image_workers))):
        raise typer.BadParameter("--retry uses the original kind, worker limits and exports; do not combine options")
    try:
        values = read_ids(ids, str(file) if file else None)
        args = SimpleNamespace(
            export=export, album_workers=album_workers, photo_workers=photo_workers, image_workers=image_workers,
            plan=plan, details=details, retry=retry, json=json_output, background=background,
            option=str(option) if option else None, task_dir=task_dir,
        )
        if background:
            from jmcomic_ai.background import from_arguments

            result = from_arguments(args, values, kind)
        else:
            from jmcomic_ai.task_store import TaskStore, execution_directory

            selected_option = args.option
            previous = TaskStore(task_dir).read(retry) if retry else {}
            if selected_option is None:
                selected_option = previous.get("option_path") or None
            if selected_option:
                selected_option = str(Path(selected_option).expanduser().resolve())
            resolved_task_dir = str(TaskStore(task_dir).directory)
            with execution_directory(previous.get("execution_cwd")):
                service = JmcomicService(option_path=selected_option, task_log_dir=resolved_task_dir)
                result = asyncio.run(run_download(service, args, values, kind))
        print_result(result, json_output)
        if result["status"] not in ({"queued", "running", "cancel_requested", "cancelling", "success"} if background else {"success"}):
            raise typer.Exit(1)
    except (OSError, ValueError) as error:
        print_result({"status": "error", "error": str(error)}, json_output)
        raise typer.Exit(1) from error
    except KeyboardInterrupt:
        typer.echo("Download interrupted; its report is in JM_TASK_LOG_DIR (default ~/.jmcomic-ai/logs).", err=True)
        raise typer.Exit(130) from None


# Queries and cancellation deliberately do not initialize JmcomicService or read option.yml.
task_app = typer.Typer(name="task", help="Control local CLI/MCP download tasks without a running service", no_args_is_help=True)
app.add_typer(task_app, name="task")


@task_app.command("status")
def task_status(
    task_id: str = typer.Argument(..., help="Task ID returned by download"),
    task_dir: Path | None = typer.Option(None, "--task-dir"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Read a live or finished task, including results from another process."""
    from jmcomic_ai.download_cli import print_result
    from jmcomic_ai.task_store import TaskStore

    try:
        print_result(TaskStore(task_dir).read(task_id), json_output)
    except (OSError, ValueError) as error:
        print_result({"status": "error", "error": str(error)}, json_output)
        raise typer.Exit(1) from error


@task_app.command("cancel")
def task_cancel(
    task_id: str = typer.Argument(...),
    task_dir: Path | None = typer.Option(None, "--task-dir"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Request cooperative cancellation; poll status until terminal. Never force-kills a PID."""
    from jmcomic_ai.download_cli import print_result
    from jmcomic_ai.task_store import TaskStore

    try:
        print_result(TaskStore(task_dir).request_cancel(task_id), json_output)
    except (OSError, ValueError) as error:
        print_result({"status": "error", "error": str(error)}, json_output)
        raise typer.Exit(1) from error


@task_app.command("retry")
def task_retry(
    task_id: str = typer.Argument(...),
    task_dir: Path | None = typer.Option(None, "--task-dir"),
    option: Path | None = typer.Option(None, "--option", help="Override original option file"),
    foreground: bool = typer.Option(False, "--foreground", help="Wait in this process; default launches a background worker"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Create a new task for unfinished IDs. Original report is retained."""
    # Reuse the main command's validation, configuration and result/exit contract.
    download_command(ids=None, file=None, kind="album", album_workers=None, photo_workers=None,
                     image_workers=None, export="", plan=False, details=False, retry=task_id,
                     background=not foreground, task_dir=task_dir, json_output=json_output, option=option)


option_app = typer.Typer(name="option", help="Manage jmcomic option (configuration)", no_args_is_help=True)
app.add_typer(option_app, name="option")


@option_app.command("show")
def option_show():
    """Show current option file path and content"""
    resolved_path = resolve_option_path()
    typer.echo(f"Option file: {resolved_path}")
    typer.echo("---")
    if resolved_path.exists():
        typer.echo(resolved_path.read_text(encoding="utf-8"))
    else:
        typer.echo("Option file does not exist yet.")


@option_app.command("path")
def option_path():
    """Print option file path"""
    resolved_path = resolve_option_path()
    typer.echo(resolved_path)


@option_app.command("edit")
def option_edit():
    """Open option file in default editor"""
    import platform
    import subprocess

    resolved_path = resolve_option_path()
    path = str(resolved_path)

    if not resolved_path.exists():
        typer.echo(f"Option file does not exist: {path}")
        typer.echo("It will be created when you first use the service (e.g. jmai mcp).")
        return

    try:
        if platform.system() == "Windows":
            subprocess.run(["notepad", path])
        elif platform.system() == "Darwin":
            subprocess.run(["open", "-e", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception as e:
        typer.echo(f"Failed to open editor: {e}")
        typer.echo(f"Please manually edit: {path}")


if __name__ == "__main__":
    app()
