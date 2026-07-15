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
        typer.echo(f"Starting MCP Server ({transport_value}) using option: {service.option_path}", err=True)

        # Print configuration hint
        import json

        typer.echo(
            "\n💡 Copy and paste the following configuration into your MCP client config (Cursor, Windsurf, Claude Desktop, "
            "etc.)",
            err=True)

        if transport == TransportType.stdio:
            config = {"mcpServers": {"jmcomic-ai": {"command": "jmai", "args": ["mcp", "stdio"]}}}
            typer.echo("\n--- MCP Client Config (STDIO Mode) ---", err=True)
            typer.echo(json.dumps(config, indent=2), err=True)
            typer.echo("----------------------------------------------------\n", err=True)

        elif transport == TransportType.sse:
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
        typer.secho("Invalid selection. Enter 1-4 or claude/codex/gemini/all.", fg=typer.colors.RED)


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
        typer.secho("[*] Hint: Pass a custom PATH to override platform directories", fg=typer.colors.CYAN)

    # 1. Preview
    typer.secho("\n[ Installation Structure Preview ]", fg=typer.colors.BRIGHT_MAGENTA, bold=True)
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

    typer.echo(f"Skills installed successfully for: {', '.join(installed_platforms)}")


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
    existing_previews = {name: preview for name, preview in previews.items() if preview["exists"]}
    if not existing_previews:
        typer.secho("[*] Skipped: No jmcomic skill directory found for the selected targets", fg=typer.colors.YELLOW)
        return

    typer.secho("\n[ Uninstallation Preview ]", fg=typer.colors.BRIGHT_RED, bold=True)
    typer.secho("THE FOLLOWING DIRECTORY AND FILES WILL BE DELETED:", fg=typer.colors.RED)
    for platform_name, preview in existing_previews.items():
        typer.echo(f"[{platform_name}] Path: {preview['skill_target_dir']}")
        typer.echo("File Tree:")
        for file_path in preview["files"]:
            typer.echo(f"  - {file_path}")

    typer.echo("\nOnly the specific skill folder (jmcomic) will be removed. Your other skills remain safe.")
    typer.echo("")

    # 2. Confirmation
    if yes or typer.confirm("Are you sure you want to PERMANENTLY DELETE the 'jmcomic' skill folder?", default=False):
        uninstalled_platforms = []
        for platform_name, preview in existing_previews.items():
            if manager.uninstall(preview["target_dir"]):
                uninstalled_platforms.append(platform_name)
        typer.echo(f"Skills uninstalled successfully for: {', '.join(uninstalled_platforms)}")


# Option group
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
