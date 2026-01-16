from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from jmcomic_ai import __version__
from jmcomic_ai.core import JmcomicService, resolve_option_path


def version_callback(value: bool):
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
        version: Optional[bool] = typer.Option(
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


@skills_app.command("install")
def install_skills(
        target_dir: Path | None = typer.Argument(
            None, help="Directory to install skills into. Defaults to ~/.claude/skills/jmcomic"
        ),
        force: bool = typer.Option(False, "--force", "-f", help="Force overwrite existing files"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Install built-in skill definitions (SKILL.md, etc.) to a directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    manager = SkillManager()

    if target_dir is None:
        # Default to ~/.claude/skills (Standard for Claude Desktop)
        target_dir = Path.home() / ".claude" / "skills"
        typer.secho(f"[*] Path not specified, using default: {target_dir}", fg=typer.colors.CYAN)
        typer.secho(f"[*] Hint: Use 'jmai skills install <PATH>' to install to a specific location", fg=typer.colors.CYAN)
    else:
        target_dir = target_dir.resolve()
        typer.echo(f"[*] Target parent directory: {target_dir}")

    # 1. Preview
    preview = manager.get_install_preview(target_dir)
    typer.secho("\n[ Installation Structure Preview ]", fg=typer.colors.BRIGHT_MAGENTA, bold=True)
    typer.echo(f"Target Directory: {preview['skill_target_dir']}")
    typer.echo("File Tree:")

    # Simple tree visualization
    for f in preview['files']:
        typer.echo(f"  - {f}")
    typer.echo("")

    # 2. Confirmation (unless -y is passed)
    if not yes:
        if not typer.confirm("Proceed with installation?", default=True):
            typer.echo("Installation cancelled.")
            return

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    # 2. Duplicate Check / Conflict Handing
    if force:
        manager.install(target_dir, overwrite=True)
    else:
        if manager.has_conflicts(target_dir):
            typer.echo("Warning: Some skill files already exist in the target directory.")
            if yes or typer.confirm("Overwrite existing files?"):
                manager.install(target_dir, overwrite=True)
            else:
                typer.echo("Skipping existing files.")
                manager.install(target_dir, overwrite=False)
        else:
            manager.install(target_dir)

    typer.echo("Skills installed successfully.")


@skills_app.command("uninstall")
def uninstall_skills(
        target_dir: Path | None = typer.Argument(
            None, help="Directory to uninstall skills from. Defaults to ~/.claude/skills/jmcomic"
        ),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Uninstall skills from the directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    manager = SkillManager()

    if target_dir is None:
        # Default to ~/.claude/skills
        target_dir = Path.home() / ".claude" / "skills"
        typer.secho(f"[*] Path not specified, uninstalling from default: {target_dir}", fg=typer.colors.YELLOW)
    else:
        target_dir = target_dir.resolve()
        typer.echo(f"[*] Uninstalling from: {target_dir}")

    if not target_dir.exists():
        typer.echo(f"Target directory {target_dir} does not exist.")
        return

    # 1. Preview
    preview = manager.get_uninstall_preview(target_dir)
    if not preview['exists']:
        typer.secho(f"[*] Skipped: No skill directory (jmcomic) found under {target_dir}", fg=typer.colors.YELLOW)
        return

    typer.secho("\n[ Uninstallation Preview ]", fg=typer.colors.BRIGHT_RED, bold=True)
    typer.secho(f"THE FOLLOWING DIRECTORY AND FILES WILL BE DELETED:", fg=typer.colors.RED)
    typer.echo(f"Path: {preview['skill_target_dir']}")
    typer.echo("File Tree:")
    for f in preview['files']:
        typer.echo(f"  - {f}")

    typer.echo("\nOnly the specific skill folder (jmcomic) will be removed. Your other skills remain safe.")
    typer.echo("")

    # 2. Confirmation
    if yes or typer.confirm(f"Are you sure you want to PERMANENTLY DELETE the 'jmcomic' skill folder?", default=False):
        if manager.uninstall(target_dir):
            typer.echo("Skills uninstalled successfully.")
        else:
            # This case is usually handled by the 'exists' check above, but as a fallback:
            typer.secho(f"[*] Skipped: No skill directory found.", fg=typer.colors.YELLOW)


# Option group
option_app = typer.Typer(name="option", help="Manage jmcomic option (configuration)", no_args_is_help=True)
app.add_typer(option_app, name="option")


@option_app.command("show")
def option_show():
    """Show current option file path and content"""
    option_path = resolve_option_path()
    typer.echo(f"Option file: {option_path}")
    typer.echo("---")
    if option_path.exists():
        typer.echo(option_path.read_text(encoding="utf-8"))
    else:
        typer.echo("Option file does not exist yet.")


@option_app.command("path")
def option_path():
    """Print option file path"""
    option_path = resolve_option_path()
    typer.echo(option_path)


@option_app.command("edit")
def option_edit():
    """Open option file in default editor"""
    import platform
    import subprocess

    option_path = resolve_option_path()
    path = str(option_path)

    if not option_path.exists():
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
